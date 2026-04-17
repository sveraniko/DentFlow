from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from app.domain.booking import Booking
from app.domain.communication import MessageDelivery, ReminderJob


@dataclass(slots=True, frozen=True)
class TelegramDeliveryTarget:
    patient_id: str
    telegram_user_id: int


@dataclass(slots=True, frozen=True)
class RecipientResolution:
    kind: str
    target: TelegramDeliveryTarget | None = None
    reason_code: str | None = None


@dataclass(slots=True, frozen=True)
class ReminderSendResult:
    provider_message_id: str | None


class ReminderDeliveryRepository(Protocol):
    async def claim_due_reminders(self, *, now: datetime, limit: int) -> list[ReminderJob]: ...
    async def create_message_delivery(self, item: MessageDelivery) -> None: ...
    async def mark_reminder_sent(self, *, reminder_id: str, sent_at: datetime) -> bool: ...
    async def mark_reminder_failed(self, *, reminder_id: str, failed_at: datetime, error_text: str) -> bool: ...
    async def mark_reminder_canceled(self, *, reminder_id: str, canceled_at: datetime, reason_code: str) -> bool: ...
    async def next_delivery_attempt_no(self, *, reminder_id: str) -> int: ...


class BookingReader(Protocol):
    async def get_booking(self, booking_id: str) -> Booking | None: ...


class TelegramRecipientResolver(Protocol):
    async def resolve(self, *, reminder: ReminderJob) -> RecipientResolution: ...


class TelegramReminderSender(Protocol):
    async def send_reminder(self, *, target: TelegramDeliveryTarget, text: str) -> ReminderSendResult: ...


@dataclass(slots=True)
class ReminderDeliveryService:
    repository: ReminderDeliveryRepository
    booking_reader: BookingReader
    recipient_resolver: TelegramRecipientResolver
    sender: TelegramReminderSender

    async def deliver_due_reminders(self, *, now: datetime, batch_limit: int) -> int:
        claimed = await self.repository.claim_due_reminders(now=now, limit=batch_limit)
        for reminder in claimed:
            await self._deliver_single(reminder=reminder, now=now)
        return len(claimed)

    async def _deliver_single(self, *, reminder: ReminderJob, now: datetime) -> None:
        attempt_no = await self.repository.next_delivery_attempt_no(reminder_id=reminder.reminder_id)
        if reminder.channel != "telegram":
            await self._persist_failure(
                reminder=reminder,
                attempt_no=attempt_no,
                now=now,
                error_text="unsupported_channel",
            )
            return

        if reminder.booking_id is not None:
            booking = await self.booking_reader.get_booking(reminder.booking_id)
            if booking is None:
                await self.repository.mark_reminder_canceled(
                    reminder_id=reminder.reminder_id,
                    canceled_at=now,
                    reason_code="booking_missing",
                )
                await self.repository.create_message_delivery(
                    MessageDelivery(
                        message_delivery_id=f"md_{uuid4().hex}",
                        reminder_id=reminder.reminder_id,
                        patient_id=reminder.patient_id,
                        channel=reminder.channel,
                        delivery_status="canceled",
                        provider_message_id=None,
                        attempt_no=attempt_no,
                        error_text="booking_missing",
                        created_at=now,
                    )
                )
                return
            if booking.status in {"canceled", "completed", "no_show"}:
                await self.repository.mark_reminder_canceled(
                    reminder_id=reminder.reminder_id,
                    canceled_at=now,
                    reason_code=f"booking_{booking.status}",
                )
                await self.repository.create_message_delivery(
                    MessageDelivery(
                        message_delivery_id=f"md_{uuid4().hex}",
                        reminder_id=reminder.reminder_id,
                        patient_id=reminder.patient_id,
                        channel=reminder.channel,
                        delivery_status="canceled",
                        provider_message_id=None,
                        attempt_no=attempt_no,
                        error_text=f"booking_{booking.status}",
                        created_at=now,
                    )
                )
                return

        resolution = await self.recipient_resolver.resolve(reminder=reminder)
        if resolution.kind != "target_found" or resolution.target is None:
            await self._persist_failure(
                reminder=reminder,
                attempt_no=attempt_no,
                now=now,
                error_text=resolution.reason_code or resolution.kind,
            )
            return

        text = render_booking_reminder_text(reminder=reminder)
        try:
            send_result = await self.sender.send_reminder(target=resolution.target, text=text)
        except Exception as exc:  # noqa: BLE001
            await self._persist_failure(reminder=reminder, attempt_no=attempt_no, now=now, error_text=str(exc) or "send_failed")
            return

        await self.repository.create_message_delivery(
            MessageDelivery(
                message_delivery_id=f"md_{uuid4().hex}",
                reminder_id=reminder.reminder_id,
                patient_id=reminder.patient_id,
                channel=reminder.channel,
                delivery_status="sent",
                provider_message_id=send_result.provider_message_id,
                attempt_no=attempt_no,
                error_text=None,
                created_at=now,
            )
        )
        await self.repository.mark_reminder_sent(reminder_id=reminder.reminder_id, sent_at=now)

    async def _persist_failure(self, *, reminder: ReminderJob, attempt_no: int, now: datetime, error_text: str) -> None:
        await self.repository.create_message_delivery(
            MessageDelivery(
                message_delivery_id=f"md_{uuid4().hex}",
                reminder_id=reminder.reminder_id,
                patient_id=reminder.patient_id,
                channel=reminder.channel,
                delivery_status="failed",
                provider_message_id=None,
                attempt_no=attempt_no,
                error_text=error_text,
                created_at=now,
            )
        )
        await self.repository.mark_reminder_failed(reminder_id=reminder.reminder_id, failed_at=now, error_text=error_text)


def render_booking_reminder_text(*, reminder: ReminderJob) -> str:
    locale = (reminder.locale_at_send_time or "ru").lower()
    if locale.startswith("en"):
        if reminder.reminder_type == "booking_confirmation":
            return "DentFlow reminder: your dental visit is coming up. Please keep this appointment in your plans."
        if reminder.reminder_type == "booking_day_of":
            return "DentFlow reminder: your dental visit is today. We are waiting for you at the clinic."
        return "DentFlow reminder: your dental visit is coming soon."

    if reminder.reminder_type == "booking_confirmation":
        return "Напоминание DentFlow: ваш визит к стоматологу скоро. Пожалуйста, сохраните запись в планах."
    if reminder.reminder_type == "booking_day_of":
        return "Напоминание DentFlow: ваш визит к стоматологу сегодня. Ждём вас в клинике."
    return "Напоминание DentFlow: ваш визит к стоматологу скоро."
