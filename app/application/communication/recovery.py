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
        stale_minutes = int(self.policy_resolver.resolve_policy("communication.reminder_stale_queued_after_minutes", clinic_id="default") or 15)
        retry_max_attempts = int(self.policy_resolver.resolve_policy("communication.reminder_retry_max_attempts", clinic_id="default") or 3)
        queued_before = now - timedelta(minutes=max(stale_minutes, 1))
        stale = await self.reminder_repository.list_stale_queued_reminders(queued_before=queued_before, limit=limit)
        requeued = 0
        failed = 0
        for reminder in stale:
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
        enabled = bool(self.policy_resolver.resolve_policy("booking.non_response_escalation_enabled", clinic_id="default"))
        if not enabled:
            return ReminderRecoveryStats()
        threshold_minutes = int(self.policy_resolver.resolve_policy("booking.non_response_escalation_after_minutes", clinic_id="default") or 30)
        sent_before = now - timedelta(minutes=max(threshold_minutes, 1))
        candidates = await self.reminder_repository.list_confirmation_no_response_candidates(sent_before=sent_before, limit=limit)
        escalated = 0
        for reminder in candidates:
            if reminder.booking_id is None:
                continue
            booking = await self.booking_repository.get_booking(reminder.booking_id)
            if booking is None:
                continue
            if booking.status in {"confirmed", "canceled", "completed", "no_show"}:
                continue
            if await self._upsert_recovery_escalation(reminder=reminder, now=now, reason_code="booking_confirmation_no_response"):
                escalated += 1
        return ReminderRecoveryStats(no_response_escalated=escalated)

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
