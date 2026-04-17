from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.application.booking.orchestration_outcomes import InvalidStateOutcome, OrchestrationSuccess
from app.application.booking.services import BookingService
from app.application.booking.state_services import BookingStateService
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.application.doctor.operations import DoctorOperationsService
from app.application.doctor.patient_read import DoctorPatientSnapshot
from app.application.voice import SpeechToTextService, VoiceSearchModeStore
from app.common.i18n import I18nService
from app.domain.access_identity.models import (
    ActorIdentity,
    ActorStatus,
    ActorType,
    ClinicRoleAssignment,
    DoctorProfile,
    RoleCode,
    StaffMember,
    StaffStatus,
    TelegramBinding,
)
from app.domain.booking import Booking, BookingStatusHistory
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, RecordStatus, Service
from app.infrastructure.speech.fake_provider import FakeSpeechToTextProvider
from app.interfaces.bots.doctor.router import make_router as make_doctor_router


class _FakeTx(AbstractAsyncContextManager):
    def __init__(self, repo: "_FakeBookingRepo") -> None:
        self.repo = repo
        self.snapshot = None

    async def __aenter__(self):
        self.snapshot = dict(self.repo.bookings)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type:
            self.repo.bookings = self.snapshot or {}
        return False

    async def get_booking_for_update(self, booking_id: str):
        return self.repo.bookings.get(booking_id)

    async def upsert_booking(self, item: Booking) -> None:
        self.repo.bookings[item.booking_id] = item

    async def append_booking_status_history(self, item: BookingStatusHistory) -> None:
        self.repo.history.append(item)

    async def cancel_scheduled_reminders_for_booking_in_transaction(self, *, booking_id: str, canceled_at: datetime, reason_code: str) -> int:
        return 0

    async def append_outbox_event(self, event) -> None:
        return None


class _FakeBookingRepo:
    def __init__(self, bookings: list[Booking]) -> None:
        self.bookings = {row.booking_id: row for row in bookings}
        self.history: list[BookingStatusHistory] = []

    def transaction(self):
        return _FakeTx(self)

    async def get_booking(self, booking_id: str):
        return self.bookings.get(booking_id)

    async def list_bookings_by_patient(self, *, patient_id: str):
        return [row for row in self.bookings.values() if row.patient_id == patient_id]

    async def list_bookings_by_doctor_time_window(self, *, doctor_id: str, start_at: datetime, end_at: datetime):
        return [row for row in self.bookings.values() if row.doctor_id == doctor_id and start_at <= row.scheduled_start_at < end_at]


class _OrchestrationStub:
    def __init__(self, state: BookingStateService) -> None:
        self.state = state

    async def complete_booking(self, *, booking_id: str, reason_code: str | None = None):
        try:
            changed = await self.state.transition_booking(booking_id=booking_id, to_status="completed", reason_code=reason_code or "completed")
        except Exception:
            return InvalidStateOutcome(kind="invalid_state", reason="cannot_complete")
        return OrchestrationSuccess(kind="success", entity=changed.entity)


class _Message:
    def __init__(self, text: str, user_id: int = 101):
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _SearchStub:
    async def search_patients(self, query):
        return SimpleNamespace(exact_matches=[], suggestions=[])

    async def search_doctors(self, query):
        return []

    async def search_services(self, query):
        return []


class _SnapshotReader:
    def __init__(self, data: dict[str, DoctorPatientSnapshot]) -> None:
        self.data = data

    async def read_snapshot(self, *, patient_id: str) -> DoctorPatientSnapshot | None:
        return self.data.get(patient_id)


def _access_with_doctor(*, include_profile: bool = True, role: RoleCode = RoleCode.DOCTOR) -> AccessResolver:
    repo = InMemoryAccessRepository()
    repo.upsert_actor_identity(ActorIdentity(actor_id="a1", actor_type=ActorType.STAFF, display_name="Dr. X", status=ActorStatus.ACTIVE, locale="en"))
    repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id="tb1", actor_id="a1", telegram_user_id=101))
    repo.upsert_staff_member(StaffMember(staff_id="s1", actor_id="a1", clinic_id="c1", full_name="Doctor X", display_name="Doctor X", staff_status=StaffStatus.ACTIVE))
    repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id="r1", staff_id="s1", clinic_id="c1", role_code=role))
    if include_profile:
        repo.upsert_doctor_profile(DoctorProfile(doctor_profile_id="dp1", doctor_id="d1", staff_id="s1", clinic_id="c1"))
    return AccessResolver(repo)


