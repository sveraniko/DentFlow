from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import pytest

from app.application.booking.orchestration import BookingOrchestrationService
from app.application.booking.orchestration_outcomes import (
    AmbiguousMatchOutcome,
    ConflictOutcome,
    InvalidStateOutcome,
    NoMatchOutcome,
    OrchestrationSuccess,
)
from app.application.booking.patient_resolution import BookingPatientResolutionService
from app.application.booking.state_services import (
    BookingSessionStateService,
    BookingStateService,
    SlotHoldStateService,
    WaitlistStateService,
)
from app.application.policy import InMemoryPolicyRepository, PolicyResolver
from app.application.communication import BookingReminderPlanner, BookingReminderService
from app.domain.booking import (
    AdminEscalation,
    AvailabilitySlot,
    Booking,
    BookingSession,
    BookingStatusHistory,
    SessionEvent,
    SlotHold,
    WaitlistEntry,
)
from app.domain.communication import ReminderJob
from app.domain.patient_registry.models import PatientPreference


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
        if item.status == "active":
            for hold in self.repo.holds.values():
                if hold.slot_id == item.slot_id and hold.slot_hold_id != item.slot_hold_id and hold.status == "active":
                    raise ValueError("uq_slot_holds_active_slot")
                if (
                    hold.booking_session_id == item.booking_session_id
                    and hold.slot_hold_id != item.slot_hold_id
                    and hold.status == "active"
                ):
                    raise ValueError("uq_slot_holds_active_session")
        self.repo.holds[item.slot_hold_id] = item

    async def upsert_booking(self, item: Booking) -> None:
        if item.slot_id and item.status in {"pending_confirmation", "confirmed", "reschedule_requested", "checked_in", "in_service"}:
            for booking in self.repo.bookings.values():
                if booking.slot_id == item.slot_id and booking.booking_id != item.booking_id and booking.status in {
                    "pending_confirmation",
                    "confirmed",
                    "reschedule_requested",
                    "checked_in",
                    "in_service",
                }:
                    raise ValueError("uq_bookings_live_slot")
        self.repo.bookings[item.booking_id] = item

    async def append_booking_status_history(self, item: BookingStatusHistory) -> None:
        if self.repo.fail_history:
            raise RuntimeError("history append failed")
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
        return [
            b
            for b in self.repo.bookings.values()
            if b.slot_id == slot_id and b.status in {"pending_confirmation", "confirmed", "reschedule_requested", "checked_in", "in_service"}
        ]


class _Repo:
    def __init__(self) -> None:
        now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
        self.sessions = {
            "s1": BookingSession(
                booking_session_id="s1",
                clinic_id="clinic_main",
                branch_id="branch_central",
                telegram_user_id=3001,
                resolved_patient_id=None,
                status="in_progress",
                route_type="service_first",
                service_id="service_consult",
                urgency_type=None,
                requested_date_type=None,
                requested_date=None,
                time_window=None,
                doctor_preference_type=None,
                doctor_id=None,
                doctor_code_raw=None,
                selected_slot_id=None,
                selected_hold_id=None,
                contact_phone_snapshot="+15551000",
                notes=None,
                expires_at=now,
                created_at=now,
                updated_at=now,
            )
        }
        self.slots = {
            "slot1": AvailabilitySlot(
                slot_id="slot1",
                clinic_id="clinic_main",
                branch_id="branch_central",
                doctor_id="doctor_anna",
                start_at=datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 4, 21, 10, 30, tzinfo=timezone.utc),
                status="open",
                visibility_policy="public",
                service_scope=None,
                source_ref=None,
                updated_at=now,
            )
        }
        self.holds: dict[str, SlotHold] = {}
        self.bookings: dict[str, Booking] = {}
        self.history: list[BookingStatusHistory] = []
        self.session_events: list[SessionEvent] = []
        self.waitlist: dict[str, WaitlistEntry] = {}
        self.escalations: dict[str, AdminEscalation] = {}
        self.fail_history = False

    def transaction(self):
        return _Tx(self)

    async def get_booking_session(self, booking_session_id: str):
        return self.sessions.get(booking_session_id)

    async def get_slot_hold(self, slot_hold_id: str):
        return self.holds.get(slot_hold_id)

    async def get_booking(self, booking_id: str):
        return self.bookings.get(booking_id)

    async def get_waitlist_entry(self, waitlist_entry_id: str):
        return self.waitlist.get(waitlist_entry_id)

    def snapshot(self):
        return {
            "sessions": dict(self.sessions),
            "holds": dict(self.holds),
            "bookings": dict(self.bookings),
            "history": list(self.history),
            "events": list(self.session_events),
            "waitlist": dict(self.waitlist),
            "escalations": dict(self.escalations),
        }

    def restore(self, snap):
        self.sessions = snap["sessions"]
        self.holds = snap["holds"]
        self.bookings = snap["bookings"]
        self.history = snap["history"]
        self.session_events = snap["events"]
        self.waitlist = snap["waitlist"]
        self.escalations = snap["escalations"]


