from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import uuid4

from app.domain.booking import Booking
from app.domain.communication import MessageDelivery, ReminderJob
from app.application.policy import PolicyResolver


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


@dataclass(slots=True, frozen=True)
class ReminderActionButton:
    action: str
    label: str
    callback_data: str


@dataclass(slots=True, frozen=True)
class RenderedReminderMessage:
    text: str
    actions: tuple[ReminderActionButton, ...]


class ReminderDeliveryRepository(Protocol):
    async def claim_due_reminders(self, *, now: datetime, limit: int) -> list[ReminderJob]: ...
    async def create_message_delivery(self, item: MessageDelivery) -> None: ...
    async def mark_reminder_sent(self, *, reminder_id: str, sent_at: datetime) -> bool: ...
    async def mark_reminder_failed(self, *, reminder_id: str, failed_at: datetime, error_text: str) -> bool: ...
    async def schedule_queued_reminder_retry(
        self,
        *,
        reminder_id: str,
        retry_at: datetime,
        failed_at: datetime,
        error_code: str,
        error_text: str,
    ) -> bool: ...
    async def mark_reminder_canceled(self, *, reminder_id: str, canceled_at: datetime, reason_code: str) -> bool: ...
    async def next_delivery_attempt_no(self, *, reminder_id: str) -> int: ...


class BookingReader(Protocol):
    async def get_booking(self, booking_id: str) -> Booking | None: ...


class TelegramRecipientResolver(Protocol):
    async def resolve(self, *, reminder: ReminderJob) -> RecipientResolution: ...


class TelegramReminderSender(Protocol):
    async def send_reminder(self, *, target: TelegramDeliveryTarget, text: str, actions: tuple[ReminderActionButton, ...]) -> ReminderSendResult: ...


@dataclass(slots=True)
class ReminderDeliveryService:
    repository: ReminderDeliveryRepository
    booking_reader: BookingReader
    recipient_resolver: TelegramRecipientResolver
    sender: TelegramReminderSender
    policy_resolver: PolicyResolver | None = None

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
                retryable=False,
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
                retryable=False,
            )
            return

        rendered = render_booking_reminder_message(reminder=reminder, booking=booking if reminder.booking_id is not None else None)
        try:
            send_result = await self.sender.send_reminder(target=resolution.target, text=rendered.text, actions=rendered.actions)
        except Exception as exc:  # noqa: BLE001
            await self._persist_failure(reminder=reminder, attempt_no=attempt_no, now=now, error_text=str(exc) or "send_failed", retryable=True)
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

    async def _persist_failure(self, *, reminder: ReminderJob, attempt_no: int, now: datetime, error_text: str, retryable: bool) -> None:
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
        if retryable and self._retry_enabled(reminder=reminder):
            retry_after = timedelta(minutes=self._retry_delay_minutes(reminder=reminder))
            if reminder.delivery_attempts_count + 1 < self._retry_max_attempts(reminder=reminder):
                await self.repository.schedule_queued_reminder_retry(
                    reminder_id=reminder.reminder_id,
                    retry_at=now + retry_after,
                    failed_at=now,
                    error_code="transient_delivery_error",
                    error_text=error_text,
                )
                return
        await self.repository.mark_reminder_failed(reminder_id=reminder.reminder_id, failed_at=now, error_text=error_text)

    def _retry_enabled(self, *, reminder: ReminderJob) -> bool:
        if self.policy_resolver is None:
            return True
        return bool(self.policy_resolver.resolve_policy("communication.reminder_retry_enabled", clinic_id=reminder.clinic_id))

    def _retry_max_attempts(self, *, reminder: ReminderJob) -> int:
        if self.policy_resolver is None:
            return 3
        return int(self.policy_resolver.resolve_policy("communication.reminder_retry_max_attempts", clinic_id=reminder.clinic_id) or 3)

    def _retry_delay_minutes(self, *, reminder: ReminderJob) -> int:
        if self.policy_resolver is None:
            return 5
        return int(self.policy_resolver.resolve_policy("communication.reminder_retry_delay_minutes", clinic_id=reminder.clinic_id) or 5)


def render_booking_reminder_message(*, reminder: ReminderJob, booking: Booking | None) -> RenderedReminderMessage:
    locale = (reminder.locale_at_send_time or "ru").lower()
    dt_label = "-"
    doctor_label = "-"
    service_label = "-"
    branch_label = "-"
    if booking is not None:
        dt_label = booking.scheduled_start_at.strftime("%Y-%m-%d %H:%M UTC")
        doctor_label = booking.doctor_id or "-"
        service_label = booking.service_id or "-"
        branch_label = booking.branch_id or "-"

    reminder_summary = ""
    actions: tuple[ReminderActionButton, ...]
    if locale.startswith("en"):
        if reminder.reminder_type == "booking_confirmation":
            reminder_summary = "Please confirm your booking."
            actions = (
                ReminderActionButton(action="confirm", label="✅ Confirm", callback_data=f"rem:confirm:{reminder.reminder_id}"),
                ReminderActionButton(action="reschedule", label="🔁 Reschedule", callback_data=f"rem:reschedule:{reminder.reminder_id}"),
                ReminderActionButton(action="cancel", label="❌ Cancel", callback_data=f"rem:cancel:{reminder.reminder_id}"),
            )
        elif reminder.reminder_type in {"booking_previsit", "booking_day_of"}:
            reminder_summary = "Please acknowledge this reminder."
            actions = (ReminderActionButton(action="ack", label="👍 Got it", callback_data=f"rem:ack:{reminder.reminder_id}"),)
        else:
            reminder_summary = "Your dental visit is coming soon."
            actions = tuple()
        text = (
            "DentFlow reminder\n"
            f"📅 {dt_label}\n"
            f"👩‍⚕️ {doctor_label}\n"
            f"🦷 {service_label}\n"
            f"🏥 {branch_label}\n\n"
            f"{reminder_summary}"
        )
        return RenderedReminderMessage(text=text, actions=actions)

    if reminder.reminder_type == "booking_confirmation":
        reminder_summary = "Подтвердите запись."
        actions = (
            ReminderActionButton(action="confirm", label="✅ Подтвердить", callback_data=f"rem:confirm:{reminder.reminder_id}"),
            ReminderActionButton(action="reschedule", label="🔁 Перенести", callback_data=f"rem:reschedule:{reminder.reminder_id}"),
            ReminderActionButton(action="cancel", label="❌ Отменить", callback_data=f"rem:cancel:{reminder.reminder_id}"),
        )
    elif reminder.reminder_type in {"booking_previsit", "booking_day_of"}:
        reminder_summary = "Подтвердите, что увидели напоминание."
        actions = (ReminderActionButton(action="ack", label="👍 Понял(а)", callback_data=f"rem:ack:{reminder.reminder_id}"),)
    else:
        reminder_summary = "Ваш визит скоро."
        actions = tuple()
    text = (
        "Напоминание DentFlow\n"
        f"📅 {dt_label}\n"
        f"👩‍⚕️ {doctor_label}\n"
        f"🦷 {service_label}\n"
        f"🏥 {branch_label}\n\n"
        f"{reminder_summary}"
    )
    return RenderedReminderMessage(text=text, actions=actions)
