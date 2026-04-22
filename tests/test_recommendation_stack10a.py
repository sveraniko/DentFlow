from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.application.booking.orchestration_outcomes import OrchestrationSuccess
from app.application.doctor.operations import DoctorOperationsService
from app.application.recommendation import PatientRecommendationDeliveryService, RecommendationService
from app.domain.access_identity.models import ActorIdentity, ActorStatus, ActorType, ClinicRoleAssignment, DoctorProfile, RoleCode, StaffMember, StaffStatus, TelegramBinding
from app.domain.booking import Booking
from app.domain.recommendations import Recommendation
from app.infrastructure.db.recommendation_repository import DbRecommendationRepository


class InMemoryRecommendationRepository:
    def __init__(self) -> None:
        self.rows: dict[str, Recommendation] = {}

    async def get(self, recommendation_id: str) -> Recommendation | None:
        return self.rows.get(recommendation_id)

    async def save(self, item: Recommendation) -> None:
        self.rows[item.recommendation_id] = item

    async def list_for_patient(self, *, patient_id: str, include_terminal: bool = False) -> list[Recommendation]:
        rows = [row for row in self.rows.values() if row.patient_id == patient_id]
        if not include_terminal:
            rows = [row for row in rows if row.status not in {"withdrawn", "expired"}]
        return sorted(rows, key=lambda x: x.created_at, reverse=True)

    async def list_for_booking(self, *, booking_id: str) -> list[Recommendation]:
        return [row for row in self.rows.values() if row.booking_id == booking_id]

    async def list_for_chart(self, *, chart_id: str) -> list[Recommendation]:
        return [row for row in self.rows.values() if row.chart_id == chart_id]

    async def find_telegram_user_ids_by_patient(self, *, clinic_id: str, patient_id: str) -> list[int]:
        if clinic_id == "c1" and patient_id == "p1":
            return [777001]
        return []


class _RecommendationPushSender:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send_patient_recommendation_delivery(
        self,
        *,
        telegram_user_id: int,
        text: str,
        button_text: str,
        callback_data: str,
    ) -> None:
        self.calls.append(
            {
                "telegram_user_id": telegram_user_id,
                "text": text,
                "button_text": button_text,
                "callback_data": callback_data,
            }
        )


def test_recommendation_lifecycle_happy_path_and_idempotent() -> None:
    repo = InMemoryRecommendationRepository()
    service = RecommendationService(repo)

    created = asyncio.run(service.create_recommendation(
        clinic_id="c1",
        patient_id="p1",
        recommendation_type="aftercare",
        source_kind="doctor_manual",
        title="Aftercare",
        body_text="Use cold compress.",
    ))
    assert created.status == "prepared"

    issued = asyncio.run(service.issue(recommendation_id=created.recommendation_id))
    viewed = asyncio.run(service.mark_viewed(recommendation_id=created.recommendation_id))
    ack = asyncio.run(service.acknowledge(recommendation_id=created.recommendation_id))
    accepted = asyncio.run(service.accept(recommendation_id=created.recommendation_id))
    accepted_again = asyncio.run(service.accept(recommendation_id=created.recommendation_id))

    assert issued and issued.status == "issued"
    assert viewed and viewed.status == "viewed"
    assert ack and ack.status == "acknowledged"
    assert accepted and accepted.status == "accepted"
    assert accepted_again and accepted_again.status == "accepted"


def test_recommendation_invalid_transition_rejected() -> None:
    repo = InMemoryRecommendationRepository()
    service = RecommendationService(repo)
    created = asyncio.run(service.create_recommendation(
        clinic_id="c1",
        patient_id="p1",
        recommendation_type="monitoring",
        source_kind="doctor_manual",
        title="Monitoring",
        body_text="Observe swelling.",
    ))
    with pytest.raises(ValueError):
        asyncio.run(service.accept(recommendation_id=created.recommendation_id))


@dataclass
class _BookingRepo:
    booking: Booking

    async def load_booking(self, booking_id: str):
        return self.booking if self.booking.booking_id == booking_id else None

    async def list_by_patient(self, *, patient_id: str):
        return [self.booking] if self.booking.patient_id == patient_id else []

    async def list_by_doctor_time_window(self, *, doctor_id: str, start_at, end_at):
        return []


class _BookState:
    async def transition_booking(self, **kwargs):
        raise AssertionError("unused")