def _reference() -> ClinicReferenceService:
    repo = InMemoryClinicReferenceRepository()
    repo.upsert_clinic(Clinic(clinic_id="c1", code="main", display_name="Main", timezone="UTC", default_locale="en", status=RecordStatus.ACTIVE))
    repo.upsert_branch(Branch(branch_id="b1", clinic_id="c1", display_name="Main", address_text="-", timezone="UTC", status=RecordStatus.ACTIVE))
    repo.upsert_doctor(Doctor(doctor_id="d1", clinic_id="c1", branch_id="b1", display_name="Doctor X", specialty_code="gen", public_booking_enabled=True, status=RecordStatus.ACTIVE))
    repo.upsert_service(Service(service_id="svc1", clinic_id="c1", code="CONS", title_key="service.consult", duration_minutes=30, specialty_required=False, status=RecordStatus.ACTIVE))
    return ClinicReferenceService(repo)


def _snapshot_data() -> dict[str, DoctorPatientSnapshot]:
    return {
        "pat1": DoctorPatientSnapshot(
            patient_id="pat1",
            display_name="Ann One",
            patient_number="P-001",
            phone_raw="+1 555 123 4567",
            has_photo=True,
            active_flags_summary="allergy",
        ),
        "pat2": DoctorPatientSnapshot(
            patient_id="pat2",
            display_name="Bob Two",
            patient_number="P-002",
            phone_raw="+1 555 999 0000",
            has_photo=False,
            active_flags_summary=None,
        ),
    }


def _booking(booking_id: str, *, patient_id: str, doctor_id: str, minutes: int, status: str) -> Booking:
    start = datetime(2026, 4, 17, 8, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes)
    return Booking(
        booking_id=booking_id,
        clinic_id="c1",
        branch_id="b1",
        patient_id=patient_id,
        doctor_id=doctor_id,
        service_id="svc1",
        slot_id=None,
        booking_mode="admin",
        source_channel="telegram",
        scheduled_start_at=start,
        scheduled_end_at=start + timedelta(minutes=30),
        status=status,
        confirmation_required=True,
        created_at=start - timedelta(days=1),
        updated_at=start - timedelta(days=1),
    )


def _ops(bookings: list[Booking], *, snapshot_data: dict[str, DoctorPatientSnapshot] | None = None) -> DoctorOperationsService:
    repo = _FakeBookingRepo(bookings)
    booking_service = BookingService(repo)
    booking_state = BookingStateService(repo)
    return DoctorOperationsService(
        access_resolver=_access_with_doctor(),
        booking_service=booking_service,
        booking_state_service=booking_state,
        booking_orchestration=_OrchestrationStub(booking_state),
        reference_service=_reference(),
        patient_reader=_SnapshotReader(snapshot_data or _snapshot_data()),
    )


def test_doctor_queue_filters_and_orders_for_doctor() -> None:
    ops = _ops([
        _booking("b3", patient_id="pat2", doctor_id="d1", minutes=120, status="confirmed"),
        _booking("b1", patient_id="pat1", doctor_id="d1", minutes=60, status="confirmed"),
        _booking("b2", patient_id="pat1", doctor_id="d2", minutes=90, status="confirmed"),
    ])
    rows = asyncio.run(ops.list_today_queue(doctor_id="d1", now=datetime(2026, 4, 17, 7, 0, tzinfo=timezone.utc)))
    assert [r.booking_id for r in rows] == ["b1", "b3"]


def test_next_patient_and_empty_state_work() -> None:
    ops = _ops([_booking("b1", patient_id="pat1", doctor_id="d1", minutes=60, status="confirmed")])
    row = asyncio.run(ops.get_next_patient(doctor_id="d1", now=datetime(2026, 4, 17, 8, 30, tzinfo=timezone.utc)))
    assert row is not None and row.booking_id == "b1"
    empty = _ops([])
    assert asyncio.run(empty.get_next_patient(doctor_id="d1")) is None


