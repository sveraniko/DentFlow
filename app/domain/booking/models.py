from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

BOOKING_FINAL_STATUSES: tuple[str, ...] = (
    "pending_confirmation",
    "confirmed",
    "reschedule_requested",
    "canceled",
    "checked_in",
    "in_service",
    "completed",
    "no_show",
)


@dataclass(slots=True, frozen=True)
class BookingSession:
    booking_session_id: str
    clinic_id: str
    telegram_user_id: int
    status: str
    route_type: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    branch_id: str | None = None
    resolved_patient_id: str | None = None
    service_id: str | None = None
    urgency_type: str | None = None
    requested_date_type: str | None = None
    requested_date: date | None = None
    time_window: str | None = None
    doctor_preference_type: str | None = None
    doctor_id: str | None = None
    doctor_code_raw: str | None = None
    selected_slot_id: str | None = None
    selected_hold_id: str | None = None
    contact_phone_snapshot: str | None = None
    notes: str | None = None


@dataclass(slots=True, frozen=True)
class SessionEvent:
    session_event_id: str
    booking_session_id: str
    event_name: str
    occurred_at: datetime
    payload_json: dict[str, object] | None = None
    actor_type: str | None = None
    actor_id: str | None = None


@dataclass(slots=True, frozen=True)
class AvailabilitySlot:
    slot_id: str
    clinic_id: str
    doctor_id: str
    start_at: datetime
    end_at: datetime
    status: str
    visibility_policy: str
    updated_at: datetime
    branch_id: str | None = None
    service_scope: dict[str, object] | None = None
    source_ref: str | None = None


@dataclass(slots=True, frozen=True)
class SlotHold:
    slot_hold_id: str
    clinic_id: str
    slot_id: str
    booking_session_id: str
    telegram_user_id: int
    status: str
    expires_at: datetime
    created_at: datetime


@dataclass(slots=True, frozen=True)
class Booking:
    booking_id: str
    clinic_id: str
    patient_id: str
    doctor_id: str
    service_id: str
    booking_mode: str
    source_channel: str
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    status: str
    confirmation_required: bool
    created_at: datetime
    updated_at: datetime
    branch_id: str | None = None
    slot_id: str | None = None
    reason_for_visit_short: str | None = None
    patient_note: str | None = None
    confirmed_at: datetime | None = None
    canceled_at: datetime | None = None
    checked_in_at: datetime | None = None
    in_service_at: datetime | None = None
    completed_at: datetime | None = None
    no_show_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class BookingStatusHistory:
    booking_status_history_id: str
    booking_id: str
    new_status: str
    occurred_at: datetime
    old_status: str | None = None
    reason_code: str | None = None
    actor_type: str | None = None
    actor_id: str | None = None


@dataclass(slots=True, frozen=True)
class WaitlistEntry:
    waitlist_entry_id: str
    clinic_id: str
    service_id: str
    priority: int
    status: str
    created_at: datetime
    updated_at: datetime
    branch_id: str | None = None
    patient_id: str | None = None
    telegram_user_id: int | None = None
    doctor_id: str | None = None
    date_window: dict[str, object] | None = None
    time_window: str | None = None
    source_session_id: str | None = None
    notes: str | None = None


@dataclass(slots=True, frozen=True)
class AdminEscalation:
    admin_escalation_id: str
    clinic_id: str
    booking_session_id: str
    reason_code: str
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    patient_id: str | None = None
    assigned_to_actor_id: str | None = None
    payload_summary: dict[str, object] | None = None
