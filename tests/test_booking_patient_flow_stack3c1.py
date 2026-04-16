from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.application.booking.orchestration import BookingOrchestrationService
from app.application.booking.orchestration_outcomes import OrchestrationSuccess
from app.application.booking.patient_resolution import BookingPatientResolutionService
from app.application.booking.state_services import BookingSessionStateService, BookingStateService, SlotHoldStateService, WaitlistStateService
from app.application.booking.telegram_flow import BookingPatientFlowService
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.application.policy import InMemoryPolicyRepository, PolicyResolver
from app.domain.booking import AdminEscalation, AvailabilitySlot, Booking, BookingSession, BookingStatusHistory, SessionEvent, SlotHold, WaitlistEntry
from app.domain.clinic_reference.models import Clinic, Doctor, Service


class _Tx(AbstractAsyncContextManager):
    def __init__(self, repo: "_Repo") -> None:
        self.repo = repo
        self._snapshot: dict[str, Any] | None = None

    async def __aenter__(self):
        self._snapshot = self.repo.snapshot()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            assert self._snapshot is not None
            self.repo.restore(self._snapshot)
        return False

    async def upsert_booking_session(self, item: BookingSession) -> None:
        self.repo.sessions[item.booking_session_id] = item

    async def append_session_event(self, event: SessionEvent) -> None:
        self.repo.session_events.append(event)

    async def upsert_slot_hold(self, item: SlotHold) -> None:
        self.repo.holds[item.slot_hold_id] = item

    async def upsert_booking(self, item: Booking) -> None:
        self.repo.bookings[item.booking_id] = item

    async def append_booking_status_history(self, item: BookingStatusHistory) -> None:
        self.repo.history.append(item)

    async def upsert_waitlist_entry(self, item: WaitlistEntry) -> None:
        self.repo.waitlist[item.waitlist_entry_id] = item

    async def upsert_admin_escalation(self, item: AdminEscalation) -> None:
        self.repo.escalations[item.admin_escalation_id] = item

    async def get_booking_session_for_update(self, booking_session_id: str) -> BookingSession | None:
        return self.repo.sessions.get(booking_session_id)

    async def get_slot_hold_for_update(self, slot_hold_id: str) -> SlotHold | None:
        return self.repo.holds.get(slot_hold_id)

    async def get_booking_for_update(self, booking_id: str) -> Booking | None:
        return self.repo.bookings.get(booking_id)

    async def get_availability_slot_for_update(self, slot_id: str) -> AvailabilitySlot | None:
        return self.repo.slots.get(slot_id)

    async def get_waitlist_entry_for_update(self, waitlist_entry_id: str) -> WaitlistEntry | None:
        return self.repo.waitlist.get(waitlist_entry_id)

    async def find_slot_hold_for_update(self, *, slot_id: str, booking_session_id: str) -> SlotHold | None:
        for hold in self.repo.holds.values():
            if hold.slot_id == slot_id and hold.booking_session_id == booking_session_id:
                return hold
        return None

    async def list_active_holds_for_slot_for_update(self, *, slot_id: str) -> list[SlotHold]:
        return [h for h in self.repo.holds.values() if h.slot_id == slot_id and h.status == "active"]

    async def list_active_holds_for_session_for_update(self, *, booking_session_id: str) -> list[SlotHold]:
        return [h for h in self.repo.holds.values() if h.booking_session_id == booking_session_id and h.status == "active"]

    async def list_live_bookings_for_slot_for_update(self, *, slot_id: str) -> list[Booking]:
        return [b for b in self.repo.bookings.values() if b.slot_id == slot_id and b.status in {"pending_confirmation", "confirmed"}]