def test_booking_detail_compact_and_no_chart_blob() -> None:
    ops = _ops([_booking("b1", patient_id="pat1", doctor_id="d1", minutes=60, status="confirmed")])
    detail = asyncio.run(ops.get_booking_detail(doctor_id="d1", booking_id="b1"))
    assert detail is not None
    assert detail.patient_card.display_name == "Ann One"
    assert "history" not in detail.service_label.lower()


def test_doctor_actions_valid_and_invalid_transitions() -> None:
    ops = _ops([_booking("b1", patient_id="pat1", doctor_id="d1", minutes=60, status="confirmed")])
    ok = asyncio.run(ops.apply_booking_action(doctor_id="d1", booking_id="b1", action="checked_in"))
    assert ok.kind == "success"
    fail = asyncio.run(ops.apply_booking_action(doctor_id="d1", booking_id="b1", action="completed"))
    assert fail.kind == "invalid_state"


def test_identity_safety_for_missing_profile_and_wrong_role() -> None:
    missing = _access_with_doctor(include_profile=False)
    did, reason = missing.resolve_doctor_id(101)
    assert did is None and reason == "doctor.identity.missing_profile"
    wrong_role = _access_with_doctor(role=RoleCode.OWNER)
    did2, reason2 = wrong_role.resolve_doctor_id(101)
    assert did2 is None and reason2 == "access.denied.role"


def test_doctor_router_today_queue_empty_and_patient_open_search_path() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    ops = _ops([_booking("b1", patient_id="pat1", doctor_id="d1", minutes=60, status="confirmed")])
    router = make_doctor_router(
        i18n=i18n,
        access_resolver=ops.access_resolver,
        search_service=_SearchStub(),
        stt_service=SpeechToTextService(provider=FakeSpeechToTextProvider(), timeout_sec=2.0, confidence_threshold=0.7, language_hint="auto"),
        voice_mode_store=VoiceSearchModeStore(),
        booking_service=ops.booking_service,
        booking_state_service=ops.booking_state_service,
        booking_orchestration=ops.booking_orchestration,
        reference_service=ops.reference_service,
        patient_reader=ops.patient_reader,
        default_locale="en",
        max_voice_duration_sec=30,
        max_voice_file_size_bytes=1000,
        voice_mode_ttl_sec=45,
    )
    today_handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "today_queue")
    m1 = _Message("/today_queue")
    asyncio.run(today_handler(m1))
    assert m1.answers and "Today's queue" in m1.answers[0]

    patient_handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "patient_open")
    m2 = _Message("/patient_open pat1")
    asyncio.run(patient_handler(m2))
    assert m2.answers and "Patient pat1" in m2.answers[0]


def test_patient_open_blocks_unrelated_patient_id() -> None:
    ops = _ops([_booking("b1", patient_id="pat1", doctor_id="d1", minutes=60, status="confirmed")])
    denied = asyncio.run(ops.build_patient_quick_card(patient_id="pat2", doctor_id="d1"))
    assert denied is None


def test_patient_open_router_denies_unrelated_raw_patient_id() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    ops = _ops([_booking("b1", patient_id="pat1", doctor_id="d1", minutes=60, status="confirmed")])
    router = make_doctor_router(
        i18n=i18n,
        access_resolver=ops.access_resolver,
        search_service=_SearchStub(),
        stt_service=SpeechToTextService(provider=FakeSpeechToTextProvider(), timeout_sec=2.0, confidence_threshold=0.7, language_hint="auto"),
        voice_mode_store=VoiceSearchModeStore(),
        booking_service=ops.booking_service,
        booking_state_service=ops.booking_state_service,
        booking_orchestration=ops.booking_orchestration,
        reference_service=ops.reference_service,
        patient_reader=ops.patient_reader,
        default_locale="en",
        max_voice_duration_sec=30,
        max_voice_file_size_bytes=1000,
        voice_mode_ttl_sec=45,
    )
    patient_handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "patient_open")
    msg = _Message("/patient_open pat2")
    asyncio.run(patient_handler(msg))
    assert msg.answers and "unavailable for this doctor" in msg.answers[0]


