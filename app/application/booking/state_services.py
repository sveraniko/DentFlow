from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Generic, Protocol, TypeVar
from uuid import uuid4

from app.domain.booking import Booking, BookingSession, BookingStatusHistory, SessionEvent, SlotHold, WaitlistEntry
from app.domain.booking.errors import (
    InvalidBookingTransitionError,
    InvalidSessionTransitionError,
    InvalidSlotHoldTransitionError,
    InvalidWaitlistTransitionError,
)
from app.domain.booking.lifecycle import (
    TransitionDecision,
    evaluate_booking_session_transition,
    evaluate_booking_transition,
    evaluate_slot_hold_transition,
    evaluate_waitlist_entry_transition,
)


class BookingTransaction(Protocol):
    async def upsert_booking_session(self, item: BookingSession) -> None: ...
    async def append_session_event(self, event: SessionEvent) -> None: ...
    async def upsert_slot_hold(self, item: SlotHold) -> None: ...
    async def upsert_booking(self, item: Booking) -> None: ...
    async def append_booking_status_history(self, item: BookingStatusHistory) -> None: ...
    async def upsert_waitlist_entry(self, item: WaitlistEntry) -> None: ...


class BookingTransitionRepository(Protocol):
    def transaction(self) -> AbstractAsyncContextManager[BookingTransaction]: ...

    async def get_booking_session(self, booking_session_id: str) -> BookingSession | None: ...
    async def get_slot_hold(self, slot_hold_id: str) -> SlotHold | None: ...
    async def get_booking(self, booking_id: str) -> Booking | None: ...
    async def get_waitlist_entry(self, waitlist_entry_id: str) -> WaitlistEntry | None: ...


TEntity = TypeVar("TEntity")


@dataclass(frozen=True, slots=True)
class TransitionResult(Generic[TEntity]):
    entity: TEntity
    changed: bool
    decision: TransitionDecision


@dataclass(slots=True)
class BookingSessionStateService:
    repository: BookingTransitionRepository

    async def transition_session(
        self,
        *,
        booking_session_id: str,
        to_status: str,
        reason_code: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
        payload_json: dict[str, object] | None = None,
        occurred_at: datetime | None = None,
    ) -> TransitionResult[BookingSession]:
        now = occurred_at or datetime.now(timezone.utc)
        current = await self.repository.get_booking_session(booking_session_id)
        if current is None:
            raise KeyError(f"Booking session not found: {booking_session_id}")

        decision = evaluate_booking_session_transition(current.status, to_status)
        if not decision.is_allowed:
            raise InvalidSessionTransitionError(current_status=current.status, requested_status=to_status)
        if decision.is_noop:
            return TransitionResult(entity=current, changed=False, decision=decision)

        async with self.repository.transaction() as tx:
            return await self.transition_session_in_transaction(
                tx=tx,
                current=current,
                to_status=to_status,
                reason_code=reason_code,
                actor_type=actor_type,
                actor_id=actor_id,
                payload_json=payload_json,
                occurred_at=now,
            )

    async def transition_session_in_transaction(
        self,
        *,
        tx: BookingTransaction,
        current: BookingSession,
        to_status: str,
        reason_code: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
        payload_json: dict[str, object] | None = None,
        occurred_at: datetime | None = None,
    ) -> TransitionResult[BookingSession]:
        now = occurred_at or datetime.now(timezone.utc)
        decision = evaluate_booking_session_transition(current.status, to_status)
        if not decision.is_allowed:
            raise InvalidSessionTransitionError(current_status=current.status, requested_status=to_status)
        if decision.is_noop:
            return TransitionResult(entity=current, changed=False, decision=decision)
        updated = BookingSession(**{**asdict(current), "status": to_status, "updated_at": now})
        event_payload = dict(payload_json or {})
        if reason_code is not None:
            event_payload.setdefault("reason_code", reason_code)
        await tx.upsert_booking_session(updated)
        await tx.append_session_event(
            SessionEvent(
                session_event_id=f"bse_{uuid4().hex}",
                booking_session_id=current.booking_session_id,
                event_name=f"booking_session.{to_status}",
                payload_json=event_payload or None,
                actor_type=actor_type,
                actor_id=actor_id,
                occurred_at=now,
            )
        )
        return TransitionResult(entity=updated, changed=True, decision=decision)


@dataclass(slots=True)
class SlotHoldStateService:
    repository: BookingTransitionRepository

    async def transition_hold(
        self,
        *,
        slot_hold_id: str,
        to_status: str,
        actor_type: str | None = None,
        actor_id: str | None = None,
        reason_code: str | None = None,
        session_event_name: str | None = None,
        payload_json: dict[str, object] | None = None,
        occurred_at: datetime | None = None,
    ) -> TransitionResult[SlotHold]:
        now = occurred_at or datetime.now(timezone.utc)
        current = await self.repository.get_slot_hold(slot_hold_id)
        if current is None:
            raise KeyError(f"Slot hold not found: {slot_hold_id}")

        decision = evaluate_slot_hold_transition(current.status, to_status)
        if not decision.is_allowed:
            raise InvalidSlotHoldTransitionError(current_status=current.status, requested_status=to_status)
        if decision.is_noop:
            return TransitionResult(entity=current, changed=False, decision=decision)

        async with self.repository.transaction() as tx:
            return await self.transition_hold_in_transaction(
                tx=tx,
                current=current,
                to_status=to_status,
                actor_type=actor_type,
                actor_id=actor_id,
                reason_code=reason_code,
                session_event_name=session_event_name,
                payload_json=payload_json,
                occurred_at=now,
            )

    async def transition_hold_in_transaction(
        self,
        *,
        tx: BookingTransaction,
        current: SlotHold,
        to_status: str,
        actor_type: str | None = None,
        actor_id: str | None = None,
        reason_code: str | None = None,
        session_event_name: str | None = None,
        payload_json: dict[str, object] | None = None,
        occurred_at: datetime | None = None,
    ) -> TransitionResult[SlotHold]:
        now = occurred_at or datetime.now(timezone.utc)
        decision = evaluate_slot_hold_transition(current.status, to_status)
        if not decision.is_allowed:
            raise InvalidSlotHoldTransitionError(current_status=current.status, requested_status=to_status)
        if decision.is_noop:
            return TransitionResult(entity=current, changed=False, decision=decision)
        updated = SlotHold(**{**asdict(current), "status": to_status})
        await tx.upsert_slot_hold(updated)
        if session_event_name:
            event_payload = dict(payload_json or {})
            if reason_code is not None:
                event_payload.setdefault("reason_code", reason_code)
            await tx.append_session_event(
                SessionEvent(
                    session_event_id=f"bse_{uuid4().hex}",
                    booking_session_id=updated.booking_session_id,
                    event_name=session_event_name,
                    payload_json=event_payload or None,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    occurred_at=now,
                )
            )
        return TransitionResult(entity=updated, changed=True, decision=decision)