class _Repo:
    def __init__(self) -> None:
        now = datetime(2026, 4, 16, 10, 0, tzinfo=timezone.utc)
        self.sessions: dict[str, BookingSession] = {}
        self.holds: dict[str, SlotHold] = {}
        self.bookings: dict[str, Booking] = {}
        self.history: list[BookingStatusHistory] = []
        self.session_events: list[SessionEvent] = []
        self.waitlist: dict[str, WaitlistEntry] = {}
        self.escalations: dict[str, AdminEscalation] = {}
        self.slots = {
            "slot_1": AvailabilitySlot(
                slot_id="slot_1",
                clinic_id="clinic_main",
                branch_id="branch_1",
                doctor_id="doctor_1",
                start_at=now + timedelta(days=1),
                end_at=now + timedelta(days=1, minutes=30),
                status="open",
                visibility_policy="public",
                service_scope=None,
                source_ref=None,
                updated_at=now,
            )
        }

    def transaction(self):
        return _Tx(self)

    def snapshot(self) -> dict[str, Any]:
        return {
            "sessions": dict(self.sessions),
            "holds": dict(self.holds),
            "bookings": dict(self.bookings),
            "history": list(self.history),
            "session_events": list(self.session_events),
            "waitlist": dict(self.waitlist),
            "escalations": dict(self.escalations),
        }

    def restore(self, snapshot: dict[str, Any]) -> None:
        self.sessions = snapshot["sessions"]
        self.holds = snapshot["holds"]
        self.bookings = snapshot["bookings"]
        self.history = snapshot["history"]
        self.session_events = snapshot["session_events"]
        self.waitlist = snapshot["waitlist"]
        self.escalations = snapshot["escalations"]

    async def get_booking_session(self, booking_session_id: str) -> BookingSession | None:
        return self.sessions.get(booking_session_id)

    async def list_active_sessions_for_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> list[BookingSession]:
        return [
            row
            for row in self.sessions.values()
            if row.clinic_id == clinic_id and row.telegram_user_id == telegram_user_id and row.status in {"initiated", "in_progress", "review_ready", "awaiting_contact_confirmation", "awaiting_slot_selection"}
        ]

    async def list_open_slots(
        self,
        *,
        clinic_id: str,
        start_at: datetime,
        end_at: datetime,
        doctor_id: str | None,
        branch_id: str | None,
        limit: int,
    ) -> list[AvailabilitySlot]:
        rows = [
            slot
            for slot in self.slots.values()
            if slot.clinic_id == clinic_id
            and slot.status == "open"
            and start_at <= slot.start_at < end_at
            and (doctor_id is None or slot.doctor_id == doctor_id)
            and (branch_id is None or slot.branch_id == branch_id)
        ]
        return sorted(rows, key=lambda row: row.start_at)[:limit]

    async def list_open_admin_escalations(self, *, clinic_id: str, limit: int) -> list[AdminEscalation]:
        rows = [row for row in self.escalations.values() if row.clinic_id == clinic_id and row.status == "open"]
        return sorted(rows, key=lambda row: row.created_at, reverse=True)[:limit]

    async def list_recent_bookings_by_statuses(self, *, clinic_id: str, statuses: tuple[str, ...], limit: int) -> list[Booking]:
        rows = [row for row in self.bookings.values() if row.clinic_id == clinic_id and row.status in statuses]
        return sorted(rows, key=lambda row: row.created_at, reverse=True)[:limit]

    async def list_bookings_by_patient(self, *, patient_id: str) -> list[Booking]:
        return [row for row in self.bookings.values() if row.patient_id == patient_id]

    async def get_booking(self, booking_id: str) -> Booking | None:
        return self.bookings.get(booking_id)


class _Finder:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    async def find_patients_by_exact_contact(self, *, contact_type: str, contact_value: str) -> list[dict]:
        return self.rows

    async def find_patients_by_external_id(self, *, external_system: str, external_id: str) -> list[dict]:
        return []


class _PatientCreator:
    def __init__(self) -> None:
        self.calls = 0

    async def create_minimal_patient(self, *, clinic_id: str, display_name: str, phone: str) -> str:
        self.calls += 1
        return "pat_new"


def _reference_service() -> ClinicReferenceService:
    repo = InMemoryClinicReferenceRepository()
    repo.upsert_clinic(Clinic(clinic_id="clinic_main", code="MAIN", display_name="Main", timezone="UTC", default_locale="en"))
    repo.upsert_service(Service(service_id="service_consult", clinic_id="clinic_main", code="CONSULT", title_key="s", duration_minutes=30))
    repo.upsert_doctor(Doctor(doctor_id="doctor_1", clinic_id="clinic_main", display_name="Dr One", specialty_code="dent", branch_id="branch_1"))
    return ClinicReferenceService(repo)


