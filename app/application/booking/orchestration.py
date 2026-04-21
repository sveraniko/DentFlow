from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Protocol
from uuid import uuid4

from app.application.booking.orchestration_outcomes import (
    AmbiguousMatchOutcome,
    BookingOutcome,
    BookingSessionOutcome,
    ConflictOutcome,
    EscalatedOutcome,
    HoldOutcome,
    InvalidStateOutcome,
    NoMatchOutcome,
    OrchestrationSuccess,
    SlotUnavailableOutcome,
    WaitlistOutcome,
)
from app.application.booking.patient_resolution import BookingPatientResolutionService
from app.application.booking.state_services import (
    BookingSessionStateService,
    BookingStateService,
    SlotHoldStateService,
    WaitlistStateService,
)
from app.application.communication import BookingReminderService
from app.application.policy import PolicyResolver
from app.domain.booking import AdminEscalation, Booking, BookingSession, BookingStatusHistory, SlotHold, WaitlistEntry
from app.domain.communication import ReminderJob
from app.domain.events import build_event
from app.domain.booking.errors import InvalidBookingTransitionError, InvalidSessionTransitionError, InvalidSlotHoldTransitionError

LIVE_SLOT_BOOKING_STATUSES: tuple[str, ...] = (
    "pending_confirmation",
    "confirmed",
    "reschedule_requested",
    "checked_in",
    "in_service",
)
TERMINAL_HOLD_STATUSES: tuple[str, ...] = ("released", "expired", "canceled", "consumed")


class BookingOrchestrationTransaction(Protocol):
    async def upsert_booking_session(self, item: BookingSession) -> None: ...
    async def upsert_slot_hold(self, item: SlotHold) -> None: ...
    async def upsert_booking(self, item: Booking) -> None: ...
    async def append_booking_status_history(self, item: BookingStatusHistory) -> None: ...
    async def upsert_waitlist_entry(self, item: WaitlistEntry) -> None: ...
    async def upsert_admin_escalation(self, item: AdminEscalation) -> None: ...
    async def get_booking_session_for_update(self, booking_session_id: str) -> BookingSession | None: ...
    async def get_slot_hold_for_update(self, slot_hold_id: str) -> SlotHold | None: ...
    async def get_booking_for_update(self, booking_id: str) -> Booking | None: ...
    async def get_availability_slot_for_update(self, slot_id: str): ...
    async def get_waitlist_entry_for_update(self, waitlist_entry_id: str) -> WaitlistEntry | None: ...
    async def find_slot_hold_for_update(self, *, slot_id: str, booking_session_id: str) -> SlotHold | None: ...
    async def list_active_holds_for_slot_for_update(self, *, slot_id: str) -> list[SlotHold]: ...
    async def list_active_holds_for_session_for_update(self, *, booking_session_id: str) -> list[SlotHold]: ...
    async def list_live_bookings_for_slot_for_update(self, *, slot_id: str) -> list[Booking]: ...
    async def create_reminder_job_in_transaction(self, item: ReminderJob) -> None: ...
    async def cancel_scheduled_reminders_for_booking_in_transaction(
        self, *, booking_id: str, canceled_at: datetime, reason_code: str
    ) -> int: ...
    async def append_outbox_event(self, event) -> None: ...


class BookingOrchestrationRepository(Protocol):
    def transaction(self) -> AbstractAsyncContextManager[BookingOrchestrationTransaction]: ...