class _Finder:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    async def find_patients_by_exact_contact(self, *, contact_type: str, contact_value: str) -> list[dict]:
        return self.rows

    async def find_patients_by_external_id(self, *, external_system: str, external_id: str) -> list[dict]:
        return self.rows


class _ReminderRepo:
    def __init__(self) -> None:
        self.jobs: dict[str, ReminderJob] = {}

    async def create_reminder_job(self, item: ReminderJob) -> None:
        self.jobs[item.reminder_id] = item

    async def list_reminder_jobs_for_booking(self, *, booking_id: str) -> list[ReminderJob]:
        return sorted([j for j in self.jobs.values() if j.booking_id == booking_id], key=lambda row: row.scheduled_for)

    async def cancel_scheduled_reminders_for_booking(self, *, booking_id: str, canceled_at: datetime, reason_code: str) -> int:
        affected = 0
        for reminder_id, job in list(self.jobs.items()):
            if job.booking_id != booking_id or job.status != "scheduled" or job.scheduled_for <= canceled_at:
                continue
            self.jobs[reminder_id] = ReminderJob(
                **{**asdict(job), "status": "canceled", "updated_at": canceled_at, "canceled_at": canceled_at, "cancel_reason_code": reason_code}
            )
            affected += 1
        return affected


class _PreferenceReader:
    def __init__(self, pref: PatientPreference | None) -> None:
        self.pref = pref

    async def get_preferences(self, patient_id: str) -> PatientPreference | None:
        return self.pref if self.pref and self.pref.patient_id == patient_id else None


def _build_orchestrator(
    repo: _Repo,
    finder_rows: list[dict],
    *,
    reminder_service: BookingReminderService | None = None,
) -> BookingOrchestrationService:
    patient_resolution = BookingPatientResolutionService(_Finder(finder_rows))
    policy = PolicyResolver(InMemoryPolicyRepository())
    return BookingOrchestrationService(
        repository=repo,
        booking_session_state_service=BookingSessionStateService(repo),  # type: ignore[arg-type]
        slot_hold_state_service=SlotHoldStateService(repo),  # type: ignore[arg-type]
        booking_state_service=BookingStateService(repo),  # type: ignore[arg-type]
        waitlist_state_service=WaitlistStateService(repo),  # type: ignore[arg-type]
        patient_resolution_service=patient_resolution,
        policy_resolver=policy,
        reminder_service=reminder_service,
    )