def _build_flow(*, finder_rows: list[dict]) -> tuple[BookingPatientFlowService, _Repo, _PatientCreator]:
    repo = _Repo()
    policy = PolicyResolver(InMemoryPolicyRepository())
    orch = BookingOrchestrationService(
        repository=repo,  # type: ignore[arg-type]
        booking_session_state_service=BookingSessionStateService(repo),  # type: ignore[arg-type]
        slot_hold_state_service=SlotHoldStateService(repo),  # type: ignore[arg-type]
        booking_state_service=BookingStateService(repo),  # type: ignore[arg-type]
        waitlist_state_service=WaitlistStateService(repo),  # type: ignore[arg-type]
        patient_resolution_service=BookingPatientResolutionService(_Finder(finder_rows)),
        policy_resolver=policy,
    )
    creator = _PatientCreator()
    flow = BookingPatientFlowService(
        orchestration=orch,
        reads=repo,
        reference=_reference_service(),
        patient_creator=creator,
    )
    return flow, repo, creator


def test_happy_path_with_no_match_creates_canonical_patient_and_finalizes() -> None:
    flow, repo, creator = _build_flow(finder_rows=[])
    session = asyncio.run(flow.start_or_resume_session(clinic_id="clinic_main", telegram_user_id=999))
    asyncio.run(flow.update_service(booking_session_id=session.booking_session_id, service_id="service_consult"))
    asyncio.run(flow.update_doctor_preference(booking_session_id=session.booking_session_id, doctor_preference_type="any"))
    slot = asyncio.run(flow.list_slots_for_session(booking_session_id=session.booking_session_id))[0]
    selected = asyncio.run(flow.select_slot(booking_session_id=session.booking_session_id, slot_id=slot.slot_id))
    assert isinstance(selected, OrchestrationSuccess)
    asyncio.run(flow.set_contact_phone(booking_session_id=session.booking_session_id, phone="+1 555 200 1000"))
    resolution = asyncio.run(
        flow.resolve_patient_from_contact(
            booking_session_id=session.booking_session_id,
            phone="+15552001000",
            fallback_display_name="New Person",
        )
    )
    assert resolution.kind == "new_patient_created"
    assert creator.calls == 1
    review = asyncio.run(flow.mark_review_ready(booking_session_id=session.booking_session_id))
    assert isinstance(review, OrchestrationSuccess)
    finalized = asyncio.run(flow.finalize(booking_session_id=session.booking_session_id))
    assert isinstance(finalized, OrchestrationSuccess)
    assert finalized.entity.status == "pending_confirmation"
    assert len(repo.bookings) == 1


def test_exact_match_path_does_not_create_duplicate_patient() -> None:
    flow, _, creator = _build_flow(
        finder_rows=[{"patient_id": "pat_existing", "clinic_id": "clinic_main", "display_name": "Existing"}]
    )
    session = asyncio.run(flow.start_or_resume_session(clinic_id="clinic_main", telegram_user_id=1001))
    asyncio.run(flow.update_service(booking_session_id=session.booking_session_id, service_id="service_consult"))
    asyncio.run(flow.update_doctor_preference(booking_session_id=session.booking_session_id, doctor_preference_type="any"))
    slot = asyncio.run(flow.list_slots_for_session(booking_session_id=session.booking_session_id))[0]
    asyncio.run(flow.select_slot(booking_session_id=session.booking_session_id, slot_id=slot.slot_id))
    asyncio.run(flow.set_contact_phone(booking_session_id=session.booking_session_id, phone="+1 555 100 1000"))
    resolution = asyncio.run(
        flow.resolve_patient_from_contact(
            booking_session_id=session.booking_session_id,
            phone="+15551001000",
            fallback_display_name="Ignored",
        )
    )
    assert resolution.kind == "exact_match"
    assert creator.calls == 0


