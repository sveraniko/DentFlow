from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import uuid4

from app.application.policy import PolicyResolver
from app.domain.booking import Booking
from app.domain.communication import ReminderJob
from app.domain.patient_registry.models import PatientPreference


class ReminderPlanningTransaction(Protocol):
    async def create_reminder_job_in_transaction(self, item: ReminderJob) -> None: ...
    async def cancel_scheduled_reminders_for_booking_in_transaction(
        self, *, booking_id: str, canceled_at: datetime, reason_code: str
    ) -> int: ...


class ReminderJobRepository(Protocol):
    async def create_reminder_job(self, item: ReminderJob) -> None: ...
    async def list_reminder_jobs_for_booking(self, *, booking_id: str) -> list[ReminderJob]: ...
    async def cancel_scheduled_reminders_for_booking(self, *, booking_id: str, canceled_at: datetime, reason_code: str) -> int: ...


class PatientPreferenceReader(Protocol):
    async def get_preferences(self, patient_id: str) -> PatientPreference | None: ...


@dataclass(slots=True, frozen=True)
class ReminderPlanItem:
    reminder_type: str
    scheduled_for: datetime
    payload_key: str


@dataclass(slots=True)
class BookingReminderPlanner:
    policy_resolver: PolicyResolver

    def build_plan(self, *, booking: Booking, now: datetime) -> list[ReminderPlanItem]:
        plan: list[ReminderPlanItem] = []
        if booking.status not in {"pending_confirmation", "confirmed"}:
            return plan

        if bool(self.policy_resolver.resolve_policy("booking.confirmation_required", clinic_id=booking.clinic_id, branch_id=booking.branch_id)):
            offset_hours = int(self.policy_resolver.resolve_policy("booking.confirmation_offset_hours", clinic_id=booking.clinic_id, branch_id=booking.branch_id) or 24)
            when = booking.scheduled_start_at - timedelta(hours=offset_hours)
            if when > now:
                plan.append(ReminderPlanItem(reminder_type="booking_confirmation", scheduled_for=when, payload_key="booking.confirmation"))

        raw_offsets = self.policy_resolver.resolve_policy("booking.reminder_offsets_hours", clinic_id=booking.clinic_id, branch_id=booking.branch_id)
        offsets = [int(v) for v in raw_offsets] if isinstance(raw_offsets, list) else [24, 2]
        for offset in sorted(set(offsets), reverse=True):
            when = booking.scheduled_start_at - timedelta(hours=offset)
            if when <= now:
                continue
            reminder_type = "booking_day_of" if offset <= 12 else "booking_previsit"
            payload_key = f"booking.reminder.{offset}h"
            plan.append(ReminderPlanItem(reminder_type=reminder_type, scheduled_for=when, payload_key=payload_key))
        return plan


