from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from app.application.booking.orchestration_outcomes import InvalidStateOutcome, OrchestrationSuccess
from app.application.communication.actions import ReminderActionService
from app.application.communication.delivery import render_booking_reminder_message
from app.domain.booking import Booking
from app.domain.communication import ReminderJob


class _MemoryTx(AbstractAsyncContextManager):
    def __init__(self, repo: "_TxRepository") -> None:
        self.repo = repo
        self._snapshot_reminders: dict[str, ReminderJob] = {}
        self._snapshot_bookings: dict[str, Booking] = {}

    async def __aenter__(self):
        self._snapshot_reminders = dict(self.repo.reminders)
        self._snapshot_bookings = dict(self.repo.bookings)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.repo.reminders = self._snapshot_reminders
            self.repo.bookings = self._snapshot_bookings
        return False

    async def get_reminder_for_update_in_transaction(self, *, reminder_id: str) -> ReminderJob | None:
        return self.repo.reminders.get(reminder_id)

    async def mark_reminder_acknowledged_in_transaction(self, *, reminder_id: str, acknowledged_at: datetime) -> bool:
        if self.repo.fail_ack:
            raise RuntimeError("ack write failed")
        current = self.repo.reminders.get(reminder_id)
        if current is None or current.status != "sent":
            return False
        self.repo.reminders[reminder_id] = ReminderJob(
            **{**asdict(current), "status": "acknowledged", "acknowledged_at": acknowledged_at, "updated_at": acknowledged_at}
        )
        return True

    async def has_sent_delivery_for_provider_message_in_transaction(self, *, reminder_id: str, provider_message_id: str) -> bool:
        return provider_message_id == self.repo.valid_message_id and reminder_id in self.repo.reminders

    async def get_booking_for_update(self, booking_id: str) -> Booking | None:
        return self.repo.bookings.get(booking_id)


class _TxRepository:
    def __init__(
        self,
        reminders: list[ReminderJob],
        bookings: list[Booking],
        *,
        valid_message_id: str = "777",
        fail_ack: bool = False,
    ) -> None:
        self.reminders = {row.reminder_id: row for row in reminders}
        self.bookings = {row.booking_id: row for row in bookings}
        self.valid_message_id = valid_message_id
        self.fail_ack = fail_ack

    def transaction(self) -> _MemoryTx:
        return _MemoryTx(self)

    async def get_reminder(self, *, reminder_id: str) -> ReminderJob | None:
        return self.reminders.get(reminder_id)

    async def mark_reminder_acknowledged(self, *, reminder_id: str, acknowledged_at: datetime) -> bool:
        return await self.transaction().mark_reminder_acknowledged_in_transaction(reminder_id=reminder_id, acknowledged_at=acknowledged_at)

    async def has_sent_delivery_for_provider_message(self, *, reminder_id: str, provider_message_id: str) -> bool:
        return provider_message_id == self.valid_message_id and reminder_id in self.reminders


class _Orchestration:
    def __init__(self) -> None:
        self.confirm_calls = 0
        self.cancel_calls = 0
        self.reschedule_calls = 0

    async def confirm_booking_in_transaction(self, *, tx: _MemoryTx, booking_id: str, reason_code: str | None = None):
        booking = await tx.get_booking_for_update(booking_id)
        if booking is None or booking.status != "pending_confirmation":
            return InvalidStateOutcome(kind="invalid_state", reason="booking cannot transition to confirmed")
        self.confirm_calls += 1
        tx.repo.bookings[booking_id] = Booking(**{**asdict(booking), "status": "confirmed", "confirmed_at": datetime.now(timezone.utc)})
        return OrchestrationSuccess(kind="success", entity=tx.repo.bookings[booking_id])

    async def request_booking_reschedule_in_transaction(self, *, tx: _MemoryTx, booking_id: str, reason_code: str | None = None):
        booking = await tx.get_booking_for_update(booking_id)
        if booking is None or booking.status in {"completed", "no_show", "canceled"}:
            return InvalidStateOutcome(kind="invalid_state", reason="booking cannot transition to reschedule_requested")
        self.reschedule_calls += 1
        tx.repo.bookings[booking_id] = Booking(**{**asdict(booking), "status": "reschedule_requested"})
        return OrchestrationSuccess(kind="success", entity=tx.repo.bookings[booking_id])

    async def cancel_booking_in_transaction(self, *, tx: _MemoryTx, booking_id: str, reason_code: str | None = None):
        booking = await tx.get_booking_for_update(booking_id)
        if booking is None or booking.status in {"completed", "no_show", "canceled"}:
            return InvalidStateOutcome(kind="invalid_state", reason="booking cannot transition to canceled")
        self.cancel_calls += 1
        tx.repo.bookings[booking_id] = Booking(**{**asdict(booking), "status": "canceled", "canceled_at": datetime.now(timezone.utc)})
        return OrchestrationSuccess(kind="success", entity=tx.repo.bookings[booking_id])


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