def test_ambiguous_path_escalates_and_does_not_leak_candidates() -> None:
    flow, repo, _ = _build_flow(
        finder_rows=[
            {"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"},
            {"patient_id": "pat_2", "clinic_id": "clinic_main", "display_name": "Two"},
        ]
    )
    session = asyncio.run(flow.start_or_resume_session(clinic_id="clinic_main", telegram_user_id=1002))
    resolution = asyncio.run(
        flow.resolve_patient_from_contact(
            booking_session_id=session.booking_session_id,
            phone="+15550000000",
            fallback_display_name="Anon",
        )
    )
    assert resolution.kind == "ambiguous_escalated"
    assert len(repo.escalations) == 1
    assert resolution.escalation is None or "pat_" not in str(resolution)


def test_admin_visibility_lists_escalations_and_pending_bookings() -> None:
    flow, repo, _ = _build_flow(finder_rows=[])
    now = datetime(2026, 4, 16, 11, 0, tzinfo=timezone.utc)
    repo.escalations["e1"] = AdminEscalation(
        admin_escalation_id="e1",
        clinic_id="clinic_main",
        booking_session_id="s42",
        patient_id=None,
        reason_code="ambiguous_exact_contact",
        priority="high",
        status="open",
        assigned_to_actor_id=None,
        payload_summary={"session_status": "admin_escalated"},
        created_at=now,
        updated_at=now,
    )
    repo.bookings["b1"] = Booking(
        booking_id="b1",
        clinic_id="clinic_main",
        branch_id="branch_1",
        patient_id="pat_1",
        doctor_id="doctor_1",
        service_id="service_consult",
        slot_id="slot_1",
        booking_mode="patient_bot",
        source_channel="telegram",
        scheduled_start_at=now + timedelta(days=1),
        scheduled_end_at=now + timedelta(days=1, minutes=30),
        status="pending_confirmation",
        reason_for_visit_short=None,
        patient_note=None,
        confirmation_required=True,
        confirmed_at=None,
        canceled_at=None,
        checked_in_at=None,
        in_service_at=None,
        completed_at=None,
        no_show_at=None,
        created_at=now,
        updated_at=now,
    )
    escalations = asyncio.run(flow.list_admin_escalations(clinic_id="clinic_main"))
    bookings = asyncio.run(flow.list_admin_new_bookings(clinic_id="clinic_main"))
    assert escalations[0].booking_session_id == "s42"
    assert bookings[0].booking_id == "b1"


def test_session_resume_mapping_and_stale_callback_guard() -> None:
    flow, _, _ = _build_flow(finder_rows=[])
    session = asyncio.run(flow.start_or_resume_session(clinic_id="clinic_main", telegram_user_id=4001))
    mapped = asyncio.run(flow.determine_resume_panel(booking_session_id=session.booking_session_id))
    assert mapped is not None
    assert mapped.panel_key == "service_selection"
    asyncio.run(flow.update_service(booking_session_id=session.booking_session_id, service_id="service_consult"))
    mapped = asyncio.run(flow.determine_resume_panel(booking_session_id=session.booking_session_id))
    assert mapped is not None
    assert mapped.panel_key == "doctor_preference_selection"
    valid = asyncio.run(
        flow.validate_active_session_callback(
            clinic_id="clinic_main",
            telegram_user_id=4001,
            callback_session_id=session.booking_session_id,
        )
    )
    stale = asyncio.run(
        flow.validate_active_session_callback(
            clinic_id="clinic_main",
            telegram_user_id=4001,
            callback_session_id="bs_stale",
        )
    )
    assert valid is True
    assert stale is False