@dataclass(slots=True)
class BookingReminderService:
    repository: ReminderJobRepository
    planner: BookingReminderPlanner
    policy_resolver: PolicyResolver
    patient_preference_reader: PatientPreferenceReader | None = None

    async def replace_booking_reminder_plan(self, *, booking: Booking, reason_code: str = "booking_plan_replaced") -> list[ReminderJob]:
        now = datetime.now(timezone.utc)
        await self.repository.cancel_scheduled_reminders_for_booking(booking_id=booking.booking_id, canceled_at=now, reason_code=reason_code)

        plan_items = self.planner.build_plan(booking=booking, now=now)
        if not plan_items:
            return []

        planning_group = f"booking:{booking.booking_id}:plan:{now.strftime('%Y%m%dT%H%M%SZ')}"
        channel, locale = await self._resolve_channel_locale(booking)
        created: list[ReminderJob] = []
        for item in plan_items:
            job = ReminderJob(
                reminder_id=f"rem_{uuid4().hex}",
                clinic_id=booking.clinic_id,
                patient_id=booking.patient_id,
                booking_id=booking.booking_id,
                care_order_id=None,
                recommendation_id=None,
                reminder_type=item.reminder_type,
                channel=channel,
                status="scheduled",
                scheduled_for=item.scheduled_for,
                payload_key=item.payload_key,
                locale_at_send_time=locale,
                planning_group=planning_group,
                supersedes_reminder_id=None,
                created_at=now,
                updated_at=now,
            )
            await self.repository.create_reminder_job(job)
            created.append(job)
        return created

    async def replace_booking_reminder_plan_in_transaction(
        self,
        *,
        tx: ReminderPlanningTransaction,
        booking: Booking,
        reason_code: str = "booking_plan_replaced",
        now: datetime | None = None,
    ) -> list[ReminderJob]:
        planned_at = now or datetime.now(timezone.utc)
        await tx.cancel_scheduled_reminders_for_booking_in_transaction(
            booking_id=booking.booking_id,
            canceled_at=planned_at,
            reason_code=reason_code,
        )

        plan_items = self.planner.build_plan(booking=booking, now=planned_at)
        if not plan_items:
            return []

        planning_group = f"booking:{booking.booking_id}:plan:{planned_at.strftime('%Y%m%dT%H%M%SZ')}"
        channel, locale = await self._resolve_channel_locale(booking)
        created: list[ReminderJob] = []
        for item in plan_items:
            job = ReminderJob(
                reminder_id=f"rem_{uuid4().hex}",
                clinic_id=booking.clinic_id,
                patient_id=booking.patient_id,
                booking_id=booking.booking_id,
                care_order_id=None,
                recommendation_id=None,
                reminder_type=item.reminder_type,
                channel=channel,
                status="scheduled",
                scheduled_for=item.scheduled_for,
                payload_key=item.payload_key,
                locale_at_send_time=locale,
                planning_group=planning_group,
                supersedes_reminder_id=None,
                created_at=planned_at,
                updated_at=planned_at,
            )
            await tx.create_reminder_job_in_transaction(job)
            created.append(job)
        return created

    async def cancel_booking_reminder_plan(self, *, booking_id: str, reason_code: str) -> int:
        return await self.repository.cancel_scheduled_reminders_for_booking(
            booking_id=booking_id,
            canceled_at=datetime.now(timezone.utc),
            reason_code=reason_code,
        )

    async def cancel_booking_reminder_plan_in_transaction(
        self,
        *,
        tx: ReminderPlanningTransaction,
        booking_id: str,
        reason_code: str,
        now: datetime | None = None,
    ) -> int:
        canceled_at = now or datetime.now(timezone.utc)
        return await tx.cancel_scheduled_reminders_for_booking_in_transaction(
            booking_id=booking_id,
            canceled_at=canceled_at,
            reason_code=reason_code,
        )

    async def list_booking_reminders(self, *, booking_id: str) -> list[ReminderJob]:
        return await self.repository.list_reminder_jobs_for_booking(booking_id=booking_id)

    async def _resolve_channel_locale(self, booking: Booking) -> tuple[str, str | None]:
        default_channel = self.policy_resolver.resolve_policy("booking.default_reminder_channel", clinic_id=booking.clinic_id, branch_id=booking.branch_id) or "telegram"
        default_locale = self.policy_resolver.resolve_policy("clinic.default_locale", clinic_id=booking.clinic_id, branch_id=booking.branch_id)
        if self.patient_preference_reader is None:
            return str(default_channel), str(default_locale) if default_locale is not None else None

        pref = await self.patient_preference_reader.get_preferences(booking.patient_id)
        if pref is None:
            return str(default_channel), str(default_locale) if default_locale is not None else None

        preferred_channel = _select_allowed_channel(preference=pref, fallback=str(default_channel))
        preferred_locale = pref.preferred_language or (str(default_locale) if default_locale is not None else None)
        return preferred_channel, preferred_locale


def _select_allowed_channel(*, preference: PatientPreference, fallback: str) -> str:
    requested = preference.preferred_reminder_channel or fallback
    requested = requested.lower()
    allow_map = {
        "telegram": preference.allow_telegram,
        "sms": preference.allow_sms,
        "call": preference.allow_call,
        "email": preference.allow_email,
    }
    if allow_map.get(requested, False):
        return requested
    for channel, allowed in allow_map.items():
        if allowed:
            return channel
    return fallback