@dataclass(slots=True)
class BookingStateService:
    repository: BookingTransitionRepository

    async def transition_booking(
        self,
        *,
        booking_id: str,
        to_status: str,
        reason_code: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> TransitionResult[Booking]:
        now = occurred_at or datetime.now(timezone.utc)
        current = await self.repository.get_booking(booking_id)
        if current is None:
            raise KeyError(f"Booking not found: {booking_id}")

        decision = evaluate_booking_transition(current.status, to_status)
        if not decision.is_allowed:
            raise InvalidBookingTransitionError(current_status=current.status, requested_status=to_status)
        if decision.is_noop:
            return TransitionResult(entity=current, changed=False, decision=decision)

        async with self.repository.transaction() as tx:
            return await self.transition_booking_in_transaction(
                tx=tx,
                current=current,
                to_status=to_status,
                reason_code=reason_code,
                actor_type=actor_type,
                actor_id=actor_id,
                occurred_at=now,
            )

    async def transition_booking_in_transaction(
        self,
        *,
        tx: BookingTransaction,
        current: Booking,
        to_status: str,
        reason_code: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> TransitionResult[Booking]:
        now = occurred_at or datetime.now(timezone.utc)
        decision = evaluate_booking_transition(current.status, to_status)
        if not decision.is_allowed:
            raise InvalidBookingTransitionError(current_status=current.status, requested_status=to_status)
        if decision.is_noop:
            return TransitionResult(entity=current, changed=False, decision=decision)
        updated = Booking(**self._build_booking_payload(current=current, to_status=to_status, now=now))
        await tx.upsert_booking(updated)
        await tx.append_booking_status_history(
            BookingStatusHistory(
                booking_status_history_id=f"bsh_{uuid4().hex}",
                booking_id=current.booking_id,
                old_status=current.status,
                new_status=to_status,
                reason_code=reason_code,
                actor_type=actor_type,
                actor_id=actor_id,
                occurred_at=now,
            )
        )
        return TransitionResult(entity=updated, changed=True, decision=decision)

    def _build_booking_payload(self, *, current: Booking, to_status: str, now: datetime) -> dict[str, object]:
        payload: dict[str, object] = {**asdict(current), "status": to_status, "updated_at": now}
        status_to_timestamp_field = {
            "confirmed": "confirmed_at",
            "canceled": "canceled_at",
            "checked_in": "checked_in_at",
            "in_service": "in_service_at",
            "completed": "completed_at",
            "no_show": "no_show_at",
        }
        timestamp_field = status_to_timestamp_field.get(to_status)
        if timestamp_field:
            payload[timestamp_field] = now
        return payload


@dataclass(slots=True)
class WaitlistStateService:
    repository: BookingTransitionRepository

    async def transition_waitlist_entry(
        self,
        *,
        waitlist_entry_id: str,
        to_status: str,
        occurred_at: datetime | None = None,
    ) -> TransitionResult[WaitlistEntry]:
        now = occurred_at or datetime.now(timezone.utc)
        current = await self.repository.get_waitlist_entry(waitlist_entry_id)
        if current is None:
            raise KeyError(f"Waitlist entry not found: {waitlist_entry_id}")

        decision = evaluate_waitlist_entry_transition(current.status, to_status)
        if not decision.is_allowed:
            raise InvalidWaitlistTransitionError(current_status=current.status, requested_status=to_status)
        if decision.is_noop:
            return TransitionResult(entity=current, changed=False, decision=decision)

        async with self.repository.transaction() as tx:
            return await self.transition_waitlist_entry_in_transaction(tx=tx, current=current, to_status=to_status, occurred_at=now)

    async def transition_waitlist_entry_in_transaction(
        self,
        *,
        tx: BookingTransaction,
        current: WaitlistEntry,
        to_status: str,
        occurred_at: datetime | None = None,
    ) -> TransitionResult[WaitlistEntry]:
        now = occurred_at or datetime.now(timezone.utc)
        decision = evaluate_waitlist_entry_transition(current.status, to_status)
        if not decision.is_allowed:
            raise InvalidWaitlistTransitionError(current_status=current.status, requested_status=to_status)
        if decision.is_noop:
            return TransitionResult(entity=current, changed=False, decision=decision)
        updated = WaitlistEntry(**{**asdict(current), "status": to_status, "updated_at": now})
        await tx.upsert_waitlist_entry(updated)
        return TransitionResult(entity=updated, changed=True, decision=decision)
