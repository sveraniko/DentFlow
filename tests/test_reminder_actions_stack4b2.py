from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from app.application.booking.orchestration_outcomes import InvalidStateOutcome, OrchestrationSuccess
from app.application.communication.actions import ReminderActionService
from app.application.communication.delivery import render_booking_reminder_message
from app.domain.booking import Booking
from app.domain.communication import ReminderJob


class _ReminderRepo:
    def __init__(self, reminders: list[ReminderJob], *, valid_message_id: str = "777") -> None:
        self.reminders = {row.reminder_id: row for row in reminders}
        self.valid_message_id = valid_message_id

    async def get_reminder(self, *, reminder_id: str) -> ReminderJob | None:
        return self.reminders.get(reminder_id)

    async def mark_reminder_acknowledged(self, *, reminder_id: str, acknowledged_at: datetime) -> bool:
        current = self.reminders.get(reminder_id)
        if current is None or current.status != "sent":
            return False
        self.reminders[reminder_id] = ReminderJob(
            **{**asdict(current), "status": "acknowledged", "acknowledged_at": acknowledged_at, "updated_at": acknowledged_at}
        )
        return True

    async def has_sent_delivery_for_provider_message(self, *, reminder_id: str, provider_message_id: str) -> bool:
        return provider_message_id == self.valid_message_id and reminder_id in self.reminders


class _BookingReader:
    def __init__(self, bookings: list[Booking]) -> None:
        self.bookings = {row.booking_id: row for row in bookings}

    async def get_booking(self, booking_id: str) -> Booking | None:
        return self.bookings.get(booking_id)


class _Orchestration:
    def __init__(self, bookings: _BookingReader) -> None:
        self.bookings = bookings
        self.confirm_calls = 0

    async def confirm_booking(self, *, booking_id: str, reason_code: str | None = None):
        booking = self.bookings.bookings.get(booking_id)
        if booking is None or booking.status != "pending_confirmation":
            return InvalidStateOutcome(kind="invalid_state", reason="booking cannot transition to confirmed")
        self.confirm_calls += 1
        updated = Booking(**{**asdict(booking), "status": "confirmed", "confirmed_at": datetime.now(timezone.utc)})
        self.bookings.bookings[booking_id] = updated
        return OrchestrationSuccess(kind="success", entity=updated)

    async def request_booking_reschedule(self, *, booking_id: str, reason_code: str | None = None):
        booking = self.bookings.bookings.get(booking_id)
        if booking is None or booking.status not in {"pending_confirmation", "confirmed", "checked_in", "in_service"}:
            return InvalidStateOutcome(kind="invalid_state", reason="booking cannot transition to reschedule_requested")
        updated = Booking(**{**asdict(booking), "status": "reschedule_requested"})
        self.bookings.bookings[booking_id] = updated
        return OrchestrationSuccess(kind="success", entity=updated)

    async def cancel_booking(self, *, booking_id: str, reason_code: str | None = None):
        booking = self.bookings.bookings.get(booking_id)
        if booking is None or booking.status in {"completed", "no_show", "canceled"}:
            return InvalidStateOutcome(kind="invalid_state", reason="booking cannot transition to canceled")
        updated = Booking(**{**asdict(booking), "status": "canceled", "canceled_at": datetime.now(timezone.utc)})
        self.bookings.bookings[booking_id] = updated
        return OrchestrationSuccess(kind="success", entity=updated)


def _booking(*, status: str = "pending_confirmation") -> Booking:
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
        scheduled_start_at=now + timedelta(days=1),
        scheduled_end_at=now + timedelta(days=1, minutes=30),
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


def _reminder(*, reminder_type: str, status: str = "sent", booking_id: str | None = "b1", locale: str = "en") -> ReminderJob:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    return ReminderJob(
        reminder_id="rem_1",
        clinic_id="clinic_main",
        patient_id="pat_1",
        booking_id=booking_id,
        care_order_id=None,
        recommendation_id=None,
        reminder_type=reminder_type,
        channel="telegram",
        status=status,
        scheduled_for=now,
        payload_key="booking.reminder.24h",
        locale_at_send_time=locale,
        planning_group="g1",
        supersedes_reminder_id=None,
        created_at=now,
        updated_at=now,
    )


def test_rendering_actions_and_context_for_confirmation_and_ack() -> None:
    booking = _booking(status="pending_confirmation")
    en_message = render_booking_reminder_message(reminder=_reminder(reminder_type="booking_confirmation", locale="en"), booking=booking)
    assert "2026-04-18" in en_message.text
    assert "doctor_1" in en_message.text and "service_consult" in en_message.text and "branch_1" in en_message.text
    assert [row.action for row in en_message.actions] == ["confirm", "reschedule", "cancel"]

    ru_message = render_booking_reminder_message(reminder=_reminder(reminder_type="booking_day_of", locale="ru"), booking=booking)
    assert "Напоминание DentFlow" in ru_message.text
    assert [row.action for row in ru_message.actions] == ["ack"]


