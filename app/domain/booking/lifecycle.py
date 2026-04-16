from __future__ import annotations

from dataclasses import dataclass

from app.domain.booking.models import BOOKING_FINAL_STATUSES

BOOKING_SESSION_STATUSES: tuple[str, ...] = (
    "initiated",
    "in_progress",
    "awaiting_slot_selection",
    "awaiting_contact_confirmation",
    "review_ready",
    "completed",
    "canceled",
    "expired",
    "abandoned",
    "admin_escalated",
)

SLOT_HOLD_STATUSES: tuple[str, ...] = (
    "created",
    "active",
    "released",
    "expired",
    "consumed",
    "canceled",
)

WAITLIST_ENTRY_STATUSES: tuple[str, ...] = (
    "created",
    "active",
    "offered",
    "accepted",
    "declined",
    "expired",
    "fulfilled",
    "canceled",
)


BOOKING_SESSION_TRANSITIONS: dict[str, set[str]] = {
    "initiated": {"in_progress", "canceled", "expired", "abandoned", "admin_escalated"},
    "in_progress": {
        "awaiting_slot_selection",
        "awaiting_contact_confirmation",
        "review_ready",
        "completed",
        "canceled",
        "expired",
        "abandoned",
        "admin_escalated",
    },
    "awaiting_slot_selection": {
        "in_progress",
        "awaiting_contact_confirmation",
        "review_ready",
        "canceled",
        "expired",
        "abandoned",
        "admin_escalated",
    },
    "awaiting_contact_confirmation": {
        "in_progress",
        "awaiting_slot_selection",
        "review_ready",
        "canceled",
        "expired",
        "abandoned",
        "admin_escalated",
    },
    "review_ready": {
        "awaiting_contact_confirmation",
        "awaiting_slot_selection",
        "completed",
        "canceled",
        "expired",
        "abandoned",
        "admin_escalated",
    },
    "completed": set(),
    "canceled": set(),
    "expired": set(),
    "abandoned": set(),
    "admin_escalated": {"in_progress", "completed", "canceled", "expired", "abandoned"},
}

SLOT_HOLD_TRANSITIONS: dict[str, set[str]] = {
    "created": {"active", "released", "expired", "canceled"},
    "active": {"released", "expired", "consumed", "canceled"},
    "released": set(),
    "expired": set(),
    "consumed": set(),
    "canceled": set(),
}

BOOKING_FINAL_TRANSITIONS: dict[str, set[str]] = {
    "pending_confirmation": {"confirmed", "canceled", "no_show"},
    "confirmed": {"reschedule_requested", "checked_in", "no_show", "canceled"},
    "reschedule_requested": {"confirmed", "canceled"},
    "canceled": set(),
    "checked_in": {"in_service"},
    "in_service": {"completed"},
    "completed": set(),
    "no_show": set(),
}

WAITLIST_ENTRY_TRANSITIONS: dict[str, set[str]] = {
    "created": {"active", "canceled", "expired"},
    "active": {"offered", "canceled", "expired"},
    "offered": {"accepted", "declined", "expired", "canceled"},
    "accepted": {"fulfilled", "canceled", "expired"},
    "declined": {"active", "canceled", "expired"},
    "expired": set(),
    "fulfilled": set(),
    "canceled": set(),
}


@dataclass(frozen=True, slots=True)
class TransitionDecision:
    from_status: str
    to_status: str
    is_allowed: bool
    is_noop: bool


def evaluate_transition(*, known_states: tuple[str, ...], transitions: dict[str, set[str]], from_status: str, to_status: str) -> TransitionDecision:
    if from_status not in known_states:
        raise ValueError(f"Unknown current status: {from_status}")
    if to_status not in known_states:
        raise ValueError(f"Unknown target status: {to_status}")
    if from_status == to_status:
        return TransitionDecision(from_status=from_status, to_status=to_status, is_allowed=True, is_noop=True)
    return TransitionDecision(
        from_status=from_status,
        to_status=to_status,
        is_allowed=to_status in transitions[from_status],
        is_noop=False,
    )


def evaluate_booking_session_transition(from_status: str, to_status: str) -> TransitionDecision:
    return evaluate_transition(
        known_states=BOOKING_SESSION_STATUSES,
        transitions=BOOKING_SESSION_TRANSITIONS,
        from_status=from_status,
        to_status=to_status,
    )


def evaluate_slot_hold_transition(from_status: str, to_status: str) -> TransitionDecision:
    return evaluate_transition(
        known_states=SLOT_HOLD_STATUSES,
        transitions=SLOT_HOLD_TRANSITIONS,
        from_status=from_status,
        to_status=to_status,
    )


def evaluate_booking_transition(from_status: str, to_status: str) -> TransitionDecision:
    return evaluate_transition(
        known_states=BOOKING_FINAL_STATUSES,
        transitions=BOOKING_FINAL_TRANSITIONS,
        from_status=from_status,
        to_status=to_status,
    )


def evaluate_waitlist_entry_transition(from_status: str, to_status: str) -> TransitionDecision:
    return evaluate_transition(
        known_states=WAITLIST_ENTRY_STATUSES,
        transitions=WAITLIST_ENTRY_TRANSITIONS,
        from_status=from_status,
        to_status=to_status,
    )
