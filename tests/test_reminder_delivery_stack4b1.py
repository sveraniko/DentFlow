from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from app.application.communication import (
    RecipientResolution,
    ReminderDeliveryService,
    ReminderSendResult,
    TelegramDeliveryTarget,
)
from app.domain.booking import Booking
from app.domain.communication import MessageDelivery, ReminderJob


class _ReminderRepo:
    def __init__(self, jobs: list[ReminderJob]) -> None:
        self.jobs = {job.reminder_id: job for job in jobs}
        self.message_deliveries: list[MessageDelivery] = []

    async def claim_due_reminders(self, *, now: datetime, limit: int) -> list[ReminderJob]:
        due = sorted(
            [
                job
                for job in self.jobs.values()
                if job.status == "scheduled" and job.scheduled_for <= now
            ],
            key=lambda row: row.scheduled_for,
        )[:limit]
        claimed: list[ReminderJob] = []
        for job in due:
            updated = ReminderJob(**{**asdict(job), "status": "queued", "updated_at": now})
            self.jobs[job.reminder_id] = updated
            claimed.append(updated)
        return claimed

    async def create_message_delivery(self, item: MessageDelivery) -> None:
        self.message_deliveries.append(item)

    async def mark_reminder_sent(self, *, reminder_id: str, sent_at: datetime) -> bool:
        current = self.jobs[reminder_id]
        if current.status != "queued":
            return False
        self.jobs[reminder_id] = ReminderJob(**{**asdict(current), "status": "sent", "updated_at": sent_at, "sent_at": sent_at})
        return True

    async def mark_reminder_failed(self, *, reminder_id: str, failed_at: datetime, error_text: str) -> bool:
        current = self.jobs[reminder_id]
        if current.status != "queued":
            return False
        self.jobs[reminder_id] = ReminderJob(**{**asdict(current), "status": "failed", "updated_at": failed_at})
        return True

    async def mark_reminder_canceled(self, *, reminder_id: str, canceled_at: datetime, reason_code: str) -> bool:
        current = self.jobs[reminder_id]
        if current.status != "queued":
            return False
        self.jobs[reminder_id] = ReminderJob(
            **{
                **asdict(current),
                "status": "canceled",
                "updated_at": canceled_at,
                "canceled_at": canceled_at,
                "cancel_reason_code": reason_code,
            }
        )
        return True

    async def next_delivery_attempt_no(self, *, reminder_id: str) -> int:
        return 1 + len([row for row in self.message_deliveries if row.reminder_id == reminder_id])


class _BookingReader:
    def __init__(self, bookings: list[Booking]) -> None:
        self.bookings = {row.booking_id: row for row in bookings}

    async def get_booking(self, booking_id: str) -> Booking | None:
        return self.bookings.get(booking_id)


class _Resolver:
    def __init__(self, targets: dict[str, RecipientResolution]) -> None:
        self.targets = targets

    async def resolve(self, *, reminder: ReminderJob) -> RecipientResolution:
        return self.targets.get(reminder.patient_id, RecipientResolution(kind="no_target", reason_code="telegram_target_missing"))


class _Sender:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[int, str, tuple[str, ...]]] = []

    async def send_reminder(self, *, target: TelegramDeliveryTarget, text: str, actions) -> ReminderSendResult:
        if self.fail:
            raise RuntimeError("telegram_send_failed")
        self.sent.append((target.telegram_user_id, text, tuple(action.action for action in actions)))
        return ReminderSendResult(provider_message_id="777")


def _job(*, reminder_id: str, patient_id: str, channel: str = "telegram", booking_id: str | None = "b1", status: str = "scheduled", locale: str = "en", reminder_type: str = "booking_previsit", scheduled_for: datetime | None = None) -> ReminderJob:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    return ReminderJob(
        reminder_id=reminder_id,
        clinic_id="clinic_main",
        patient_id=patient_id,
        booking_id=booking_id,
        care_order_id=None,
        recommendation_id=None,
        reminder_type=reminder_type,
        channel=channel,
        status=status,
        scheduled_for=scheduled_for or (now - timedelta(minutes=1)),
        payload_key="booking.reminder.24h",
        locale_at_send_time=locale,
        planning_group="g1",
        supersedes_reminder_id=None,
        created_at=now,
        updated_at=now,
    )


def _booking(status: str = "confirmed") -> Booking:
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