def test_session_start_update_and_resolve_paths() -> None:
    repo = _Repo()
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}])

    started = asyncio.run(orchestrator.start_booking_session(clinic_id="clinic_main", telegram_user_id=999, route_type="service_first"))
    assert isinstance(started, OrchestrationSuccess)

    updated = asyncio.run(orchestrator.update_session_context(booking_session_id="s1", notes="needs evening slot"))
    assert isinstance(updated, OrchestrationSuccess)
    assert updated.entity.notes == "needs evening slot"

    exact = asyncio.run(orchestrator.resolve_patient_for_session(booking_session_id="s1", contact_type="phone", contact_value="+1 555"))
    assert isinstance(exact, OrchestrationSuccess)
    assert exact.entity.resolved_patient_id == "pat_1"

    no_match_orchestrator = _build_orchestrator(repo, [])
    no_match = asyncio.run(no_match_orchestrator.resolve_patient_for_session(booking_session_id="s1", contact_type="phone", contact_value="+1"))
    assert isinstance(no_match, NoMatchOutcome)

    ambiguous_orchestrator = _build_orchestrator(
        repo,
        [
            {"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"},
            {"patient_id": "pat_2", "clinic_id": "clinic_main", "display_name": "Two"},
        ],
    )
    ambiguous = asyncio.run(
        ambiguous_orchestrator.resolve_patient_for_session(booking_session_id="s1", contact_type="phone", contact_value="+1")
    )
    assert isinstance(ambiguous, AmbiguousMatchOutcome)


def test_hold_selection_conflict_release_and_finalize_happy_path() -> None:
    repo = _Repo()
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}])
    repo.sessions["s1"] = BookingSession(**{**asdict(repo.sessions["s1"]), "resolved_patient_id": "pat_1"})

    hold = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(hold, OrchestrationSuccess)
    assert hold.entity.status == "active"

    second_session = BookingSession(**{**asdict(repo.sessions["s1"]), "booking_session_id": "s2", "selected_hold_id": None, "selected_slot_id": None})
    repo.sessions["s2"] = second_session
    conflict = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s2", slot_id="slot1"))
    assert isinstance(conflict, ConflictOutcome)

    review_ready = asyncio.run(orchestrator.mark_session_review_ready(booking_session_id="s1"))
    assert isinstance(review_ready, OrchestrationSuccess)
    assert review_ready.entity.status == "review_ready"

    finalized = asyncio.run(orchestrator.finalize_booking_from_session(booking_session_id="s1"))
    assert isinstance(finalized, OrchestrationSuccess)
    assert len(repo.bookings) == 1
    assert len(repo.history) == 1
    consumed = next(iter(repo.holds.values()))
    assert consumed.status == "consumed"
    assert repo.sessions["s1"].status == "completed"

    release_invalid = asyncio.run(orchestrator.release_or_expire_hold_for_session(booking_session_id="s1", action="released"))
    assert isinstance(release_invalid, InvalidStateOutcome)


def test_finalize_invalid_and_atomic_rollback() -> None:
    repo = _Repo()
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}])

    unresolved = asyncio.run(orchestrator.finalize_booking_from_session(booking_session_id="s1"))
    assert isinstance(unresolved, InvalidStateOutcome)

    repo.sessions["s1"] = BookingSession(**{**asdict(repo.sessions["s1"]), "resolved_patient_id": "pat_1", "status": "review_ready"})
    held = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(held, OrchestrationSuccess)
    repo.sessions["s1"] = BookingSession(**{**asdict(repo.sessions["s1"]), "status": "review_ready"})
    repo.fail_history = True

    with pytest.raises(RuntimeError):
        asyncio.run(orchestrator.finalize_booking_from_session(booking_session_id="s1"))

    assert repo.bookings == {}
    assert repo.history == []
    assert next(iter(repo.holds.values())).status == "active"


def test_select_slot_uses_canonical_session_transitions_from_initiated() -> None:
    repo = _Repo()
    repo.sessions["s1"] = BookingSession(
        **{**asdict(repo.sessions["s1"]), "status": "initiated", "contact_phone_snapshot": None}
    )
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}])

    selected = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(selected, OrchestrationSuccess)
    assert repo.sessions["s1"].status == "awaiting_contact_confirmation"
    lifecycle_events = [event.event_name for event in repo.session_events if event.event_name.startswith("booking_session.")]
    assert lifecycle_events[-3:] == [
        "booking_session.in_progress",
        "booking_session.awaiting_slot_selection",
        "booking_session.awaiting_contact_confirmation",
    ]


