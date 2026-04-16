from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class ReminderJob:
    reminder_id: str
    clinic_id: str
    patient_id: str
    booking_id: str | None
    care_order_id: str | None
    recommendation_id: str | None
    reminder_type: str
    channel: str
    status: str
    scheduled_for: datetime
    payload_key: str
    locale_at_send_time: str | None
    planning_group: str | None
    supersedes_reminder_id: str | None
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None = None
    acknowledged_at: datetime | None = None
    canceled_at: datetime | None = None
    cancel_reason_code: str | None = None


@dataclass(slots=True, frozen=True)
class MessageDelivery:
    message_delivery_id: str
    reminder_id: str | None
    patient_id: str
    channel: str
    delivery_status: str
    provider_message_id: str | None
    attempt_no: int
    error_text: str | None
    created_at: datetime