def test_claiming_moves_due_scheduled_to_queued() -> None:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    repo = _ReminderRepo([_job(reminder_id="r1", patient_id="pat_1"), _job(reminder_id="r2", patient_id="pat_2", scheduled_for=now + timedelta(hours=1))])
    claimed = asyncio.run(repo.claim_due_reminders(now=now, limit=10))
    assert [row.reminder_id for row in claimed] == ["r1"]
    assert repo.jobs["r1"].status == "queued"
    assert repo.jobs["r2"].status == "scheduled"
    claimed_again = asyncio.run(repo.claim_due_reminders(now=now, limit=10))
    assert claimed_again == []


def test_delivery_success_persists_message_and_marks_sent() -> None:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    reminder = _job(reminder_id="r1", patient_id="pat_1", locale="en", reminder_type="booking_confirmation")
    repo = _ReminderRepo([reminder])
    service = ReminderDeliveryService(
        repository=repo,
        booking_reader=_BookingReader([_booking("confirmed")]),
        recipient_resolver=_Resolver({"pat_1": RecipientResolution(kind="target_found", target=TelegramDeliveryTarget(patient_id="pat_1", telegram_user_id=3001))}),
        sender=_Sender(),
    )
    processed = asyncio.run(service.deliver_due_reminders(now=now, batch_limit=10))
    assert processed == 1
    assert repo.jobs["r1"].status == "sent"
    assert repo.message_deliveries and repo.message_deliveries[0].delivery_status == "sent"
    assert repo.message_deliveries[0].provider_message_id == "777"
    assert service.sender.sent[0][2] == ("confirm", "reschedule", "cancel")


def test_delivery_failure_persists_message_and_marks_failed() -> None:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    reminder = _job(reminder_id="r1", patient_id="pat_1")
    repo = _ReminderRepo([reminder])
    service = ReminderDeliveryService(
        repository=repo,
        booking_reader=_BookingReader([_booking("confirmed")]),
        recipient_resolver=_Resolver({"pat_1": RecipientResolution(kind="target_found", target=TelegramDeliveryTarget(patient_id="pat_1", telegram_user_id=3001))}),
        sender=_Sender(fail=True),
    )
    asyncio.run(service.deliver_due_reminders(now=now, batch_limit=10))
    assert repo.jobs["r1"].status == "failed"
    assert repo.message_deliveries[0].delivery_status == "failed"
    assert "telegram_send_failed" in (repo.message_deliveries[0].error_text or "")


def test_unsupported_channel_fails_explicitly_without_crash() -> None:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    repo = _ReminderRepo([_job(reminder_id="r1", patient_id="pat_1", channel="sms")])
    service = ReminderDeliveryService(
        repository=repo,
        booking_reader=_BookingReader([_booking("confirmed")]),
        recipient_resolver=_Resolver({}),
        sender=_Sender(),
    )
    asyncio.run(service.deliver_due_reminders(now=now, batch_limit=10))
    assert repo.jobs["r1"].status == "failed"
    assert repo.message_deliveries[0].error_text == "unsupported_channel"


def test_missing_or_invalid_telegram_target_fails_explicitly() -> None:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    repo = _ReminderRepo([_job(reminder_id="r1", patient_id="pat_missing"), _job(reminder_id="r2", patient_id="pat_invalid")])
    service = ReminderDeliveryService(
        repository=repo,
        booking_reader=_BookingReader([_booking("confirmed")]),
        recipient_resolver=_Resolver(
            {
                "pat_missing": RecipientResolution(kind="no_target", reason_code="telegram_target_missing"),
                "pat_invalid": RecipientResolution(kind="invalid_target", reason_code="telegram_target_invalid"),
            }
        ),
        sender=_Sender(),
    )
    asyncio.run(service.deliver_due_reminders(now=now, batch_limit=10))
    assert repo.jobs["r1"].status == "failed"
    assert repo.jobs["r2"].status == "failed"
    assert {d.error_text for d in repo.message_deliveries} == {"telegram_target_missing", "telegram_target_invalid"}


def test_booking_sanity_cancels_send_for_terminal_or_missing_booking() -> None:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    repo = _ReminderRepo(
        [
            _job(reminder_id="r_cancel", patient_id="pat_1", booking_id="b1"),
            _job(reminder_id="r_missing", patient_id="pat_1", booking_id="b_missing"),
        ]
    )
    service = ReminderDeliveryService(
        repository=repo,
        booking_reader=_BookingReader([_booking("canceled")]),
        recipient_resolver=_Resolver({"pat_1": RecipientResolution(kind="target_found", target=TelegramDeliveryTarget(patient_id="pat_1", telegram_user_id=3001))}),
        sender=_Sender(),
    )
    asyncio.run(service.deliver_due_reminders(now=now, batch_limit=10))
    assert repo.jobs["r_cancel"].status == "canceled"
    assert repo.jobs["r_missing"].status == "canceled"
    assert {row.delivery_status for row in repo.message_deliveries} == {"canceled"}
