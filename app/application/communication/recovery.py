from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from app.application.policy import PolicyResolver
from app.domain.booking import AdminEscalation, Booking, BookingSession
from app.domain.communication import ReminderJob


class ReminderRecoveryRepository(Protocol):
    async def list_stale_queued_reminders(self, *, queued_before: datetime, limit: int) -> list[ReminderJob]: ...
    async def reclaim_stale_queued_reminder(self, *, reminder_id: str, retry_at: datetime) -> bool: ...
    async def mark_reminder_failed(self, *, reminder_id: str, failed_at: datetime, error_text: str) -> bool: ...
    async def list_failed_booking_reminders(self, *, limit: int) -> list[ReminderJob]: ...
    async def list_confirmation_no_response_candidates(self, *, sent_before: datetime, limit: int) -> list[ReminderJob]: ...
    async def create_reminder_job(self, item: ReminderJob) -> None: ...
    async def get_reminder(self, *, reminder_id: str) -> ReminderJob | None: ...


class ReminderRecoveryBookingRepository(Protocol):
    async def get_booking(self, booking_id: str) -> Booking | None: ...
    async def find_latest_session_for_patient(self, *, clinic_id: str, patient_id: str) -> BookingSession | None: ...
    async def upsert_admin_escalation(self, item: AdminEscalation) -> None: ...
    async def get_admin_escalation(self, admin_escalation_id: str) -> AdminEscalation | None: ...
    async def list_open_admin_escalations(self, *, clinic_id: str, limit: int) -> list[AdminEscalation]: ...


@dataclass(slots=True, frozen=True)
class ReminderRecoveryStats:
    stale_requeued: int = 0
    stale_failed: int = 0
    failed_escalated: int = 0
    no_response_escalated: int = 0