def test_release_hold_transitions_session_canonically_and_clears_selection() -> None:
    repo = _Repo()
    repo.sessions["s1"] = BookingSession(
        **{**asdict(repo.sessions["s1"]), "status": "awaiting_contact_confirmation", "contact_phone_snapshot": None}
    )
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}])

    hold = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(hold, OrchestrationSuccess)
    released = asyncio.run(orchestrator.release_or_expire_hold_for_session(booking_session_id="s1", action="released"))
    assert isinstance(released, OrchestrationSuccess)
    assert repo.sessions["s1"].status == "awaiting_slot_selection"
    assert repo.sessions["s1"].selected_hold_id is None
    assert repo.sessions["s1"].selected_slot_id is None
    assert any(event.event_name == "booking_session.awaiting_slot_selection" for event in repo.session_events)


def test_finalize_fails_cleanly_when_service_missing() -> None:
    repo = _Repo()
    repo.sessions["s1"] = BookingSession(
        **{
            **asdict(repo.sessions["s1"]),
            "resolved_patient_id": "pat_1",
            "status": "review_ready",
            "service_id": None,
        }
    )
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}])
    held = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(held, OrchestrationSuccess)
    repo.sessions["s1"] = BookingSession(**{**asdict(repo.sessions["s1"]), "status": "review_ready", "service_id": None})

    finalized = asyncio.run(orchestrator.finalize_booking_from_session(booking_session_id="s1"))
    assert isinstance(finalized, InvalidStateOutcome)
    assert "selected service" in finalized.reason
    assert repo.bookings == {}


@pytest.mark.parametrize("terminal_status", ["released", "expired", "canceled", "consumed"])
def test_same_session_same_slot_terminal_hold_gets_fresh_hold(terminal_status: str) -> None:
    repo = _Repo()
    repo.sessions["s1"] = BookingSession(
        **{**asdict(repo.sessions["s1"]), "status": "awaiting_contact_confirmation", "contact_phone_snapshot": None}
    )
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}])
    first = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(first, OrchestrationSuccess)
    old_hold_id = first.entity.slot_hold_id
    repo.holds[old_hold_id] = SlotHold(**{**asdict(repo.holds[old_hold_id]), "status": terminal_status})
    repo.sessions["s1"] = BookingSession(**{**asdict(repo.sessions["s1"]), "selected_hold_id": None, "selected_slot_id": None})

    second = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(second, OrchestrationSuccess)
    assert second.entity.status == "active"
    assert second.entity.slot_hold_id != old_hold_id


def test_same_session_reselect_different_slot_releases_previous_active_hold() -> None:
    repo = _Repo()
    slot2 = AvailabilitySlot(**{**asdict(repo.slots["slot1"]), "slot_id": "slot2"})
    repo.slots["slot2"] = slot2
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}])

    first = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(first, OrchestrationSuccess)
    second = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot2"))
    assert isinstance(second, OrchestrationSuccess)

    old_hold = repo.holds[first.entity.slot_hold_id]
    new_hold = repo.holds[second.entity.slot_hold_id]
    assert old_hold.status == "released"
    assert new_hold.status == "active"
    assert repo.sessions["s1"].selected_slot_id == "slot2"
    assert repo.sessions["s1"].selected_hold_id == second.entity.slot_hold_id


def test_same_session_never_keeps_two_active_holds_after_slot_switch() -> None:
    repo = _Repo()
    slot2 = AvailabilitySlot(**{**asdict(repo.slots["slot1"]), "slot_id": "slot2"})
    repo.slots["slot2"] = slot2
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}])

    first = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(first, OrchestrationSuccess)
    second = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot2"))
    assert isinstance(second, OrchestrationSuccess)

    active = [hold for hold in repo.holds.values() if hold.booking_session_id == "s1" and hold.status == "active"]
    assert len(active) == 1
    assert active[0].slot_id == "slot2"


def test_same_session_same_slot_with_active_hold_reuses_existing_hold() -> None:
    repo = _Repo()
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}])

    first = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(first, OrchestrationSuccess)
    second = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(second, OrchestrationSuccess)
    assert second.entity.slot_hold_id == first.entity.slot_hold_id
    assert len(repo.holds) == 1


