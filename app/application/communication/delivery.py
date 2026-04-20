from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.booking import Booking
from app.domain.communication import MessageDelivery, ReminderJob
from app.application.policy import PolicyResolver
from app.application.communication.runtime_integrity import evaluate_booking_relevance
from app.common.i18n import I18nService


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
    async def mark_reminder_expired(self, *, reminder_id: str, expired_at: datetime, reason_code: str) -> bool: ...
    async def next_delivery_attempt_no(self, *, reminder_id: str) -> int: ...


class BookingReader(Protocol):
    async def get_booking(self, booking_id: str) -> Booking | None: ...


class TelegramRecipientResolver(Protocol):
    async def resolve(self, *, reminder: ReminderJob) -> RecipientResolution: ...


class TelegramReminderSender(Protocol):
    async def send_reminder(self, *, target: TelegramDeliveryTarget, text: str, actions: tuple[ReminderActionButton, ...]) -> ReminderSendResult: ...


class BookingTimezoneResolver(Protocol):
    def resolve_timezone(self, *, clinic_id: str, branch_id: str | None) -> str: ...


@dataclass(slots=True)
class ReminderDeliveryService:
    repository: ReminderDeliveryRepository
    booking_reader: BookingReader
    recipient_resolver: TelegramRecipientResolver
    sender: TelegramReminderSender
    policy_resolver: PolicyResolver | None = None
    i18n: I18nService | None = None
    timezone_resolver: BookingTimezoneResolver | None = None
    app_default_timezone: str = "UTC"

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

        booking = await self.booking_reader.get_booking(reminder.booking_id) if reminder.booking_id is not None else None
        relevance = evaluate_booking_relevance(reminder=reminder, booking=booking, now=now)
        if not relevance.should_send:
            await self._persist_non_send_terminal(
                reminder=reminder,
                attempt_no=attempt_no,
                now=now,
                terminal_status=relevance.terminal_status or "canceled",
                reason_code=relevance.reason_code or "no_longer_relevant",
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

        rendered = render_booking_reminder_message(
            reminder=reminder,
            booking=booking if reminder.booking_id is not None else None,
            i18n=self.i18n,
            timezone_resolver=self.timezone_resolver,
            app_default_timezone=self.app_default_timezone,
        )
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

    async def _persist_non_send_terminal(
        self,
        *,
        reminder: ReminderJob,
        attempt_no: int,
        now: datetime,
        terminal_status: str,
        reason_code: str,
    ) -> None:
        if terminal_status == "expired":
            await self.repository.mark_reminder_expired(
                reminder_id=reminder.reminder_id,
                expired_at=now,
                reason_code=reason_code,
            )
            delivery_status = "expired"
        else:
            await self.repository.mark_reminder_canceled(
                reminder_id=reminder.reminder_id,
                canceled_at=now,
                reason_code=reason_code,
            )
            delivery_status = "canceled"

        await self.repository.create_message_delivery(
            MessageDelivery(
                message_delivery_id=f"md_{uuid4().hex}",
                reminder_id=reminder.reminder_id,
                patient_id=reminder.patient_id,
                channel=reminder.channel,
                delivery_status=delivery_status,
                provider_message_id=None,
                attempt_no=attempt_no,
                error_text=reason_code,
                created_at=now,
            )
        )

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


def render_booking_reminder_message(
    *,
    reminder: ReminderJob,
    booking: Booking | None,
    i18n: I18nService | None = None,
    timezone_resolver: BookingTimezoneResolver | None = None,
    app_default_timezone: str = "UTC",
) -> RenderedReminderMessage:
    locale = (reminder.locale_at_send_time or "ru").lower()
    dt_label = "-"
    doctor_label = "-"
    service_label = "-"
    branch_label = "-"
    if booking is not None:
        tz_name = app_default_timezone
        if timezone_resolver is not None:
            tz_name = timezone_resolver.resolve_timezone(clinic_id=booking.clinic_id, branch_id=booking.branch_id)
        dt_label = booking.scheduled_start_at.astimezone(_zone_or_utc(tz_name)).strftime("%Y-%m-%d %H:%M %Z")
        doctor_label = booking.doctor_id or "-"
        service_label = booking.service_id or "-"
        branch_label = booking.branch_id or "-"

    text = _t(i18n, locale, "reminder.message.layout").format(
        datetime=dt_label,
        doctor=doctor_label,
        service=service_label,
        branch=branch_label,
        summary=_t(i18n, locale, f"reminder.type.{reminder.reminder_type}.summary"),
    )
    actions = _build_actions(reminder=reminder, i18n=i18n, locale=locale)
    return RenderedReminderMessage(text=text, actions=actions)


def _build_actions(*, reminder: ReminderJob, i18n: I18nService | None, locale: str) -> tuple[ReminderActionButton, ...]:
    action_map: dict[str, tuple[str, ...]] = {
        "booking_confirmation": ("confirm", "reschedule", "cancel"),
        "booking_no_response_followup": ("confirm", "reschedule", "cancel"),
        "booking_previsit": ("ack",),
        "booking_day_of": ("ack",),
        "booking_next_visit_recall": ("ack",),
    }
    actions = action_map.get(reminder.reminder_type, tuple())
    return tuple(
        ReminderActionButton(
            action=action,
            label=_t(i18n, locale, f"reminder.action.{action}"),
            callback_data=f"rem:{action}:{reminder.reminder_id}",
        )
        for action in actions
    )


def _t(i18n: I18nService | None, locale: str, key: str) -> str:
    if i18n is None:
        defaults = _DEFAULT_RU if not locale.startswith("en") else _DEFAULT_EN
        return defaults.get(key, key)
    return i18n.t(key, locale)


def _zone_or_utc(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


_DEFAULT_EN = {
    "reminder.message.layout": "DentFlow reminder\n📅 {datetime}\n👩‍⚕️ {doctor}\n🦷 {service}\n🏥 {branch}\n\n{summary}",
    "reminder.type.booking_confirmation.summary": "Please confirm your appointment or request a change.",
    "reminder.type.booking_previsit.summary": "Upcoming visit reminder. Please check the time.",
    "reminder.type.booking_day_of.summary": "Today is your dental visit. Please tap “Got it”.",
    "reminder.type.booking_no_response_followup.summary": "We still need your confirmation. Please confirm or request a reschedule.",
    "reminder.type.booking_next_visit_recall.summary": "It is time to plan your next prophylaxis visit.",
    "reminder.action.confirm": "✅ Confirm",
    "reminder.action.reschedule": "🔁 Reschedule",
    "reminder.action.cancel": "❌ Cancel",
    "reminder.action.ack": "👍 Got it",
}

_DEFAULT_RU = {
    "reminder.message.layout": "Напоминание DentFlow\n📅 {datetime}\n👩‍⚕️ {doctor}\n🦷 {service}\n🏥 {branch}\n\n{summary}",
    "reminder.type.booking_confirmation.summary": "Подтвердите запись или выберите удобное изменение.",
    "reminder.type.booking_previsit.summary": "Напоминание о предстоящем визите. Проверьте время, пожалуйста.",
    "reminder.type.booking_day_of.summary": "Сегодня ваш визит в клинику. Нажмите «Получил(а)».",
    "reminder.type.booking_no_response_followup.summary": "Мы всё ещё ждём подтверждение визита. Подтвердите или запросите перенос.",
    "reminder.type.booking_next_visit_recall.summary": "Пора запланировать следующий профилактический визит.",
    "reminder.action.confirm": "✅ Подтвердить",
    "reminder.action.reschedule": "🔁 Перенести",
    "reminder.action.cancel": "❌ Отменить",
    "reminder.action.ack": "👍 Получил(а)",
}