@dataclass(slots=True)
class ReminderRecoveryService:
    reminder_repository: ReminderRecoveryRepository
    booking_repository: ReminderRecoveryBookingRepository
    policy_resolver: PolicyResolver

    async def recover_stale_queued_reminders(self, *, now: datetime, limit: int = 100) -> ReminderRecoveryStats:
        queued_before = now - timedelta(minutes=1)
        stale = await self.reminder_repository.list_stale_queued_reminders(queued_before=queued_before, limit=limit)
        stale_minutes_by_clinic: dict[str, int] = {}
        retry_max_by_clinic: dict[str, int] = {}
        requeued = 0
        failed = 0
        for reminder in stale:
            stale_minutes = self._resolve_int_policy(
                key="communication.reminder_stale_queued_after_minutes",
                clinic_id=reminder.clinic_id,
                fallback=15,
                cache=stale_minutes_by_clinic,
            )
            stale_before = now - timedelta(minutes=max(stale_minutes, 1))
            if reminder.queued_at is None or reminder.queued_at > stale_before:
                continue
            retry_max_attempts = self._resolve_int_policy(
                key="communication.reminder_retry_max_attempts",
                clinic_id=reminder.clinic_id,
                fallback=3,
                cache=retry_max_by_clinic,
            )
            if reminder.delivery_attempts_count >= retry_max_attempts:
                if await self.reminder_repository.mark_reminder_failed(
                    reminder_id=reminder.reminder_id,
                    failed_at=now,
                    error_text="stale_queued_retry_exhausted",
                ):
                    failed += 1
                await self._upsert_recovery_escalation(reminder=reminder, now=now, reason_code="reminder_delivery_stale_queued")
                continue
            if await self.reminder_repository.reclaim_stale_queued_reminder(reminder_id=reminder.reminder_id, retry_at=now):
                requeued += 1
        return ReminderRecoveryStats(stale_requeued=requeued, stale_failed=failed)

    async def escalate_failed_delivery_reminders(self, *, now: datetime, limit: int = 100) -> ReminderRecoveryStats:
        reminders = await self.reminder_repository.list_failed_booking_reminders(limit=limit)
        escalated = 0
        for reminder in reminders:
            reason = "reminder_target_missing" if (reminder.last_error_code or "").startswith("target") else "reminder_delivery_failed"
            if await self._upsert_recovery_escalation(reminder=reminder, now=now, reason_code=reason):
                escalated += 1
        return ReminderRecoveryStats(failed_escalated=escalated)

    async def detect_confirmation_no_response(self, *, now: datetime, limit: int = 100) -> ReminderRecoveryStats:
        sent_before = now - timedelta(minutes=1)
        candidates = await self.reminder_repository.list_confirmation_no_response_candidates(sent_before=sent_before, limit=limit)
        enabled_by_clinic: dict[str, bool] = {}
        threshold_by_clinic: dict[str, int] = {}
        escalated = 0
        for reminder in candidates:
            enabled = self._resolve_bool_policy(
                key="booking.non_response_escalation_enabled",
                clinic_id=reminder.clinic_id,
                fallback=False,
                cache=enabled_by_clinic,
            )
            if not enabled:
                continue
            threshold_minutes = self._resolve_int_policy(
                key="booking.non_response_escalation_after_minutes",
                clinic_id=reminder.clinic_id,
                fallback=30,
                cache=threshold_by_clinic,
            )
            sent_at = reminder.sent_at
            if sent_at is None:
                continue
            sent_cutoff = now - timedelta(minutes=max(threshold_minutes, 1))
            if sent_at > sent_cutoff:
                continue
            if reminder.booking_id is None:
                continue
            booking = await self.booking_repository.get_booking(reminder.booking_id)
            if booking is None:
                continue
            if booking.status in {"confirmed", "canceled", "completed", "no_show"}:
                continue
            followup = await self._ensure_no_response_followup(reminder=reminder, now=now)
            if followup == "scheduled":
                continue
            if not self._followup_window_elapsed(followup=followup, now=now, clinic_id=reminder.clinic_id):
                continue
            if await self._upsert_recovery_escalation(reminder=reminder, now=now, reason_code="booking_confirmation_no_response"):
                escalated += 1
        return ReminderRecoveryStats(no_response_escalated=escalated)

    async def _ensure_no_response_followup(self, *, reminder: ReminderJob, now: datetime) -> ReminderJob | str:
        enabled = bool(self.policy_resolver.resolve_policy("booking.no_response_followup_enabled", clinic_id=reminder.clinic_id))
        if not enabled:
            return "disabled"
        followup_id = f"rem_nr_{reminder.reminder_id}"
        existing = await self.reminder_repository.get_reminder(reminder_id=followup_id)
        if existing is not None:
            return existing
        delay_minutes = int(self.policy_resolver.resolve_policy("booking.no_response_followup_delay_minutes", clinic_id=reminder.clinic_id) or 30)
        followup = ReminderJob(
            reminder_id=followup_id,
            clinic_id=reminder.clinic_id,
            patient_id=reminder.patient_id,
            booking_id=reminder.booking_id,
            care_order_id=None,
            recommendation_id=None,
            reminder_type="booking_no_response_followup",
            channel=reminder.channel,
            status="scheduled",
            scheduled_for=now + timedelta(minutes=max(delay_minutes, 1)),
            payload_key="booking.confirmation.no_response_followup",
            locale_at_send_time=reminder.locale_at_send_time,
            planning_group=f"booking:{reminder.booking_id}:no_response_followup",
            supersedes_reminder_id=reminder.reminder_id,
            created_at=now,
            updated_at=now,
        )
        await self.reminder_repository.create_reminder_job(followup)
        return "scheduled"

    def _followup_window_elapsed(self, *, followup: ReminderJob | str, now: datetime, clinic_id: str) -> bool:
        if isinstance(followup, str):
            return followup == "disabled"
        if followup.status in {"scheduled", "queued"}:
            return False
        if followup.status == "acknowledged":
            return False
        if followup.status != "sent":
            return True
        window_minutes = int(
            self.policy_resolver.resolve_policy("booking.non_response_escalation_after_followup_minutes", clinic_id=clinic_id) or 30
        )
        sent_at = followup.sent_at
        if sent_at is None:
            return True
        return sent_at <= now - timedelta(minutes=max(window_minutes, 1))

    async def _upsert_recovery_escalation(self, *, reminder: ReminderJob, now: datetime, reason_code: str) -> bool:
        if reminder.booking_id is None:
            return False
        session = await self.booking_repository.find_latest_session_for_patient(clinic_id=reminder.clinic_id, patient_id=reminder.patient_id)
        if session is None:
            return False
        escalation_id = f"aes_rem_{reason_code}_{reminder.reminder_id}"
        existing = await self.booking_repository.get_admin_escalation(escalation_id)
        if existing is not None and existing.status != "open":
            return False
        payload = {
            "booking_id": reminder.booking_id,
            "reminder_id": reminder.reminder_id,
            "reason_code": reason_code,
            "last_error_code": reminder.last_error_code,
            "last_error_text": reminder.last_error_text,
        }
        escalation = AdminEscalation(
            admin_escalation_id=escalation_id,
            clinic_id=reminder.clinic_id,
            booking_session_id=session.booking_session_id,
            patient_id=reminder.patient_id,
            reason_code=reason_code,
            priority="high" if reason_code in {"booking_confirmation_no_response", "reminder_target_missing"} else "normal",
            status="open",
            assigned_to_actor_id=None,
            payload_summary=payload,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        await self.booking_repository.upsert_admin_escalation(escalation)
        return existing is None

    async def list_open_reminder_escalations(self, *, clinic_id: str, limit: int = 50) -> list[AdminEscalation]:
        items = await self.booking_repository.list_open_admin_escalations(clinic_id=clinic_id, limit=limit)
        return [item for item in items if item.reason_code.startswith("reminder") or item.reason_code == "booking_confirmation_no_response"]

    def _resolve_int_policy(self, *, key: str, clinic_id: str, fallback: int, cache: dict[str, int]) -> int:
        if clinic_id in cache:
            return cache[clinic_id]
        value = int(self.policy_resolver.resolve_policy(key, clinic_id=clinic_id) or fallback)
        cache[clinic_id] = value
        return value

    def _resolve_bool_policy(self, *, key: str, clinic_id: str, fallback: bool, cache: dict[str, bool]) -> bool:
        if clinic_id in cache:
            return cache[clinic_id]
        raw = self.policy_resolver.resolve_policy(key, clinic_id=clinic_id)
        value = fallback if raw is None else bool(raw)
        cache[clinic_id] = value
        return value
