from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone

import pytest

from app.application.booking.state_services import (
    BookingSessionStateService,
    BookingStateService,
    SlotHoldStateService,
    WaitlistStateService,
)
from app.domain.booking import Booking, BookingSession, SlotHold, WaitlistEntry
from app.domain.booking.errors import (
    InvalidBookingTransitionError,
    InvalidSessionTransitionError,
    InvalidSlotHoldTransitionError,
    InvalidWaitlistTransitionError,
)
from app.domain.booking.lifecycle import (
    BOOKING_SESSION_STATUSES,
    evaluate_booking_session_transition,
    evaluate_booking_transition,
    evaluate_slot_hold_transition,
    evaluate_waitlist_entry_transition,
)


class _FakeTx(AbstractAsyncContextManager):
    def __init__(self, repo: "_FakeTransitionRepo") -> None:
        self.repo = repo
        self._snapshot = None

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

    async def append_session_event(self, event) -> None:
        if self.repo.fail_session_event:
            raise RuntimeError("boom")
        self.repo.session_events.append(event)

    async def upsert_slot_hold(self, item: SlotHold) -> None:
        self.repo.holds[item.slot_hold_id] = item

    async def upsert_booking(self, item: Booking) -> None:
        self.repo.bookings[item.booking_id] = item

    async def append_booking_status_history(self, item) -> None:
        if self.repo.fail_booking_history:
            raise RuntimeError("boom")
        self.repo.history.append(item)

    async def upsert_waitlist_entry(self, item: WaitlistEntry) -> None:
        self.repo.waitlist[item.waitlist_entry_id] = item