def test_review_ready_requires_selected_hold_to_be_active() -> None:
    repo = _Repo()
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}])
    repo.sessions["s1"] = BookingSession(**{**asdict(repo.sessions["s1"]), "resolved_patient_id": "pat_1"})

    hold = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(hold, OrchestrationSuccess)
    repo.holds[hold.entity.slot_hold_id] = SlotHold(**{**asdict(repo.holds[hold.entity.slot_hold_id]), "status": "released"})

    result = asyncio.run(orchestrator.mark_session_review_ready(booking_session_id="s1"))
    assert isinstance(result, InvalidStateOutcome)
    assert "selected active hold" in result.reason


def test_cancel_expire_escalate_waitlist_and_booking_lifecycle() -> None:
    repo = _Repo()
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}])
    repo.sessions["s1"] = BookingSession(**{**asdict(repo.sessions["s1"]), "resolved_patient_id": "pat_1"})
    hold = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(hold, OrchestrationSuccess)

    canceled = asyncio.run(orchestrator.cancel_session(booking_session_id="s1"))
    assert isinstance(canceled, OrchestrationSuccess)
    assert repo.sessions["s1"].status == "canceled"

    repo.sessions["s3"] = BookingSession(**{**asdict(repo.sessions["s1"]), "booking_session_id": "s3", "status": "in_progress"})
    hold2 = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s3", slot_id="slot1"))
    assert isinstance(hold2, OrchestrationSuccess)
    expired = asyncio.run(orchestrator.expire_session(booking_session_id="s3"))
    assert isinstance(expired, OrchestrationSuccess)
    assert repo.sessions["s3"].status == "expired"

    repo.sessions["s4"] = BookingSession(**{**asdict(repo.sessions["s1"]), "booking_session_id": "s4", "status": "in_progress"})
    escalated = asyncio.run(orchestrator.escalate_session_to_admin(booking_session_id="s4", reason_code="manual_needed"))
    assert escalated.kind in {"escalated", "success"}
    assert len(repo.escalations) == 1

    waitlist = asyncio.run(
        orchestrator.create_waitlist_entry(clinic_id="clinic_main", service_id="service_consult", source_session_id="s4", telegram_user_id=3001)
    )
    assert isinstance(waitlist, OrchestrationSuccess)
    assert waitlist.entity.status == "active"

    now = datetime(2026, 4, 22, 9, 0, tzinfo=timezone.utc)
    booking = Booking(
        booking_id="b1",
        clinic_id="clinic_main",
        branch_id="branch_central",
        patient_id="pat_1",
        doctor_id="doctor_anna",
        service_id="service_consult",
        slot_id="slot1",
        booking_mode="patient_bot",
        source_channel="telegram",
        scheduled_start_at=now,
        scheduled_end_at=now.replace(minute=30),
        status="confirmed",
        reason_for_visit_short=None,
        patient_note=None,
        confirmation_required=True,
        confirmed_at=now,
        canceled_at=None,
        checked_in_at=None,
        in_service_at=None,
        completed_at=None,
        no_show_at=None,
        created_at=now,
        updated_at=now,
    )
    repo.bookings["b1"] = booking
    rescheduled = asyncio.run(orchestrator.request_booking_reschedule(booking_id="b1"))
    assert isinstance(rescheduled, OrchestrationSuccess)
    canceled_booking = asyncio.run(orchestrator.cancel_booking(booking_id="b1"))
    assert isinstance(canceled_booking, OrchestrationSuccess)
    assert any(row.new_status == "reschedule_requested" for row in repo.history)
    assert any(row.new_status == "canceled" for row in repo.history)