def _service(repo: _TxRepository, orchestration: _Orchestration | None = None) -> ReminderActionService:
    return ReminderActionService(
        repository=repo,
        transaction_repository=repo,
        booking_orchestration=orchestration or _Orchestration(),
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
    repo = _TxRepository([_reminder(reminder_type="booking_previsit")], [_booking(status="confirmed")])
    service = _service(repo)

    first = asyncio.run(service.handle_action(reminder_id="rem_1", action="ack", provider_message_id="777"))
    second = asyncio.run(service.handle_action(reminder_id="rem_1", action="ack", provider_message_id="777"))
    assert first.kind == "accepted"
    assert repo.reminders["rem_1"].status == "acknowledged"
    assert second.kind == "stale"


def test_confirm_booking_action_acknowledges_and_duplicate_is_safe() -> None:
    repo = _TxRepository([_reminder(reminder_type="booking_confirmation")], [_booking(status="pending_confirmation")])
    orchestration = _Orchestration()
    service = _service(repo, orchestration)

    first = asyncio.run(service.handle_action(reminder_id="rem_1", action="confirm", provider_message_id="777"))
    second = asyncio.run(service.handle_action(reminder_id="rem_1", action="confirm", provider_message_id="777"))

    assert first.kind == "accepted"
    assert repo.bookings["b1"].status == "confirmed"
    assert repo.reminders["rem_1"].status == "acknowledged"
    assert second.kind == "stale"
    assert orchestration.confirm_calls == 1


def test_reschedule_and_cancel_actions_use_booking_bridge() -> None:
    repo_res = _TxRepository([_reminder(reminder_type="booking_confirmation", status="sent")], [_booking(status="confirmed")])
    orchestration_res = _Orchestration()
    service_res = _service(repo_res, orchestration_res)
    res_outcome = asyncio.run(service_res.handle_action(reminder_id="rem_1", action="reschedule", provider_message_id="777"))
    assert res_outcome.kind == "accepted"
    assert repo_res.bookings["b1"].status == "reschedule_requested"
    assert repo_res.reminders["rem_1"].status == "acknowledged"
    assert orchestration_res.reschedule_calls == 1

    repo_cancel = _TxRepository([_reminder(reminder_type="booking_confirmation", status="sent")], [_booking(status="confirmed")])
    orchestration_cancel = _Orchestration()
    service_cancel = _service(repo_cancel, orchestration_cancel)
    cancel_outcome = asyncio.run(service_cancel.handle_action(reminder_id="rem_1", action="cancel", provider_message_id="777"))
    assert cancel_outcome.kind == "accepted"
    assert repo_cancel.bookings["b1"].status == "canceled"
    assert repo_cancel.reminders["rem_1"].status == "acknowledged"
    assert orchestration_cancel.cancel_calls == 1


def test_atomicity_rolls_back_booking_when_ack_write_fails() -> None:
    repo = _TxRepository(
        [_reminder(reminder_type="booking_confirmation", status="sent")],
        [_booking(status="pending_confirmation")],
        fail_ack=True,
    )
    service = _service(repo, _Orchestration())

    try:
        asyncio.run(service.handle_action(reminder_id="rem_1", action="confirm", provider_message_id="777"))
    except RuntimeError as exc:
        assert str(exc) == "ack write failed"
    else:
        raise AssertionError("expected ack write failure")

    assert repo.bookings["b1"].status == "pending_confirmation"
    assert repo.reminders["rem_1"].status == "sent"


def test_invalid_or_stale_integrity_cases_are_safe() -> None:
    repo_with_booking = _TxRepository([_reminder(reminder_type="booking_confirmation")], [_booking(status="confirmed")])

    service_missing = _service(_TxRepository([], [_booking(status="confirmed")]))
    missing = asyncio.run(service_missing.handle_action(reminder_id="rem_missing", action="ack", provider_message_id="777"))
    assert missing.kind == "invalid" and missing.reason == "reminder_not_found"

    stale_service = _service(_TxRepository([_reminder(reminder_type="booking_previsit", status="failed")], [_booking(status="confirmed")]))
    stale = asyncio.run(stale_service.handle_action(reminder_id="rem_1", action="ack", provider_message_id="777"))
    assert stale.kind == "stale"

    mismatch_service = _service(repo_with_booking)
    mismatch = asyncio.run(mismatch_service.handle_action(reminder_id="rem_1", action="confirm", provider_message_id="999"))
    assert mismatch.kind == "invalid" and mismatch.reason == "message_mismatch"

    booking_missing_service = _service(_TxRepository([_reminder(reminder_type="booking_confirmation", booking_id="b_missing")], [_booking(status="confirmed")]))
    booking_missing = asyncio.run(booking_missing_service.handle_action(reminder_id="rem_1", action="confirm", provider_message_id="777"))
    assert booking_missing.kind == "invalid" and booking_missing.reason == "booking_missing"