def test_patient_quick_card_reads_fresh_snapshot_not_startup_registry() -> None:
    snapshots = _snapshot_data()
    ops = _ops([_booking("b1", patient_id="pat1", doctor_id="d1", minutes=60, status="confirmed")], snapshot_data=snapshots)
    snapshots["pat1"] = DoctorPatientSnapshot(
        patient_id="pat1",
        display_name="Ann Renamed",
        patient_number="P-001",
        phone_raw="+1 555 123 7777",
        has_photo=True,
        active_flags_summary="allergy",
    )
    card = asyncio.run(ops.build_patient_quick_card(patient_id="pat1", doctor_id="d1"))
    assert card is not None
    assert card.display_name == "Ann Renamed"
    assert card.phone_hint == "***7777"


def test_patient_open_id_hint_respects_visibility_guard() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    ops = _ops([_booking("b1", patient_id="pat1", doctor_id="d1", minutes=60, status="confirmed")])

    router = make_doctor_router(
        i18n=i18n,
        access_resolver=ops.access_resolver,
        search_service=_SearchStub(),
        stt_service=SpeechToTextService(provider=FakeSpeechToTextProvider(), timeout_sec=2.0, confidence_threshold=0.7, language_hint="auto"),
        voice_mode_store=VoiceSearchModeStore(),
        booking_service=ops.booking_service,
        booking_state_service=ops.booking_state_service,
        booking_orchestration=ops.booking_orchestration,
        reference_service=ops.reference_service,
        patient_reader=ops.patient_reader,
        default_locale="en",
        max_voice_duration_sec=30,
        max_voice_file_size_bytes=1000,
        voice_mode_ttl_sec=45,
    )
    search_handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "search_patient")
    msg = _Message("/search_patient id:pat2")
    asyncio.run(search_handler(msg))
    assert msg.answers
    assert not any("/patient_open pat2" in ans for ans in msg.answers)


def test_today_queue_uses_branch_local_day_not_raw_utc() -> None:
    ops = _ops([
        _booking("b0", patient_id="pat1", doctor_id="d1", minutes=-60, status="confirmed"),
        _booking("b1", patient_id="pat1", doctor_id="d1", minutes=60, status="confirmed"),
    ])
    # branch is UTC in fixture, so both same day for UTC; swap to Pacific to ensure boundary behavior
    ops.reference_service.repository.branches["b1"] = Branch(
        branch_id="b1", clinic_id="c1", display_name="Main", address_text="-", timezone="America/Los_Angeles", status=RecordStatus.ACTIVE
    )
    rows = asyncio.run(ops.list_today_queue(doctor_id="d1", now=datetime(2026, 4, 17, 1, 0, tzinfo=timezone.utc)))
    assert rows == []
    later = asyncio.run(ops.list_today_queue(doctor_id="d1", now=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)))
    assert [r.booking_id for r in later] == ["b0", "b1"]


def test_today_queue_timezone_fallbacks_clinic_then_default() -> None:
    ops = _ops([_booking("b1", patient_id="pat1", doctor_id="d1", minutes=60, status="confirmed")])
    ops.reference_service.repository.branches["b1"] = Branch(
        branch_id="b1", clinic_id="c1", display_name="Main", address_text="-", timezone="", status=RecordStatus.ACTIVE
    )
    ops.reference_service.repository.clinics["c1"] = SimpleNamespace(clinic_id="c1", timezone="Europe/Berlin")
    rows = asyncio.run(ops.list_today_queue(doctor_id="d1", now=datetime(2026, 4, 17, 0, 30, tzinfo=timezone.utc)))
    assert rows
    ops.reference_service.repository.clinics["c1"] = SimpleNamespace(clinic_id="c1", timezone="")
    ops.app_default_timezone = "UTC"
    rows2 = asyncio.run(ops.list_today_queue(doctor_id="d1", now=datetime(2026, 4, 17, 0, 30, tzinfo=timezone.utc)))
    assert rows2