def test_existing_booking_controls_exact_match_no_match_and_ambiguous() -> None:
    flow, repo, _ = _build_flow(finder_rows=[{"patient_id": "pat_existing", "clinic_id": "clinic_main", "display_name": "Existing"}])
    now = datetime(2026, 4, 16, 11, 0, tzinfo=timezone.utc)
    repo.bookings["b1"] = Booking(
        booking_id="b1",
        clinic_id="clinic_main",
        branch_id="branch_1",
        patient_id="pat_existing",
        doctor_id="doctor_1",
        service_id="service_consult",
        slot_id="slot_1",
        booking_mode="patient_bot",
        source_channel="telegram",
        scheduled_start_at=now + timedelta(days=1),
        scheduled_end_at=now + timedelta(days=1, minutes=30),
        status="confirmed",
        reason_for_visit_short=None,
        patient_note=None,
        confirmation_required=True,
        confirmed_at=None,
        canceled_at=None,
        checked_in_at=None,
        in_service_at=None,
        completed_at=None,
        no_show_at=None,
        created_at=now,
        updated_at=now,
    )
    exact = asyncio.run(
        flow.resolve_existing_booking_by_contact(
            clinic_id="clinic_main",
            telegram_user_id=4101,
            phone="+15550101010",
        )
    )
    assert exact.kind == "exact_match"
    assert exact.bookings[0].booking_id == "b1"

    flow_no_match, _, _ = _build_flow(finder_rows=[])
    no_match = asyncio.run(
        flow_no_match.resolve_existing_booking_by_contact(
            clinic_id="clinic_main",
            telegram_user_id=4102,
            phone="+15550101011",
        )
    )
    assert no_match.kind == "no_match"

    flow_ambiguous, repo_ambiguous, _ = _build_flow(
        finder_rows=[
            {"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"},
            {"patient_id": "pat_2", "clinic_id": "clinic_main", "display_name": "Two"},
        ]
    )
    ambiguous = asyncio.run(
        flow_ambiguous.resolve_existing_booking_by_contact(
            clinic_id="clinic_main",
            telegram_user_id=4103,
            phone="+15550101012",
        )
    )
    assert ambiguous.kind == "ambiguous_escalated"
    assert len(repo_ambiguous.escalations) == 1


def test_reschedule_cancel_waitlist_and_admin_open_details() -> None:
    flow, repo, _ = _build_flow(finder_rows=[])
    now = datetime(2026, 4, 16, 11, 0, tzinfo=timezone.utc)
    repo.escalations["e1"] = AdminEscalation(
        admin_escalation_id="e1",
        clinic_id="clinic_main",
        booking_session_id="s42",
        patient_id=None,
        reason_code="ambiguous_exact_contact",
        priority="high",
        status="open",
        assigned_to_actor_id=None,
        payload_summary={"session_status": "admin_escalated"},
        created_at=now,
        updated_at=now,
    )
    repo.bookings["b1"] = Booking(
        booking_id="b1",
        clinic_id="clinic_main",
        branch_id="branch_1",
        patient_id="pat_1",
        doctor_id="doctor_1",
        service_id="service_consult",
        slot_id="slot_1",
        booking_mode="patient_bot",
        source_channel="telegram",
        scheduled_start_at=now + timedelta(days=1),
        scheduled_end_at=now + timedelta(days=1, minutes=30),
        status="confirmed",
        reason_for_visit_short=None,
        patient_note=None,
        confirmation_required=True,
        confirmed_at=None,
        canceled_at=None,
        checked_in_at=None,
        in_service_at=None,
        completed_at=None,
        no_show_at=None,
        created_at=now,
        updated_at=now,
    )

    rescheduled = asyncio.run(flow.request_reschedule(booking_id="b1"))
    assert isinstance(rescheduled, OrchestrationSuccess)
    assert rescheduled.entity.status == "reschedule_requested"

    canceled = asyncio.run(flow.cancel_booking(booking_id="b1"))
    assert isinstance(canceled, OrchestrationSuccess)
    assert canceled.entity.status == "canceled"

    waitlist = asyncio.run(flow.join_earlier_slot_waitlist(booking_id="b1", telegram_user_id=5010))
    assert isinstance(waitlist, OrchestrationSuccess)
    assert len(repo.waitlist) == 1
    assert next(iter(repo.waitlist.values())).status == "active"

    escalation_detail = asyncio.run(flow.get_admin_escalation_detail(clinic_id="clinic_main", escalation_id="e1"))
    booking_detail = asyncio.run(flow.get_admin_booking_detail(booking_id="b1"))
    assert escalation_detail is not None
    assert booking_detail is not None
    assert booking_detail.doctor_label == "Dr One"