class _Orch:
    async def complete_booking(self, *, booking_id: str, reason_code: str | None = None):
        now = datetime.now(timezone.utc)
        done = Booking(
            booking_id=booking_id,
            clinic_id="c1",
            branch_id="br1",
            patient_id="p1",
            service_id="srv",
            doctor_id="doc1",
            slot_id="s1",
            booking_mode="manual",
            source_channel="doctor",
            status="completed",
            scheduled_start_at=now,
            scheduled_end_at=now,
            confirmation_required=True,
            completed_at=now,
            canceled_at=None,
            no_show_at=None,
            checked_in_at=now,
            in_service_at=now,
            reason_for_visit_short=None,
            patient_note=None,
            confirmed_at=now,
            created_at=now,
            updated_at=now,
        )
        return OrchestrationSuccess(kind="success", entity=done)


def _access_for_doctor() -> AccessResolver:
    repo = InMemoryAccessRepository()
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    repo.upsert_actor_identity(ActorIdentity(actor_id="a1", actor_type=ActorType.STAFF, display_name="Doc", status=ActorStatus.ACTIVE, locale="en"))
    repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id="tg1", actor_id="a1", telegram_user_id=41))
    repo.upsert_staff_member(StaffMember(staff_id="s1", actor_id="a1", clinic_id="c1", full_name="Doc", display_name="Doc", staff_status=StaffStatus.ACTIVE))
    repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id="ra1", staff_id="s1", clinic_id="c1", role_code=RoleCode.DOCTOR, granted_at=now))
    repo.upsert_doctor_profile(DoctorProfile(doctor_profile_id="dp1", doctor_id="doc1", staff_id="s1", clinic_id="c1", branch_id="br1", specialty_code="gen", active_for_booking=True, active_for_clinical_work=True))
    return AccessResolver(repo)


def test_doctor_issue_and_booking_trigger() -> None:
    now = datetime.now(timezone.utc)
    booking = Booking(
        booking_id="b1",
        clinic_id="c1",
        branch_id="br1",
        patient_id="p1",
        service_id="srv",
        doctor_id="doc1",
        slot_id="s1",
        booking_mode="manual",
        source_channel="doctor",
        status="in_service",
        scheduled_start_at=now,
        scheduled_end_at=now,
        confirmation_required=True,
        completed_at=None,
        canceled_at=None,
        no_show_at=None,
        checked_in_at=now,
        in_service_at=now,
        reason_for_visit_short=None,
        patient_note=None,
        confirmed_at=now,
        created_at=now,
        updated_at=now,
    )
    rec_repo = InMemoryRecommendationRepository()
    rec_service = RecommendationService(rec_repo)
    ops = DoctorOperationsService(
        access_resolver=_access_for_doctor(),
        booking_service=_BookingRepo(booking),
        booking_state_service=_BookState(),
        booking_orchestration=_Orch(),
        reference_service=None,  # not used in this test path
        patient_reader=None,  # not used in this test path
        recommendation_service=rec_service,
    )

    issued = asyncio.run(ops.issue_recommendation(
        doctor_id="doc1",
        clinic_id="c1",
        patient_id="p1",
        recommendation_type="follow_up",
        title="Follow-up",
        body_text="Return in 7 days",
        booking_id="b1",
    ))
    assert issued and issued.status == "issued"

    asyncio.run(ops.apply_booking_action(doctor_id="doc1", booking_id="b1", action="completed"))
    rows = asyncio.run(rec_service.list_for_booking(booking_id="b1"))
    assert any(row.source_kind == "booking_trigger" and row.status == "issued" for row in rows)
    denied = asyncio.run(
        ops.issue_recommendation(
            doctor_id="doc_x",
            clinic_id="c1",
            patient_id="p1",
            recommendation_type="follow_up",
            title="Denied",
            body_text="Denied",
            booking_id="b1",
        )
    )
    assert denied is None


def test_proactive_delivery_uses_callback_open_path() -> None:
    sender = _RecommendationPushSender()
    delivery = PatientRecommendationDeliveryService(
        binding_reader=InMemoryRecommendationRepository(),
        sender=sender,
    )
    result = asyncio.run(
        delivery.deliver_patient_recommendation_if_possible(
            clinic_id="c1",
            patient_id="p1",
            recommendation_id="rec_123",
            locale="en",
        )
    )
    assert result.status == "delivered"
    assert sender.calls and sender.calls[0]["callback_data"] == "prec:open:rec_123"
    assert "/recommendation_open" not in str(sender.calls[0]["text"])


def test_proactive_delivery_safe_skip_without_trusted_binding() -> None:
    sender = _RecommendationPushSender()
    delivery = PatientRecommendationDeliveryService(
        binding_reader=InMemoryRecommendationRepository(),
        sender=sender,
    )
    result = asyncio.run(
        delivery.deliver_patient_recommendation_if_possible(
            clinic_id="c1",
            patient_id="missing_patient",
            recommendation_id="rec_404",
            locale="en",
        )
    )
    assert result.status == "skipped_no_binding"
    assert sender.calls == []


