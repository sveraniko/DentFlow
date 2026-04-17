from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Protocol

from app.application.booking.orchestration_outcomes import OrchestrationSuccess
from app.domain.communication import ReminderJob

ReminderActionName = Literal["ack", "confirm", "reschedule", "cancel"]


@dataclass(frozen=True, slots=True)
class ReminderActionOutcome:
    kind: str
    reason: str
    reminder_id: str | None = None
    booking_id: str | None = None


class ReminderActionRepository(Protocol):
    async def get_reminder(self, *, reminder_id: str) -> ReminderJob | None: ...
    async def mark_reminder_acknowledged(self, *, reminder_id: str, acknowledged_at: datetime) -> bool: ...
    async def has_sent_delivery_for_provider_message(self, *, reminder_id: str, provider_message_id: str) -> bool: ...


class ReminderActionTransaction(Protocol):
    async def get_reminder_for_update_in_transaction(self, *, reminder_id: str) -> ReminderJob | None: ...
    async def mark_reminder_acknowledged_in_transaction(self, *, reminder_id: str, acknowledged_at: datetime) -> bool: ...
    async def has_sent_delivery_for_provider_message_in_transaction(self, *, reminder_id: str, provider_message_id: str) -> bool: ...
    async def get_booking_for_update(self, booking_id: str): ...


class ReminderActionTransactionRepository(Protocol):
    def transaction(self): ...


class ReminderActionBookingOrchestration(Protocol):
    async def confirm_booking_in_transaction(self, *, tx: ReminderActionTransaction, booking_id: str, reason_code: str | None = None): ...
    async def request_booking_reschedule_in_transaction(
        self, *, tx: ReminderActionTransaction, booking_id: str, reason_code: str | None = None
    ): ...
    async def cancel_booking_in_transaction(self, *, tx: ReminderActionTransaction, booking_id: str, reason_code: str | None = None): ...


@dataclass(slots=True)
class ReminderActionService:
    repository: ReminderActionRepository
    transaction_repository: ReminderActionTransactionRepository
    booking_orchestration: ReminderActionBookingOrchestration

    async def handle_action(
        self,
        *,
        reminder_id: str,
        action: ReminderActionName,
        provider_message_id: str | None,
    ) -> ReminderActionOutcome:
        now = datetime.now(timezone.utc)
        async with self.transaction_repository.transaction() as tx:
            reminder = await tx.get_reminder_for_update_in_transaction(reminder_id=reminder_id)
            if reminder is None:
                return ReminderActionOutcome(kind="invalid", reason="reminder_not_found")

            if reminder.status in {"acknowledged", "canceled", "failed", "expired"}:
                return ReminderActionOutcome(
                    kind="stale",
                    reason=f"reminder_{reminder.status}",
                    reminder_id=reminder.reminder_id,
                    booking_id=reminder.booking_id,
                )
            if reminder.status != "sent":
                return ReminderActionOutcome(
                    kind="invalid",
                    reason="reminder_not_actionable",
                    reminder_id=reminder.reminder_id,
                    booking_id=reminder.booking_id,
                )

            if provider_message_id is not None:
                matched = await tx.has_sent_delivery_for_provider_message_in_transaction(
                    reminder_id=reminder.reminder_id,
                    provider_message_id=provider_message_id,
                )
                if not matched:
                    return ReminderActionOutcome(
                        kind="invalid",
                        reason="message_mismatch",
                        reminder_id=reminder.reminder_id,
                        booking_id=reminder.booking_id,
                    )

            if action == "ack":
                await tx.mark_reminder_acknowledged_in_transaction(
                    reminder_id=reminder.reminder_id,
                    acknowledged_at=now,
                )
                return ReminderActionOutcome(
                    kind="accepted",
                    reason="acknowledged",
                    reminder_id=reminder.reminder_id,
                    booking_id=reminder.booking_id,
                )

            if reminder.booking_id is None:
                return ReminderActionOutcome(
                    kind="invalid",
                    reason="booking_link_missing",
                    reminder_id=reminder.reminder_id,
                )

            booking = await tx.get_booking_for_update(reminder.booking_id)
            if booking is None:
                return ReminderActionOutcome(
                    kind="invalid",
                    reason="booking_missing",
                    reminder_id=reminder.reminder_id,
                    booking_id=reminder.booking_id,
                )

            if action == "confirm":
                result = await self.booking_orchestration.confirm_booking_in_transaction(
                    tx=tx,
                    booking_id=booking.booking_id,
                    reason_code="patient_reminder_confirmed",
                )
                if not isinstance(result, OrchestrationSuccess):
                    return ReminderActionOutcome(
                        kind="invalid",
                        reason="booking_not_confirmable",
                        reminder_id=reminder.reminder_id,
                        booking_id=reminder.booking_id,
                    )
                await tx.mark_reminder_acknowledged_in_transaction(reminder_id=reminder.reminder_id, acknowledged_at=now)
                return ReminderActionOutcome(
                    kind="accepted",
                    reason="booking_confirmed",
                    reminder_id=reminder.reminder_id,
                    booking_id=reminder.booking_id,
                )

            if action == "reschedule":
                result = await self.booking_orchestration.request_booking_reschedule_in_transaction(
                    tx=tx,
                    booking_id=booking.booking_id,
                    reason_code="patient_reminder_reschedule_requested",
                )
                if not isinstance(result, OrchestrationSuccess):
                    return ReminderActionOutcome(
                        kind="invalid",
                        reason="booking_not_reschedulable",
                        reminder_id=reminder.reminder_id,
                        booking_id=reminder.booking_id,
                    )
                await tx.mark_reminder_acknowledged_in_transaction(reminder_id=reminder.reminder_id, acknowledged_at=now)
                return ReminderActionOutcome(
                    kind="accepted",
                    reason="reschedule_requested",
                    reminder_id=reminder.reminder_id,
                    booking_id=reminder.booking_id,
                )

            if action == "cancel":
                result = await self.booking_orchestration.cancel_booking_in_transaction(
                    tx=tx,
                    booking_id=booking.booking_id,
                    reason_code="patient_reminder_canceled",
                )
                if not isinstance(result, OrchestrationSuccess):
                    return ReminderActionOutcome(
                        kind="invalid",
                        reason="booking_not_cancelable",
                        reminder_id=reminder.reminder_id,
                        booking_id=reminder.booking_id,
                    )
                await tx.mark_reminder_acknowledged_in_transaction(reminder_id=reminder.reminder_id, acknowledged_at=now)
                return ReminderActionOutcome(
                    kind="accepted",
                    reason="booking_canceled",
                    reminder_id=reminder.reminder_id,
                    booking_id=reminder.booking_id,
                )

            return ReminderActionOutcome(
                kind="invalid",
                reason="unsupported_action",
                reminder_id=reminder.reminder_id,
                booking_id=reminder.booking_id,
            )
