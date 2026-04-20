from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.application.communication.runtime_integrity import can_transition, evaluate_booking_relevance
from app.domain.booking import Booking
from app.domain.communication import ReminderJob


def _booking(*, status: str = "confirmed", start_delta_hours: int = 24) -> Booking:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    return Booking(
        booking_id="b1",
        clinic_id="clinic_main",
        branch_id="branch_1",
        patient_id="pat_1",
        doctor_id="doctor_1",
        service_id="service_consult",
        slot_id="slot_1",
        booking_mode="patient_bot",
        source_channel="telegram",
        scheduled_start_at=now + timedelta(hours=start_delta_hours),
        scheduled_end_at=now + timedelta(hours=start_delta_hours, minutes=30),
        status=status,
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


def _reminder(*, reminder_type: str = "booking_previsit") -> ReminderJob:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    return ReminderJob(
        reminder_id="r1",
        clinic_id="clinic_main",
        patient_id="pat_1",
        booking_id="b1",
        care_order_id=None,
        recommendation_id=None,
        reminder_type=reminder_type,
        channel="telegram",
        status="queued",
        scheduled_for=now - timedelta(minutes=5),
        payload_key="booking.reminder.24h",
        locale_at_send_time="en",
        planning_group="g1",
        supersedes_reminder_id=None,
        created_at=now,
        updated_at=now,
        queued_at=now,
    )


def test_reminder_transition_rules_are_explicit() -> None:
    assert can_transition(from_status="scheduled", to_status="queued")
    assert can_transition(from_status="queued", to_status="sent")
    assert can_transition(from_status="queued", to_status="failed")
    assert can_transition(from_status="sent", to_status="acknowledged")

    assert not can_transition(from_status="scheduled", to_status="acknowledged")
    assert not can_transition(from_status="acknowledged", to_status="scheduled")
    assert not can_transition(from_status="canceled", to_status="queued")


def test_booking_relevance_revalidation_decisions() -> None:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)

    missing = evaluate_booking_relevance(reminder=_reminder(), booking=None, now=now)
    assert not missing.should_send and missing.terminal_status == "canceled" and missing.reason_code == "booking_missing"

    rescheduled = evaluate_booking_relevance(reminder=_reminder(), booking=_booking(status="reschedule_requested"), now=now)
    assert not rescheduled.should_send and rescheduled.reason_code == "booking_reschedule_requested"

    expired = evaluate_booking_relevance(reminder=_reminder(), booking=_booking(status="confirmed", start_delta_hours=-1), now=now)
    assert not expired.should_send and expired.terminal_status == "expired" and expired.reason_code == "booking_window_passed"

    already_confirmed = evaluate_booking_relevance(
        reminder=_reminder(reminder_type="booking_confirmation"),
        booking=_booking(status="confirmed"),
        now=now,
    )
    assert not already_confirmed.should_send and already_confirmed.reason_code == "booking_already_confirmed"

    active = evaluate_booking_relevance(reminder=_reminder(), booking=_booking(status="pending_confirmation"), now=now)
    assert active.should_send
