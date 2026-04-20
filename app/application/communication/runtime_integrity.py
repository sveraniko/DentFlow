from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.booking import Booking
from app.domain.communication import ReminderJob

REMINDER_TERMINAL_STATES = frozenset({"sent", "acknowledged", "failed", "canceled", "expired"})

_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "scheduled": frozenset({"queued", "canceled", "expired"}),
    "queued": frozenset({"scheduled", "sent", "failed", "canceled", "expired"}),
    "sent": frozenset({"acknowledged", "expired"}),
    "acknowledged": frozenset(),
    "failed": frozenset({"scheduled"}),
    "canceled": frozenset(),
    "expired": frozenset(),
}


@dataclass(frozen=True, slots=True)
class ReminderRelevanceDecision:
    should_send: bool
    terminal_status: str | None = None
    reason_code: str | None = None


def can_transition(*, from_status: str, to_status: str) -> bool:
    return to_status in _ALLOWED_TRANSITIONS.get(from_status, frozenset())


def evaluate_booking_relevance(*, reminder: ReminderJob, booking: Booking | None, now: datetime) -> ReminderRelevanceDecision:
    if reminder.booking_id is None:
        return ReminderRelevanceDecision(should_send=True)

    if booking is None:
        return ReminderRelevanceDecision(False, "canceled", "booking_missing")

    if booking.status in {"canceled", "completed", "no_show"}:
        return ReminderRelevanceDecision(False, "canceled", f"booking_{booking.status}")

    if booking.status == "reschedule_requested":
        return ReminderRelevanceDecision(False, "canceled", "booking_reschedule_requested")

    if reminder.reminder_type == "booking_confirmation" and booking.status == "confirmed":
        return ReminderRelevanceDecision(False, "canceled", "booking_already_confirmed")

    if booking.scheduled_start_at <= now:
        return ReminderRelevanceDecision(False, "expired", "booking_window_passed")

    return ReminderRelevanceDecision(should_send=True)