class _FakeTransitionRepo:
    def __init__(self) -> None:
        now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
        self.sessions = {
            "s1": BookingSession(
                booking_session_id="s1",
                clinic_id="clinic_main",
                branch_id="branch_central",
                telegram_user_id=3001,
                resolved_patient_id="patient_1",
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
                contact_phone_snapshot=None,
                notes=None,
                expires_at=now,
                created_at=now,
                updated_at=now,
            )
        }
        self.holds = {
            "h1": SlotHold(
                slot_hold_id="h1",
                clinic_id="clinic_main",
                slot_id="slot1",
                booking_session_id="s1",
                telegram_user_id=3001,
                status="created",
                expires_at=now,
                created_at=now,
            )
        }
        self.bookings = {
            "b1": Booking(
                booking_id="b1",
                clinic_id="clinic_main",
                branch_id="branch_central",
                patient_id="patient_1",
                doctor_id="doctor_1",
                service_id="service_consult",
                slot_id="slot1",
                booking_mode="patient_bot",
                source_channel="telegram",
                scheduled_start_at=now,
                scheduled_end_at=now.replace(minute=30),
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
        }
        self.waitlist = {
            "w1": WaitlistEntry(
                waitlist_entry_id="w1",
                clinic_id="clinic_main",
                branch_id="branch_central",
                patient_id="patient_2",
                telegram_user_id=3002,
                service_id="service_consult",
                doctor_id="doctor_1",
                date_window={"from": "2026-04-21", "to": "2026-04-22"},
                time_window="morning",
                priority=1,
                status="active",
                source_session_id="s1",
                notes=None,
                created_at=now,
                updated_at=now,
            )
        }
        self.history = []
        self.session_events = []
        self.fail_booking_history = False
        self.fail_session_event = False

    def snapshot(self):
        return {
            "sessions": dict(self.sessions),
            "holds": dict(self.holds),
            "bookings": dict(self.bookings),
            "waitlist": dict(self.waitlist),
            "history": list(self.history),
            "session_events": list(self.session_events),
        }

    def restore(self, snapshot):
        self.sessions = snapshot["sessions"]
        self.holds = snapshot["holds"]
        self.bookings = snapshot["bookings"]
        self.waitlist = snapshot["waitlist"]
        self.history = snapshot["history"]
        self.session_events = snapshot["session_events"]

    def transaction(self):
        return _FakeTx(self)

    async def get_booking_session(self, booking_session_id: str):
        return self.sessions.get(booking_session_id)

    async def get_slot_hold(self, slot_hold_id: str):
        return self.holds.get(slot_hold_id)

    async def get_booking(self, booking_id: str):
        return self.bookings.get(booking_id)

    async def get_waitlist_entry(self, waitlist_entry_id: str):
        return self.waitlist.get(waitlist_entry_id)


def test_booking_session_transition_rules_and_noop() -> None:
    allowed = evaluate_booking_session_transition("in_progress", "awaiting_slot_selection")
    assert allowed.is_allowed and not allowed.is_noop

    forbidden = evaluate_booking_session_transition("completed", "in_progress")
    assert not forbidden.is_allowed and not forbidden.is_noop

    noop = evaluate_booking_session_transition("review_ready", "review_ready")
    assert noop.is_allowed and noop.is_noop

    assert "active" not in BOOKING_SESSION_STATUSES


def test_slot_hold_transition_rules() -> None:
    assert evaluate_slot_hold_transition("created", "active").is_allowed
    assert not evaluate_slot_hold_transition("expired", "active").is_allowed


def test_booking_transition_rules_cover_required_matrix() -> None:
    allowed_pairs = [
        ("pending_confirmation", "confirmed"),
        ("pending_confirmation", "canceled"),
        ("pending_confirmation", "no_show"),
        ("confirmed", "reschedule_requested"),
        ("reschedule_requested", "confirmed"),
        ("reschedule_requested", "canceled"),
        ("confirmed", "checked_in"),
        ("checked_in", "in_service"),
        ("in_service", "completed"),
        ("confirmed", "no_show"),
    ]
    for source, target in allowed_pairs:
        assert evaluate_booking_transition(source, target).is_allowed

    forbidden_pairs = [
        ("canceled", "checked_in"),
        ("no_show", "in_service"),
        ("completed", "confirmed"),
        ("completed", "pending_confirmation"),
    ]
    for source, target in forbidden_pairs:
        assert not evaluate_booking_transition(source, target).is_allowed


def test_waitlist_transition_rules_subset() -> None:
    assert evaluate_waitlist_entry_transition("active", "offered").is_allowed
    assert evaluate_waitlist_entry_transition("offered", "accepted").is_allowed
    assert not evaluate_waitlist_entry_transition("fulfilled", "active").is_allowed


def test_session_state_service_noop_does_not_emit_event() -> None:
    repo = _FakeTransitionRepo()
    service = BookingSessionStateService(repo)

    result = asyncio.run(service.transition_session(booking_session_id="s1", to_status="in_progress"))

    assert not result.changed
    assert len(repo.session_events) == 0


def test_services_raise_typed_transition_errors() -> None:
    repo = _FakeTransitionRepo()

    with pytest.raises(InvalidSessionTransitionError):
        asyncio.run(BookingSessionStateService(repo).transition_session(booking_session_id="s1", to_status="initiated"))

    with pytest.raises(InvalidSlotHoldTransitionError):
        asyncio.run(SlotHoldStateService(repo).transition_hold(slot_hold_id="h1", to_status="consumed"))

    with pytest.raises(InvalidBookingTransitionError):
        asyncio.run(BookingStateService(repo).transition_booking(booking_id="b1", to_status="in_service"))

    with pytest.raises(InvalidWaitlistTransitionError):
        asyncio.run(WaitlistStateService(repo).transition_waitlist_entry(waitlist_entry_id="w1", to_status="fulfilled"))


def test_booking_transition_is_atomic_for_booking_and_history() -> None:
    repo = _FakeTransitionRepo()
    repo.fail_booking_history = True
    service = BookingStateService(repo)

    with pytest.raises(RuntimeError):
        asyncio.run(service.transition_booking(booking_id="b1", to_status="confirmed"))

    assert repo.bookings["b1"].status == "pending_confirmation"
    assert repo.history == []


def test_session_transition_is_atomic_for_session_and_event() -> None:
    repo = _FakeTransitionRepo()
    repo.fail_session_event = True
    service = BookingSessionStateService(repo)

    with pytest.raises(RuntimeError):
        asyncio.run(service.transition_session(booking_session_id="s1", to_status="awaiting_slot_selection"))

    assert repo.sessions["s1"].status == "in_progress"
    assert repo.session_events == []


def test_booking_state_service_sets_timestamps() -> None:
    repo = _FakeTransitionRepo()
    service = BookingStateService(repo)
    t1 = datetime(2026, 4, 20, 9, 1, tzinfo=timezone.utc)
    confirmed = asyncio.run(service.transition_booking(booking_id="b1", to_status="confirmed", occurred_at=t1))
    assert confirmed.entity.confirmed_at == t1

    repo.bookings["b1"] = confirmed.entity
    checked_in = asyncio.run(
        service.transition_booking(
            booking_id="b1",
            to_status="checked_in",
            occurred_at=datetime(2026, 4, 20, 9, 2, tzinfo=timezone.utc),
        )
    )
    assert checked_in.entity.checked_in_at is not None