def test_acknowledge_marks_reminder_and_duplicate_is_stale() -> None:
    reminder_repo = _ReminderRepo([_reminder(reminder_type="booking_previsit")])
    booking_reader = _BookingReader([_booking(status="confirmed")])
    service = ReminderActionService(
        repository=reminder_repo,
        booking_reader=booking_reader,
        booking_orchestration=_Orchestration(booking_reader),
    )

    first = asyncio.run(service.handle_action(reminder_id="rem_1", action="ack", provider_message_id="777"))
    second = asyncio.run(service.handle_action(reminder_id="rem_1", action="ack", provider_message_id="777"))
    assert first.kind == "accepted"
    assert reminder_repo.reminders["rem_1"].status == "acknowledged"
    assert second.kind == "stale"


def test_confirm_booking_action_acknowledges_and_duplicate_is_safe() -> None:
    reminder_repo = _ReminderRepo([_reminder(reminder_type="booking_confirmation")])
    booking_reader = _BookingReader([_booking(status="pending_confirmation")])
    orchestration = _Orchestration(booking_reader)
    service = ReminderActionService(repository=reminder_repo, booking_reader=booking_reader, booking_orchestration=orchestration)

    first = asyncio.run(service.handle_action(reminder_id="rem_1", action="confirm", provider_message_id="777"))
    second = asyncio.run(service.handle_action(reminder_id="rem_1", action="confirm", provider_message_id="777"))

    assert first.kind == "accepted"
    assert booking_reader.bookings["b1"].status == "confirmed"
    assert reminder_repo.reminders["rem_1"].status == "acknowledged"
    assert second.kind == "stale"
    assert orchestration.confirm_calls == 1


def test_reschedule_and_cancel_actions_use_booking_bridge() -> None:
    reminder_res = _ReminderRepo([_reminder(reminder_type="booking_confirmation", status="sent")])
    bookings_res = _BookingReader([_booking(status="confirmed")])
    service_res = ReminderActionService(
        repository=reminder_res,
        booking_reader=bookings_res,
        booking_orchestration=_Orchestration(bookings_res),
    )
    res_outcome = asyncio.run(service_res.handle_action(reminder_id="rem_1", action="reschedule", provider_message_id="777"))
    assert res_outcome.kind == "accepted"
    assert bookings_res.bookings["b1"].status == "reschedule_requested"
    assert reminder_res.reminders["rem_1"].status == "acknowledged"

    reminder_cancel = _ReminderRepo([_reminder(reminder_type="booking_confirmation", status="sent")])
    bookings_cancel = _BookingReader([_booking(status="confirmed")])
    service_cancel = ReminderActionService(
        repository=reminder_cancel,
        booking_reader=bookings_cancel,
        booking_orchestration=_Orchestration(bookings_cancel),
    )
    cancel_outcome = asyncio.run(service_cancel.handle_action(reminder_id="rem_1", action="cancel", provider_message_id="777"))
    assert cancel_outcome.kind == "accepted"
    assert bookings_cancel.bookings["b1"].status == "canceled"
    assert reminder_cancel.reminders["rem_1"].status == "acknowledged"


def test_invalid_or_stale_integrity_cases_are_safe() -> None:
    bookings = _BookingReader([_booking(status="confirmed")])
    service_missing = ReminderActionService(
        repository=_ReminderRepo([], valid_message_id="777"),
        booking_reader=bookings,
        booking_orchestration=_Orchestration(bookings),
    )
    missing = asyncio.run(service_missing.handle_action(reminder_id="rem_missing", action="ack", provider_message_id="777"))
    assert missing.kind == "invalid" and missing.reason == "reminder_not_found"

    stale_service = ReminderActionService(
        repository=_ReminderRepo([_reminder(reminder_type="booking_previsit", status="failed")]),
        booking_reader=bookings,
        booking_orchestration=_Orchestration(bookings),
    )
    stale = asyncio.run(stale_service.handle_action(reminder_id="rem_1", action="ack", provider_message_id="777"))
    assert stale.kind == "stale"

    mismatch_service = ReminderActionService(
        repository=_ReminderRepo([_reminder(reminder_type="booking_confirmation")]),
        booking_reader=bookings,
        booking_orchestration=_Orchestration(bookings),
    )
    mismatch = asyncio.run(mismatch_service.handle_action(reminder_id="rem_1", action="confirm", provider_message_id="999"))
    assert mismatch.kind == "invalid" and mismatch.reason == "message_mismatch"

    booking_missing_service = ReminderActionService(
        repository=_ReminderRepo([_reminder(reminder_type="booking_confirmation", booking_id="b_missing")]),
        booking_reader=bookings,
        booking_orchestration=_Orchestration(bookings),
    )
    booking_missing = asyncio.run(booking_missing_service.handle_action(reminder_id="rem_1", action="confirm", provider_message_id="777"))
    assert booking_missing.kind == "invalid" and booking_missing.reason == "booking_missing"