@dataclass(slots=True)
class BookingOrchestrationService:
    repository: BookingOrchestrationRepository
    booking_session_state_service: BookingSessionStateService
    slot_hold_state_service: SlotHoldStateService
    booking_state_service: BookingStateService
    waitlist_state_service: WaitlistStateService
    patient_resolution_service: BookingPatientResolutionService
    policy_resolver: PolicyResolver
    reminder_service: BookingReminderService | None = None

    async def _transition_session_within_transaction(
        self,
        *,
        tx: BookingOrchestrationTransaction,
        current: BookingSession,
        to_status: str,
        occurred_at: datetime,
        payload_json: dict[str, object] | None = None,
    ) -> BookingSession | None:
        try:
            transitioned = await self.booking_session_state_service.transition_session_in_transaction(
                tx=tx,
                current=current,
                to_status=to_status,
                payload_json=payload_json,
                occurred_at=occurred_at,
            )
        except InvalidSessionTransitionError:
            return None
        return transitioned.entity

    async def _advance_session_for_slot_selection(
        self,
        *,
        tx: BookingOrchestrationTransaction,
        session: BookingSession,
        contact_phone_snapshot: str | None,
        occurred_at: datetime,
    ) -> BookingSession | None:
        target = "awaiting_contact_confirmation" if contact_phone_snapshot is None else "in_progress"
        if session.status == target:
            return session

        current = session
        if target == "awaiting_contact_confirmation" and current.status != "awaiting_slot_selection":
            if current.status == "initiated":
                transitioned = await self._transition_session_within_transaction(
                    tx=tx, current=current, to_status="in_progress", occurred_at=occurred_at
                )
                if transitioned is None:
                    return None
                current = transitioned
            if current.status != "awaiting_slot_selection":
                transitioned = await self._transition_session_within_transaction(
                    tx=tx, current=current, to_status="awaiting_slot_selection", occurred_at=occurred_at
                )
                if transitioned is None:
                    return None
                current = transitioned
            transitioned = await self._transition_session_within_transaction(
                tx=tx, current=current, to_status="awaiting_contact_confirmation", occurred_at=occurred_at
            )
            return transitioned

        if target == "in_progress" and current.status == "review_ready":
            to_contact = await self._transition_session_within_transaction(
                tx=tx,
                current=current,
                to_status="awaiting_contact_confirmation",
                occurred_at=occurred_at,
            )
            if to_contact is None:
                return None
            current = to_contact

        transitioned = await self._transition_session_within_transaction(
            tx=tx, current=current, to_status=target, occurred_at=occurred_at
        )
        return transitioned

    async def start_booking_session(
        self, *, clinic_id: str, telegram_user_id: int, route_type: str, branch_id: str | None = None, expires_at: datetime | None = None
    ) -> OrchestrationSuccess[BookingSession]:
        now = datetime.now(timezone.utc)
        session = BookingSession(
            booking_session_id=f"bs_{uuid4().hex}",
            clinic_id=clinic_id,
            branch_id=branch_id,
            telegram_user_id=telegram_user_id,
            resolved_patient_id=None,
            status="initiated",
            route_type=route_type,
            service_id=None,
            urgency_type=None,
            requested_date_type=None,
            requested_date=None,
            time_window=None,
            doctor_preference_type=None,
            doctor_id=None,
            doctor_code_raw=None,
            selected_slot_id=None,
            selected_hold_id=None,
            contact_phone_snapshot=None,
            notes=None,
            expires_at=expires_at or (now + timedelta(minutes=30)),
            created_at=now,
            updated_at=now,
        )
        async with self.repository.transaction() as tx:
            await tx.upsert_booking_session(session)
        return OrchestrationSuccess(kind="success", entity=session)

    async def update_session_context(self, *, booking_session_id: str, **changes) -> BookingSessionOutcome:
        allowed = {
            "service_id",
            "urgency_type",
            "requested_date_type",
            "requested_date",
            "time_window",
            "doctor_preference_type",
            "doctor_id",
            "doctor_code_raw",
            "contact_phone_snapshot",
            "notes",
        }
        if any(key not in allowed for key in changes):
            return InvalidStateOutcome(kind="invalid_state", reason="update_session_context only accepts non-lifecycle context fields")

        async with self.repository.transaction() as tx:
            session = await tx.get_booking_session_for_update(booking_session_id)
            if session is None:
                return InvalidStateOutcome(kind="invalid_state", reason="booking session not found")
            updated = BookingSession(**{**asdict(session), **changes, "updated_at": datetime.now(timezone.utc)})
            await tx.upsert_booking_session(updated)
        return OrchestrationSuccess(kind="success", entity=updated)

    async def resolve_patient_for_session(
        self, *, booking_session_id: str, contact_type: str | None = None, contact_value: str | None = None, external_system: str | None = None, external_id: str | None = None
    ) -> BookingSessionOutcome:
        if contact_type and contact_value:
            resolution = await self.patient_resolution_service.resolve_by_exact_normalized_contact(
                contact_type=contact_type,
                contact_value=contact_value,
            )
        elif external_system and external_id:
            resolution = await self.patient_resolution_service.resolve_by_external_system_id(
                external_system=external_system,
                external_id=external_id,
            )
        else:
            return InvalidStateOutcome(kind="invalid_state", reason="patient resolution requires contact or external id input")

        if resolution.resolution_kind == "no_match":
            return NoMatchOutcome(kind="no_match", reason=resolution.match_reason)
        if resolution.resolution_kind == "ambiguous_match":
            return AmbiguousMatchOutcome(
                kind="ambiguous_match",
                reason=resolution.match_reason,
                candidate_patient_ids=tuple(candidate.patient_id for candidate in resolution.candidates),
            )

        patient_id = resolution.candidates[0].patient_id
        async with self.repository.transaction() as tx:
            session = await tx.get_booking_session_for_update(booking_session_id)
            if session is None:
                return InvalidStateOutcome(kind="invalid_state", reason="booking session not found")
            updated = BookingSession(**{**asdict(session), "resolved_patient_id": patient_id, "updated_at": datetime.now(timezone.utc)})
            await tx.upsert_booking_session(updated)
        return OrchestrationSuccess(kind="success", entity=updated)

    async def attach_resolved_patient_to_session(self, *, booking_session_id: str, patient_id: str) -> BookingSessionOutcome:
        async with self.repository.transaction() as tx:
            session = await tx.get_booking_session_for_update(booking_session_id)
            if session is None:
                return InvalidStateOutcome(kind="invalid_state", reason="booking session not found")
            updated = BookingSession(**{**asdict(session), "resolved_patient_id": patient_id, "updated_at": datetime.now(timezone.utc)})
            await tx.upsert_booking_session(updated)
        return OrchestrationSuccess(kind="success", entity=updated)

    async def select_slot_and_activate_hold(self, *, booking_session_id: str, slot_id: str, hold_ttl_minutes: int = 10) -> HoldOutcome:
        now = datetime.now(timezone.utc)
        async with self.repository.transaction() as tx:
            session = await tx.get_booking_session_for_update(booking_session_id)
            if session is None:
                return InvalidStateOutcome(kind="invalid_state", reason="booking session not found")
            slot = await tx.get_availability_slot_for_update(slot_id)
            if slot is None:
                return SlotUnavailableOutcome(kind="slot_unavailable", reason="slot does not exist")
            if slot.status != "open":
                return SlotUnavailableOutcome(kind="slot_unavailable", reason="slot is not bookable")
            if await tx.list_live_bookings_for_slot_for_update(slot_id=slot_id):
                return SlotUnavailableOutcome(kind="slot_unavailable", reason="slot already occupied by live booking")

            slot_active_holds = await tx.list_active_holds_for_slot_for_update(slot_id=slot_id)
            if any(hold.booking_session_id != booking_session_id for hold in slot_active_holds):
                return ConflictOutcome(kind="conflict", reason="slot already has an active hold")

            session_active_holds = await tx.list_active_holds_for_session_for_update(booking_session_id=booking_session_id)
            hold = next((h for h in session_active_holds if h.slot_id == slot_id), None)

            for stale_hold in session_active_holds:
                if hold is not None and stale_hold.slot_hold_id == hold.slot_hold_id:
                    continue
                try:
                    await self.slot_hold_state_service.transition_hold_in_transaction(
                        tx=tx,
                        current=stale_hold,
                        to_status="released",
                        session_event_name="slot_hold.released",
                        payload_json={"replaced_by_slot_id": slot_id},
                        occurred_at=now,
                    )
                except InvalidSlotHoldTransitionError:
                    return InvalidStateOutcome(kind="invalid_state", reason="active hold cannot be released for slot reselection")

            if hold is None:
                hold = await tx.find_slot_hold_for_update(slot_id=slot_id, booking_session_id=booking_session_id)
            if hold is not None and hold.status in TERMINAL_HOLD_STATUSES:
                hold = None
            if hold is None:
                hold = SlotHold(
                    slot_hold_id=f"bsh_{uuid4().hex}",
                    clinic_id=session.clinic_id,
                    slot_id=slot_id,
                    booking_session_id=booking_session_id,
                    telegram_user_id=session.telegram_user_id,
                    status="created",
                    expires_at=now + timedelta(minutes=hold_ttl_minutes),
                    created_at=now,
                )
                await tx.upsert_slot_hold(hold)

            if hold.status == "active":
                active_hold = hold
            else:
                try:
                    hold_transition = await self.slot_hold_state_service.transition_hold_in_transaction(
                        tx=tx,
                        current=hold,
                        to_status="active",
                        session_event_name="slot_hold.activated",
                        payload_json={"slot_id": slot_id},
                        occurred_at=now,
                    )
                except InvalidSlotHoldTransitionError:
                    return ConflictOutcome(kind="conflict", reason="hold cannot be activated from current status")
                active_hold = hold_transition.entity

            progressed_session = await self._advance_session_for_slot_selection(
                tx=tx,
                session=session,
                contact_phone_snapshot=session.contact_phone_snapshot,
                occurred_at=now,
            )
            if progressed_session is None:
                return InvalidStateOutcome(kind="invalid_state", reason="session cannot progress to slot-selection state canonically")
            updated_session = BookingSession(
                **{
                    **asdict(progressed_session),
                    "selected_slot_id": slot_id,
                    "selected_hold_id": active_hold.slot_hold_id,
                    "updated_at": now,
                }
            )
            await tx.upsert_booking_session(updated_session)
            return OrchestrationSuccess(kind="success", entity=active_hold)

    async def release_or_expire_hold_for_session(self, *, booking_session_id: str, action: str = "released") -> HoldOutcome:
        if action not in {"released", "expired"}:
            return InvalidStateOutcome(kind="invalid_state", reason="action must be released or expired")
        async with self.repository.transaction() as tx:
            session = await tx.get_booking_session_for_update(booking_session_id)
            if session is None or not session.selected_hold_id:
                return InvalidStateOutcome(kind="invalid_state", reason="session has no selected hold")
            hold = await tx.get_slot_hold_for_update(session.selected_hold_id)
            if hold is None:
                return InvalidStateOutcome(kind="invalid_state", reason="selected hold not found")
            try:
                transitioned = await self.slot_hold_state_service.transition_hold_in_transaction(
                    tx=tx,
                    current=hold,
                    to_status=action,
                    session_event_name=f"slot_hold.{action}",
                )
            except InvalidSlotHoldTransitionError:
                return InvalidStateOutcome(kind="invalid_state", reason=f"hold cannot transition to {action}")

            transitioned_session = await self._transition_session_within_transaction(
                tx=tx,
                current=session,
                to_status="awaiting_slot_selection",
                occurred_at=datetime.now(timezone.utc),
                payload_json={"hold_action": action},
            )
            if transitioned_session is None:
                return InvalidStateOutcome(kind="invalid_state", reason="session cannot transition to awaiting_slot_selection")

            updated_session = BookingSession(
                **{
                    **asdict(transitioned_session),
                    "selected_hold_id": None,
                    "selected_slot_id": None,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            await tx.upsert_booking_session(updated_session)
            return OrchestrationSuccess(kind="success", entity=transitioned.entity)

    async def mark_session_review_ready(self, *, booking_session_id: str) -> BookingSessionOutcome:
        async with self.repository.transaction() as tx:
            session = await tx.get_booking_session_for_update(booking_session_id)
            if session is None:
                return InvalidStateOutcome(kind="invalid_state", reason="booking session not found")
            if not session.selected_slot_id or not session.selected_hold_id:
                return InvalidStateOutcome(kind="invalid_state", reason="session requires selected slot and active hold")
            selected_hold = await tx.get_slot_hold_for_update(session.selected_hold_id)
            if selected_hold is None or selected_hold.booking_session_id != session.booking_session_id:
                return InvalidStateOutcome(kind="invalid_state", reason="selected hold is missing for this session")
            if selected_hold.status != "active":
                return InvalidStateOutcome(kind="invalid_state", reason="session requires selected active hold")
            if selected_hold.slot_id != session.selected_slot_id:
                return InvalidStateOutcome(kind="invalid_state", reason="selected hold does not match selected slot")
            if session.resolved_patient_id is None:
                return InvalidStateOutcome(kind="invalid_state", reason="session requires resolved patient")
            contact_required = bool(
                self.policy_resolver.resolve_policy(
                    "booking.contact_confirmation_required",
                    clinic_id=session.clinic_id,
                    branch_id=session.branch_id,
                )
            )
            if contact_required and not session.contact_phone_snapshot:
                return InvalidStateOutcome(kind="invalid_state", reason="contact confirmation required before review_ready")
            try:
                transitioned = await self.booking_session_state_service.transition_session_in_transaction(
                    tx=tx,
                    current=session,
                    to_status="review_ready",
                )
            except InvalidSessionTransitionError:
                return InvalidStateOutcome(kind="invalid_state", reason="session cannot move to review_ready")
            return OrchestrationSuccess(kind="success", entity=transitioned.entity)

    async def finalize_booking_from_session(self, *, booking_session_id: str) -> BookingOutcome:
        now = datetime.now(timezone.utc)
        async with self.repository.transaction() as tx:
            session = await tx.get_booking_session_for_update(booking_session_id)
            if session is None:
                return InvalidStateOutcome(kind="invalid_state", reason="booking session not found")
            if session.status != "review_ready":
                return InvalidStateOutcome(kind="invalid_state", reason="session is not review_ready")
            if session.resolved_patient_id is None:
                return InvalidStateOutcome(kind="invalid_state", reason="cannot finalize booking without resolved patient")
            if session.service_id is None:
                return InvalidStateOutcome(kind="invalid_state", reason="cannot finalize booking without selected service")
            if not session.selected_slot_id or not session.selected_hold_id:
                return InvalidStateOutcome(kind="invalid_state", reason="cannot finalize without selected slot and hold")

            hold = await tx.get_slot_hold_for_update(session.selected_hold_id)
            if hold is None or hold.booking_session_id != booking_session_id:
                return InvalidStateOutcome(kind="invalid_state", reason="session hold missing or not owned by session")
            if hold.status != "active":
                return InvalidStateOutcome(kind="invalid_state", reason="hold is not active")

            slot = await tx.get_availability_slot_for_update(session.selected_slot_id)
            if slot is None or slot.status != "open":
                return SlotUnavailableOutcome(kind="slot_unavailable", reason="selected slot is unavailable")
            if await tx.list_live_bookings_for_slot_for_update(slot_id=slot.slot_id):
                return ConflictOutcome(kind="conflict", reason="selected slot already has live booking")

            confirmation_required = bool(
                self.policy_resolver.resolve_policy(
                    "booking.confirmation_required",
                    clinic_id=session.clinic_id,
                    branch_id=session.branch_id,
                )
            )
            booking = Booking(
                booking_id=f"bk_{uuid4().hex}",
                clinic_id=session.clinic_id,
                branch_id=session.branch_id,
                patient_id=session.resolved_patient_id,
                doctor_id=slot.doctor_id,
                service_id=session.service_id,
                slot_id=slot.slot_id,
                booking_mode="patient_bot",
                source_channel="telegram",
                scheduled_start_at=slot.start_at,
                scheduled_end_at=slot.end_at,
                status="pending_confirmation",
                reason_for_visit_short=None,
                patient_note=session.notes,
                confirmation_required=confirmation_required,
                confirmed_at=None,
                canceled_at=None,
                checked_in_at=None,
                in_service_at=None,
                completed_at=None,
                no_show_at=None,
                created_at=now,
                updated_at=now,
            )
            await tx.upsert_booking(booking)
            await tx.append_outbox_event(
                build_event(
                    event_name="booking.created",
                    producer_context="booking.orchestration",
                    clinic_id=booking.clinic_id,
                    entity_type="booking",
                    entity_id=booking.booking_id,
                    occurred_at=now,
                    payload={"status": booking.status, "doctor_id": booking.doctor_id, "service_id": booking.service_id},
                )
            )
            await tx.append_booking_status_history(
                BookingStatusHistory(
                    booking_status_history_id=f"bsh_{uuid4().hex}",
                    booking_id=booking.booking_id,
                    old_status=None,
                    new_status="pending_confirmation",
                    reason_code="session_finalize",
                    actor_type="system",
                    actor_id=None,
                    occurred_at=now,
                )
            )
            await self.slot_hold_state_service.transition_hold_in_transaction(tx=tx, current=hold, to_status="consumed")
            await self.booking_session_state_service.transition_session_in_transaction(
                tx=tx,
                current=session,
                to_status="completed",
                payload_json={"booking_id": booking.booking_id},
            )
            await self._replace_reminder_plan_for_booking_in_transaction(
                tx=tx,
                booking=booking,
                reason_code="booking_finalized",
                now=now,
            )
            return OrchestrationSuccess(kind="success", entity=booking)

    async def cancel_session(self, *, booking_session_id: str) -> BookingSessionOutcome:
        async with self.repository.transaction() as tx:
            session = await tx.get_booking_session_for_update(booking_session_id)
            if session is None:
                return InvalidStateOutcome(kind="invalid_state", reason="booking session not found")
            active_holds = await tx.list_active_holds_for_session_for_update(booking_session_id=booking_session_id)
            for hold in active_holds:
                await self.slot_hold_state_service.transition_hold_in_transaction(tx=tx, current=hold, to_status="released")
            transitioned = await self.booking_session_state_service.transition_session_in_transaction(tx=tx, current=session, to_status="canceled")
            return OrchestrationSuccess(kind="success", entity=transitioned.entity)

    async def expire_session(self, *, booking_session_id: str) -> BookingSessionOutcome:
        async with self.repository.transaction() as tx:
            session = await tx.get_booking_session_for_update(booking_session_id)
            if session is None:
                return InvalidStateOutcome(kind="invalid_state", reason="booking session not found")
            active_holds = await tx.list_active_holds_for_session_for_update(booking_session_id=booking_session_id)
            for hold in active_holds:
                await self.slot_hold_state_service.transition_hold_in_transaction(tx=tx, current=hold, to_status="expired")
            transitioned = await self.booking_session_state_service.transition_session_in_transaction(tx=tx, current=session, to_status="expired")
            return OrchestrationSuccess(kind="success", entity=transitioned.entity)

    async def escalate_session_to_admin(self, *, booking_session_id: str, reason_code: str, priority: str = "normal") -> BookingSessionOutcome:
        async with self.repository.transaction() as tx:
            session = await tx.get_booking_session_for_update(booking_session_id)
            if session is None:
                return InvalidStateOutcome(kind="invalid_state", reason="booking session not found")
            escalation = AdminEscalation(
                admin_escalation_id=f"aes_{uuid4().hex}",
                clinic_id=session.clinic_id,
                booking_session_id=session.booking_session_id,
                patient_id=session.resolved_patient_id,
                reason_code=reason_code,
                priority=priority,
                status="open",
                assigned_to_actor_id=None,
                payload_summary={
                    "session_status": session.status,
                    "selected_slot_id": session.selected_slot_id,
                    "selected_hold_id": session.selected_hold_id,
                },
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            await tx.upsert_admin_escalation(escalation)
            transitioned = await self.booking_session_state_service.transition_session_in_transaction(
                tx=tx,
                current=session,
                to_status="admin_escalated",
            )
            return EscalatedOutcome(kind="escalated", reason=reason_code, escalation=escalation) if transitioned.changed else OrchestrationSuccess(kind="success", entity=session)

    async def create_waitlist_entry(
        self, *, clinic_id: str, service_id: str, branch_id: str | None = None, patient_id: str | None = None, telegram_user_id: int | None = None, source_session_id: str | None = None, requested_from: date | None = None, requested_to: date | None = None, time_window: str | None = None, notes: str | None = None
    ) -> WaitlistOutcome:
        now = datetime.now(timezone.utc)
        entry = WaitlistEntry(
            waitlist_entry_id=f"wle_{uuid4().hex}",
            clinic_id=clinic_id,
            branch_id=branch_id,
            patient_id=patient_id,
            telegram_user_id=telegram_user_id,
            service_id=service_id,
            doctor_id=None,
            date_window={"from": str(requested_from), "to": str(requested_to)} if requested_from or requested_to else None,
            time_window=time_window,
            priority=0,
            status="created",
            source_session_id=source_session_id,
            notes=notes,
            created_at=now,
            updated_at=now,
        )
        async with self.repository.transaction() as tx:
            await tx.upsert_waitlist_entry(entry)
            transitioned = await self.waitlist_state_service.transition_waitlist_entry_in_transaction(tx=tx, current=entry, to_status="active")
        return OrchestrationSuccess(kind="success", entity=transitioned.entity)

    async def request_booking_reschedule(self, *, booking_id: str, reason_code: str | None = None) -> BookingOutcome:
        async with self.repository.transaction() as tx:
            return await self.request_booking_reschedule_in_transaction(tx=tx, booking_id=booking_id, reason_code=reason_code)

    async def request_booking_reschedule_in_transaction(
        self,
        *,
        tx: BookingOrchestrationTransaction,
        booking_id: str,
        reason_code: str | None = None,
    ) -> BookingOutcome:
        booking = await tx.get_booking_for_update(booking_id)
        if booking is None:
            return InvalidStateOutcome(kind="invalid_state", reason="booking not found")
        try:
            transitioned = await self.booking_state_service.transition_booking_in_transaction(
                tx=tx, current=booking, to_status="reschedule_requested", reason_code=reason_code
            )
        except InvalidBookingTransitionError:
            return InvalidStateOutcome(kind="invalid_state", reason="booking cannot transition to reschedule_requested")
        transitioned_booking = transitioned.entity
        await self._cancel_reminders_for_booking_in_transaction(
            tx=tx,
            booking_id=booking_id,
            reason_code="booking_reschedule_requested",
        )
        return OrchestrationSuccess(kind="success", entity=transitioned_booking)

    async def confirm_booking(self, *, booking_id: str, reason_code: str | None = None) -> BookingOutcome:
        async with self.repository.transaction() as tx:
            return await self.confirm_booking_in_transaction(tx=tx, booking_id=booking_id, reason_code=reason_code)

    async def confirm_booking_in_transaction(
        self,
        *,
        tx: BookingOrchestrationTransaction,
        booking_id: str,
        reason_code: str | None = None,
    ) -> BookingOutcome:
        booking = await tx.get_booking_for_update(booking_id)
        if booking is None:
            return InvalidStateOutcome(kind="invalid_state", reason="booking not found")
        try:
            transitioned = await self.booking_state_service.transition_booking_in_transaction(
                tx=tx,
                current=booking,
                to_status="confirmed",
                reason_code=reason_code,
            )
        except InvalidBookingTransitionError:
            return InvalidStateOutcome(kind="invalid_state", reason="booking cannot transition to confirmed")
        return OrchestrationSuccess(kind="success", entity=transitioned.entity)

    async def cancel_booking(self, *, booking_id: str, reason_code: str | None = None) -> BookingOutcome:
        async with self.repository.transaction() as tx:
            return await self.cancel_booking_in_transaction(tx=tx, booking_id=booking_id, reason_code=reason_code)

    async def cancel_booking_in_transaction(
        self,
        *,
        tx: BookingOrchestrationTransaction,
        booking_id: str,
        reason_code: str | None = None,
    ) -> BookingOutcome:
        booking = await tx.get_booking_for_update(booking_id)
        if booking is None:
            return InvalidStateOutcome(kind="invalid_state", reason="booking not found")
        try:
            transitioned = await self.booking_state_service.transition_booking_in_transaction(
                tx=tx, current=booking, to_status="canceled", reason_code=reason_code
            )
        except InvalidBookingTransitionError:
            return InvalidStateOutcome(kind="invalid_state", reason="booking cannot transition to canceled")
        transitioned_booking = transitioned.entity
        await self._cancel_reminders_for_booking_in_transaction(
            tx=tx,
            booking_id=booking_id,
            reason_code="booking_canceled",
        )
        return OrchestrationSuccess(kind="success", entity=transitioned_booking)

    async def reschedule_booking(
        self,
        *,
        booking_id: str,
        scheduled_start_at: datetime,
        scheduled_end_at: datetime,
        reason_code: str | None = "booking_rescheduled",
    ) -> BookingOutcome:
        now = datetime.now(timezone.utc)
        async with self.repository.transaction() as tx:
            current = await tx.get_booking_for_update(booking_id)
            if current is None:
                return InvalidStateOutcome(kind="invalid_state", reason="booking not found")
            if scheduled_end_at <= scheduled_start_at:
                return InvalidStateOutcome(kind="invalid_state", reason="scheduled_end_at must be after scheduled_start_at")
            payload = asdict(current)
            payload["scheduled_start_at"] = scheduled_start_at
            payload["scheduled_end_at"] = scheduled_end_at
            payload["updated_at"] = now
            if payload["status"] == "reschedule_requested":
                payload["status"] = "confirmed"
                payload["confirmed_at"] = now
            updated_booking = Booking(**payload)
            await tx.upsert_booking(updated_booking)
            await tx.append_booking_status_history(
                BookingStatusHistory(
                    booking_status_history_id=f"bsh_{uuid4().hex}",
                    booking_id=updated_booking.booking_id,
                    old_status=current.status,
                    new_status=updated_booking.status,
                    reason_code=reason_code,
                    actor_type="system",
                    actor_id=None,
                    occurred_at=now,
                )
            )
            await tx.append_outbox_event(
                build_event(
                    event_name="booking.rescheduled",
                    producer_context="booking.orchestration",
                    clinic_id=updated_booking.clinic_id,
                    entity_type="booking",
                    entity_id=updated_booking.booking_id,
                    occurred_at=now,
                    payload={
                        "status": updated_booking.status,
                        "scheduled_start_at": updated_booking.scheduled_start_at.isoformat(),
                        "scheduled_end_at": updated_booking.scheduled_end_at.isoformat(),
                    },
                )
            )
            await self._replace_reminder_plan_for_booking_in_transaction(
                tx=tx,
                booking=updated_booking,
                reason_code="booking_rescheduled",
                now=now,
            )
            return OrchestrationSuccess(kind="success", entity=updated_booking)

    async def complete_booking_reschedule_from_session(
        self,
        *,
        booking_id: str,
        booking_session_id: str,
        reason_code: str | None = "booking_rescheduled",
    ) -> BookingOutcome:
        now = datetime.now(timezone.utc)
        async with self.repository.transaction() as tx:
            session = await tx.get_booking_session_for_update(booking_session_id)
            if session is None:
                return InvalidStateOutcome(kind="invalid_state", reason="booking session not found")
            if session.route_type != "reschedule_booking_control":
                return InvalidStateOutcome(kind="invalid_state", reason="session route type is not reschedule")
            if not session.selected_slot_id or not session.selected_hold_id:
                return InvalidStateOutcome(kind="invalid_state", reason="session requires selected slot and hold")
            if session.resolved_patient_id is None:
                return InvalidStateOutcome(kind="invalid_state", reason="session requires resolved patient")

            booking = await tx.get_booking_for_update(booking_id)
            if booking is None:
                return InvalidStateOutcome(kind="invalid_state", reason="booking not found")
            if booking.status not in {"reschedule_requested"}:
                return InvalidStateOutcome(kind="invalid_state", reason="booking status is not eligible for reschedule completion")
            if booking.clinic_id != session.clinic_id:
                return InvalidStateOutcome(kind="invalid_state", reason="booking and session clinic mismatch")
            if booking.patient_id != session.resolved_patient_id:
                return InvalidStateOutcome(kind="invalid_state", reason="booking and session patient mismatch")

            hold = await tx.get_slot_hold_for_update(session.selected_hold_id)
            if hold is None or hold.booking_session_id != booking_session_id:
                return InvalidStateOutcome(kind="invalid_state", reason="selected hold is missing for this session")
            if hold.status != "active":
                return InvalidStateOutcome(kind="invalid_state", reason="selected hold is not active")
            if hold.slot_id != session.selected_slot_id:
                return InvalidStateOutcome(kind="invalid_state", reason="selected hold does not match selected slot")

            slot = await tx.get_availability_slot_for_update(session.selected_slot_id)
            if slot is None or slot.status != "open":
                return SlotUnavailableOutcome(kind="slot_unavailable", reason="selected slot is unavailable")
            if await tx.list_live_bookings_for_slot_for_update(slot_id=slot.slot_id):
                return ConflictOutcome(kind="conflict", reason="selected slot already has live booking")

            payload = asdict(booking)
            payload["slot_id"] = slot.slot_id
            payload["scheduled_start_at"] = slot.start_at
            payload["scheduled_end_at"] = slot.end_at
            payload["doctor_id"] = slot.doctor_id
            payload["branch_id"] = slot.branch_id
            payload["updated_at"] = now
            if payload["status"] == "reschedule_requested":
                payload["status"] = "confirmed"
                payload["confirmed_at"] = now
            updated_booking = Booking(**payload)
            await tx.upsert_booking(updated_booking)
            await tx.append_booking_status_history(
                BookingStatusHistory(
                    booking_status_history_id=f"bsh_{uuid4().hex}",
                    booking_id=updated_booking.booking_id,
                    old_status=booking.status,
                    new_status=updated_booking.status,
                    reason_code=reason_code,
                    actor_type="system",
                    actor_id=None,
                    occurred_at=now,
                )
            )
            await tx.append_outbox_event(
                build_event(
                    event_name="booking.rescheduled",
                    producer_context="booking.orchestration",
                    clinic_id=updated_booking.clinic_id,
                    entity_type="booking",
                    entity_id=updated_booking.booking_id,
                    occurred_at=now,
                    payload={
                        "status": updated_booking.status,
                        "slot_id": updated_booking.slot_id,
                        "scheduled_start_at": updated_booking.scheduled_start_at.isoformat(),
                        "scheduled_end_at": updated_booking.scheduled_end_at.isoformat(),
                    },
                )
            )
            await self.slot_hold_state_service.transition_hold_in_transaction(tx=tx, current=hold, to_status="consumed")
            await self._replace_reminder_plan_for_booking_in_transaction(
                tx=tx,
                booking=updated_booking,
                reason_code="booking_rescheduled",
                now=now,
            )
            return OrchestrationSuccess(kind="success", entity=updated_booking)

    async def complete_booking(self, *, booking_id: str, reason_code: str | None = None) -> BookingOutcome:
        return await self._transition_booking_and_cancel_reminders(booking_id=booking_id, to_status="completed", reason_code=reason_code or "booking_completed")

    async def mark_booking_no_show(self, *, booking_id: str, reason_code: str | None = None) -> BookingOutcome:
        return await self._transition_booking_and_cancel_reminders(booking_id=booking_id, to_status="no_show", reason_code=reason_code or "booking_no_show")

    async def _transition_booking_and_cancel_reminders(self, *, booking_id: str, to_status: str, reason_code: str) -> BookingOutcome:
        async with self.repository.transaction() as tx:
            booking = await tx.get_booking_for_update(booking_id)
            if booking is None:
                return InvalidStateOutcome(kind="invalid_state", reason="booking not found")
            try:
                transitioned = await self.booking_state_service.transition_booking_in_transaction(
                    tx=tx, current=booking, to_status=to_status, reason_code=reason_code
                )
            except InvalidBookingTransitionError:
                return InvalidStateOutcome(kind="invalid_state", reason=f"booking cannot transition to {to_status}")
            transitioned_booking = transitioned.entity
            await self._cancel_reminders_for_booking_in_transaction(tx=tx, booking_id=booking_id, reason_code=reason_code)
            if to_status == "completed":
                await self._plan_post_visit_recall_in_transaction(
                    tx=tx,
                    booking=transitioned_booking,
                    now=datetime.now(timezone.utc),
                )
            return OrchestrationSuccess(kind="success", entity=transitioned_booking)

    async def _replace_reminder_plan_for_booking_in_transaction(
        self,
        *,
        tx: BookingOrchestrationTransaction,
        booking: Booking,
        reason_code: str,
        now: datetime,
    ) -> None:
        if self.reminder_service is None:
            return
        await self.reminder_service.replace_booking_reminder_plan_in_transaction(
            tx=tx,
            booking=booking,
            reason_code=reason_code,
            now=now,
        )

    async def _cancel_reminders_for_booking_in_transaction(
        self,
        *,
        tx: BookingOrchestrationTransaction,
        booking_id: str,
        reason_code: str,
    ) -> None:
        if self.reminder_service is None:
            return
        await self.reminder_service.cancel_booking_reminder_plan_in_transaction(
            tx=tx,
            booking_id=booking_id,
            reason_code=reason_code,
        )

    async def _plan_post_visit_recall_in_transaction(
        self,
        *,
        tx: BookingOrchestrationTransaction,
        booking: Booking,
        now: datetime,
    ) -> None:
        if self.reminder_service is None:
            return
        await self.reminder_service.plan_post_visit_recall_in_transaction(
            tx=tx,
            booking=booking,
            now=now,
        )