def test_reminder_scheduling_on_finalize_and_storage_outside_booking() -> None:
    repo = _Repo()
    reminder_repo = _ReminderRepo()
    reminder_service = BookingReminderService(
        repository=reminder_repo,
        planner=BookingReminderPlanner(PolicyResolver(InMemoryPolicyRepository())),
        policy_resolver=PolicyResolver(InMemoryPolicyRepository()),
    )
    orchestrator = _build_orchestrator(
        repo,
        [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}],
        reminder_service=reminder_service,
    )
    repo.sessions["s1"] = BookingSession(**{**asdict(repo.sessions["s1"]), "resolved_patient_id": "pat_1", "status": "review_ready"})
    hold = asyncio.run(orchestrator.select_slot_and_activate_hold(booking_session_id="s1", slot_id="slot1"))
    assert isinstance(hold, OrchestrationSuccess)
    repo.sessions["s1"] = BookingSession(**{**asdict(repo.sessions["s1"]), "status": "review_ready", "service_id": "service_consult"})

    finalized = asyncio.run(orchestrator.finalize_booking_from_session(booking_session_id="s1"))
    assert isinstance(finalized, OrchestrationSuccess)
    assert finalized.entity.booking_id in repo.bookings
    jobs = asyncio.run(reminder_service.list_booking_reminders(booking_id=finalized.entity.booking_id))
    assert jobs
    assert all(job.status == "scheduled" for job in jobs)
    assert all(job.booking_id == finalized.entity.booking_id for job in jobs)
    assert not hasattr(finalized.entity, "reminder_status")


def test_reminder_replacement_on_reschedule_and_cancel_on_cancel() -> None:
    repo = _Repo()
    reminder_repo = _ReminderRepo()
    reminder_service = BookingReminderService(
        repository=reminder_repo,
        planner=BookingReminderPlanner(PolicyResolver(InMemoryPolicyRepository())),
        policy_resolver=PolicyResolver(InMemoryPolicyRepository()),
    )
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}], reminder_service=reminder_service)
    now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    booking = Booking(
        booking_id="b_sched",
        clinic_id="clinic_main",
        branch_id="branch_central",
        patient_id="pat_1",
        doctor_id="doctor_anna",
        service_id="service_consult",
        slot_id="slot1",
        booking_mode="patient_bot",
        source_channel="telegram",
        scheduled_start_at=now.replace(day=21, hour=10),
        scheduled_end_at=now.replace(day=21, hour=10, minute=30),
        status="confirmed",
        reason_for_visit_short=None,
        patient_note=None,
        confirmation_required=True,
        confirmed_at=now,
        canceled_at=None,
        checked_in_at=None,
        in_service_at=None,
        completed_at=None,
        no_show_at=None,
        created_at=now,
        updated_at=now,
    )
    repo.bookings[booking.booking_id] = booking
    asyncio.run(reminder_service.replace_booking_reminder_plan(booking=booking))
    before = asyncio.run(reminder_service.list_booking_reminders(booking_id=booking.booking_id))
    assert before and all(item.status == "scheduled" for item in before)

    rescheduled = asyncio.run(
        orchestrator.reschedule_booking(
            booking_id=booking.booking_id,
            scheduled_start_at=now.replace(day=22, hour=13),
            scheduled_end_at=now.replace(day=22, hour=13, minute=30),
        )
    )
    assert isinstance(rescheduled, OrchestrationSuccess)
    after = asyncio.run(reminder_service.list_booking_reminders(booking_id=booking.booking_id))
    assert any(item.status == "canceled" for item in after)
    assert any(item.status == "scheduled" and item.scheduled_for.date().day == 22 for item in after)

    canceled = asyncio.run(orchestrator.cancel_booking(booking_id=booking.booking_id))
    assert isinstance(canceled, OrchestrationSuccess)
    done = asyncio.run(reminder_service.list_booking_reminders(booking_id=booking.booking_id))
    assert not any(item.status == "scheduled" for item in done if item.scheduled_for > datetime.now(timezone.utc))