def test_doctor_issue_recommendation_still_succeeds_when_proactive_delivery_fails_safe() -> None:
    now = datetime.now(timezone.utc)
    booking = Booking(
        booking_id="b1",
        clinic_id="c1",
        branch_id="br1",
        patient_id="p1",
        service_id="srv",
        doctor_id="doc1",
        slot_id="s1",
        booking_mode="manual",
        source_channel="doctor",
        status="in_service",
        scheduled_start_at=now,
        scheduled_end_at=now,
        confirmation_required=True,
        completed_at=None,
        canceled_at=None,
        no_show_at=None,
        checked_in_at=now,
        in_service_at=now,
        reason_for_visit_short=None,
        patient_note=None,
        confirmed_at=now,
        created_at=now,
        updated_at=now,
    )
    rec_repo = InMemoryRecommendationRepository()
    rec_service = RecommendationService(rec_repo)

    class _FailingBindingReader:
        async def find_telegram_user_ids_by_patient(self, *, clinic_id: str, patient_id: str) -> list[int]:
            raise RuntimeError("db down")

    delivery = PatientRecommendationDeliveryService(
        binding_reader=_FailingBindingReader(),
        sender=_RecommendationPushSender(),
    )
    ops = DoctorOperationsService(
        access_resolver=_access_for_doctor(),
        booking_service=_BookingRepo(booking),
        booking_state_service=_BookState(),
        booking_orchestration=_Orch(),
        reference_service=None,
        patient_reader=None,
        recommendation_service=rec_service,
        recommendation_delivery_service=delivery,
    )
    issued = asyncio.run(
        ops.issue_recommendation(
            doctor_id="doc1",
            clinic_id="c1",
            patient_id="p1",
            recommendation_type="follow_up",
            title="Follow-up",
            body_text="Return in 7 days",
            booking_id="b1",
        )
    )
    assert issued is not None
    assert issued.status == "issued"


def test_db_recommendation_repository_emits_events(monkeypatch: pytest.MonkeyPatch) -> None:
    appended: list[str] = []

    class _Result:
        def __init__(self, value=None):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class _Conn:
        def __init__(self):
            self.status = None

        async def execute(self, statement, params):
            sql = str(statement)
            if "SELECT status" in sql:
                return _Result(self.status)
            if "INSERT INTO recommendation.recommendations" in sql:
                self.status = params["status"]
                return _Result()
            return _Result()

    class _Engine:
        def __init__(self):
            self.conn = _Conn()

        def begin(self):
            class _Ctx:
                async def __aenter__(self_non):
                    return engine.conn

                async def __aexit__(self_non, exc_type, exc, tb):
                    return False

            return _Ctx()

        async def dispose(self):
            return None

    engine = _Engine()

    class _Outbox:
        def __init__(self, _db):
            pass

        async def append_on_connection(self, conn, event):
            appended.append(event.event_name)

    monkeypatch.setattr("app.infrastructure.db.recommendation_repository.create_engine", lambda _: engine)
    monkeypatch.setattr("app.infrastructure.db.recommendation_repository.OutboxRepository", _Outbox)

    repo = DbRecommendationRepository(db_config=object())
    now = datetime.now(timezone.utc)
    item = Recommendation(
        recommendation_id="r1",
        clinic_id="c1",
        patient_id="p1",
        booking_id=None,
        encounter_id=None,
        chart_id=None,
        issued_by_actor_id=None,
        source_kind="doctor_manual",
        recommendation_type="aftercare",
        title="A",
        body_text="B",
        rationale_text=None,
        status="prepared",
        issued_at=None,
        viewed_at=None,
        acknowledged_at=None,
        accepted_at=None,
        declined_at=None,
        expired_at=None,
        withdrawn_at=None,
        created_at=now,
        updated_at=now,
    )

    asyncio.run(repo.save(item))
    asyncio.run(repo.save(Recommendation(**{**item.__dict__, "status": "issued", "issued_at": now, "updated_at": now})))
    assert "recommendation.created" in appended
    assert "recommendation.prepared" in appended
    assert "recommendation.issued" in appended


def test_db_patient_resolution_ambiguity_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_fetch_all(_db, _sql, _params):
        return [{"patient_id": "p1"}, {"patient_id": "p2"}]

    monkeypatch.setattr("app.infrastructure.db.recommendation_repository._fetch_all", _fake_fetch_all)
    repo = DbRecommendationRepository(db_config=object())
    resolved = asyncio.run(repo.find_patient_id_by_telegram_user(clinic_id="c1", telegram_user_id=100))
    assert resolved is None