def test_reminder_policy_uses_patient_preferences_then_clinic_fallback() -> None:
    policy_repo = InMemoryPolicyRepository()
    resolver = PolicyResolver(policy_repo)

    pref_reader = _PreferenceReader(
        PatientPreference(
            patient_preference_id="pp1",
            patient_id="pat_1",
            preferred_language="uk",
            preferred_reminder_channel="sms",
            allow_sms=True,
            allow_telegram=True,
            allow_call=False,
            allow_email=False,
        )
    )
    reminder_repo = _ReminderRepo()
    service = BookingReminderService(
        repository=reminder_repo,
        planner=BookingReminderPlanner(resolver),
        policy_resolver=resolver,
        patient_preference_reader=pref_reader,
    )
    booking = Booking(
        booking_id="b_pref",
        clinic_id="clinic_main",
        branch_id="branch_central",
        patient_id="pat_1",
        doctor_id="doctor_anna",
        service_id="service_consult",
        slot_id="slot1",
        booking_mode="patient_bot",
        source_channel="telegram",
        scheduled_start_at=datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc),
        scheduled_end_at=datetime(2026, 4, 22, 10, 30, tzinfo=timezone.utc),
        status="confirmed",
        reason_for_visit_short=None,
        patient_note=None,
        confirmation_required=True,
        confirmed_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
        canceled_at=None,
        checked_in_at=None,
        in_service_at=None,
        completed_at=None,
        no_show_at=None,
        created_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
    )
    jobs = asyncio.run(service.replace_booking_reminder_plan(booking=booking))
    assert jobs and all(job.channel == "sms" and job.locale_at_send_time == "uk" for job in jobs)

    fallback_service = BookingReminderService(
        repository=reminder_repo,
        planner=BookingReminderPlanner(resolver),
        policy_resolver=resolver,
        patient_preference_reader=_PreferenceReader(None),
    )
    jobs_fb = asyncio.run(fallback_service.replace_booking_reminder_plan(booking=Booking(**{**asdict(booking), "booking_id": "b_fallback", "patient_id": "pat_2"})))
    assert jobs_fb and all(job.channel == "telegram" for job in jobs_fb)
    assert all(job.locale_at_send_time == "ru" for job in jobs_fb)


def test_reminder_cancel_on_completed_and_no_show() -> None:
    repo = _Repo()
    reminder_repo = _ReminderRepo()
    service = BookingReminderService(
        repository=reminder_repo,
        planner=BookingReminderPlanner(PolicyResolver(InMemoryPolicyRepository())),
        policy_resolver=PolicyResolver(InMemoryPolicyRepository()),
    )
    orchestrator = _build_orchestrator(repo, [{"patient_id": "pat_1", "clinic_id": "clinic_main", "display_name": "One"}], reminder_service=service)
    start = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
    booking = Booking(
        booking_id="b_done",
        clinic_id="clinic_main",
        branch_id="branch_central",
        patient_id="pat_1",
        doctor_id="doctor_anna",
        service_id="service_consult",
        slot_id="slot1",
        booking_mode="patient_bot",
        source_channel="telegram",
        scheduled_start_at=start,
        scheduled_end_at=start.replace(minute=30),
        status="in_service",
        reason_for_visit_short=None,
        patient_note=None,
        confirmation_required=True,
        confirmed_at=start,
        canceled_at=None,
        checked_in_at=None,
        in_service_at=start,
        completed_at=None,
        no_show_at=None,
        created_at=start,
        updated_at=start,
    )
    repo.bookings[booking.booking_id] = booking
    asyncio.run(service.replace_booking_reminder_plan(booking=booking))
    completed = asyncio.run(orchestrator.complete_booking(booking_id=booking.booking_id))
    assert isinstance(completed, OrchestrationSuccess)
    completed_jobs = asyncio.run(service.list_booking_reminders(booking_id=booking.booking_id))
    assert all(job.status == "canceled" for job in completed_jobs if job.scheduled_for > datetime.now(timezone.utc))

    booking2 = Booking(**{**asdict(booking), "booking_id": "b_noshow", "status": "confirmed", "in_service_at": None})
    repo.bookings[booking2.booking_id] = booking2
    asyncio.run(service.replace_booking_reminder_plan(booking=booking2))
    no_show = asyncio.run(orchestrator.mark_booking_no_show(booking_id=booking2.booking_id))
    assert isinstance(no_show, OrchestrationSuccess)
    no_show_jobs = asyncio.run(service.list_booking_reminders(booking_id=booking2.booking_id))
    assert all(job.status == "canceled" for job in no_show_jobs if job.scheduled_for > datetime.now(timezone.utc))
