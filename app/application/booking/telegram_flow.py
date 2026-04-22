from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.application.booking.orchestration import BookingOrchestrationService
from app.application.booking.orchestration_outcomes import (
    AmbiguousMatchOutcome,
    ConflictOutcome,
    InvalidStateOutcome,
    NoMatchOutcome,
    OrchestrationSuccess,
    SlotUnavailableOutcome,
)
from app.application.clinic_reference import ClinicReferenceService
from app.domain.booking import AdminEscalation, AvailabilitySlot, Booking, BookingSession
from app.domain.clinic_reference.models import Branch, Doctor, Service
from app.interfaces.cards import BookingRuntimeSnapshot

ACTIVE_SESSION_STATUSES: tuple[str, ...] = (
    "initiated",
    "in_progress",
    "awaiting_slot_selection",
    "awaiting_contact_confirmation",
    "review_ready",
)
NEW_BOOKING_ROUTE_TYPES: frozenset[str] = frozenset({"service_first"})
EXISTING_BOOKING_CONTROL_ROUTE_TYPES: frozenset[str] = frozenset({"existing_booking_control"})
RESCHEDULE_BOOKING_CONTROL_ROUTE_TYPES: frozenset[str] = frozenset({"reschedule_booking_control"})
LIVE_EXISTING_BOOKING_STATUSES: frozenset[str] = frozenset({"pending_confirmation", "confirmed", "reschedule_requested", "checked_in", "in_service"})


class BookingFlowReadRepository(Protocol):
    async def get_booking_session(self, booking_session_id: str) -> BookingSession | None: ...
    async def get_availability_slot(self, slot_id: str) -> AvailabilitySlot | None: ...
    async def list_active_sessions_for_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> list[BookingSession]: ...
    async def list_open_slots(
        self,
        *,
        clinic_id: str,
        start_at: datetime,
        end_at: datetime,
        doctor_id: str | None,
        branch_id: str | None,
        limit: int,
    ) -> list[AvailabilitySlot]: ...
    async def list_open_admin_escalations(self, *, clinic_id: str, limit: int) -> list[AdminEscalation]: ...
    async def list_recent_bookings_by_statuses(self, *, clinic_id: str, statuses: tuple[str, ...], limit: int) -> list[Booking]: ...
    async def list_bookings_by_patient(self, *, patient_id: str) -> list[Booking]: ...
    async def get_booking(self, booking_id: str) -> Booking | None: ...


class CanonicalPatientCreator(Protocol):
    async def create_minimal_patient(self, *, clinic_id: str, display_name: str, phone: str) -> str: ...
    async def upsert_telegram_contact(self, *, patient_id: str, telegram_user_id: int) -> None: ...


@dataclass(slots=True, frozen=True)
class PatientResolutionFlowResult:
    kind: str
    booking_session: BookingSession | None = None
    escalation: AdminEscalation | None = None


@dataclass(slots=True, frozen=True)
class BookingResumePanel:
    panel_key: str
    booking_session: BookingSession


@dataclass(slots=True, frozen=True)
class BookingControlResolutionResult:
    kind: str
    bookings: tuple[Booking, ...] = ()
    booking_session: BookingSession | None = None


@dataclass(slots=True, frozen=True)
class ReturningPatientStartResult:
    booking_session: BookingSession
    trusted_shortcut_applied: bool = False


@dataclass(slots=True, frozen=True)
class ExistingBookingControlValidationResult:
    kind: str
    booking_session: BookingSession | None = None
    booking: Booking | None = None


@dataclass(slots=True, frozen=True)
class ExistingBookingControlStartResult:
    kind: str
    booking_session: BookingSession | None = None
    booking: Booking | None = None


@dataclass(slots=True, frozen=True)
class BookingCardView:
    booking_id: str
    doctor_label: str
    service_label: str
    datetime_label: str
    branch_label: str
    status_label: str
    next_step_key: str


@dataclass(slots=True)
class BookingPatientFlowService:
    orchestration: BookingOrchestrationService
    reads: BookingFlowReadRepository
    reference: ClinicReferenceService
    patient_creator: CanonicalPatientCreator

    async def start_or_resume_session(self, *, clinic_id: str, telegram_user_id: int, branch_id: str | None = None) -> BookingSession:
        latest = await self._latest_active_session(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            allowed_route_types=NEW_BOOKING_ROUTE_TYPES,
        )
        if latest is not None:
            return latest
        started = await self.orchestration.start_booking_session(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            route_type="service_first",
            branch_id=branch_id,
        )
        return started.entity

    async def start_or_resume_returning_patient_booking(
        self,
        *,
        clinic_id: str,
        telegram_user_id: int,
        branch_id: str | None = None,
        trusted_patient_id: str | None = None,
        trusted_phone_snapshot: str | None = None,
    ) -> ReturningPatientStartResult:
        latest = await self._latest_active_session(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            allowed_route_types=NEW_BOOKING_ROUTE_TYPES,
        )
        if latest is not None:
            return ReturningPatientStartResult(booking_session=latest, trusted_shortcut_applied=False)

        started = await self.orchestration.start_booking_session(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            route_type="service_first",
            branch_id=branch_id,
        )
        session = started.entity

        if not trusted_patient_id or not trusted_phone_snapshot:
            return ReturningPatientStartResult(booking_session=session, trusted_shortcut_applied=False)

        attached = await self.orchestration.attach_resolved_patient_to_session(
            booking_session_id=session.booking_session_id,
            patient_id=trusted_patient_id,
        )
        if not isinstance(attached, OrchestrationSuccess):
            return ReturningPatientStartResult(booking_session=session, trusted_shortcut_applied=False)

        hydrated = await self.orchestration.update_session_context(
            booking_session_id=session.booking_session_id,
            contact_phone_snapshot=trusted_phone_snapshot,
        )
        if not isinstance(hydrated, OrchestrationSuccess):
            return ReturningPatientStartResult(booking_session=attached.entity, trusted_shortcut_applied=False)

        return ReturningPatientStartResult(booking_session=hydrated.entity, trusted_shortcut_applied=True)

    async def start_or_resume_existing_booking_session(self, *, clinic_id: str, telegram_user_id: int) -> BookingSession:
        latest = await self._latest_active_session(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            allowed_route_types=EXISTING_BOOKING_CONTROL_ROUTE_TYPES,
        )
        if latest is not None:
            return latest
        started = await self.orchestration.start_booking_session(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            route_type="existing_booking_control",
        )
        return started.entity

    async def start_new_existing_booking_session(self, *, clinic_id: str, telegram_user_id: int) -> BookingSession:
        started = await self.orchestration.start_booking_session(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            route_type="existing_booking_control",
        )
        return started.entity

    async def start_existing_booking_control_for_booking(
        self,
        *,
        clinic_id: str,
        telegram_user_id: int,
        booking_id: str,
    ) -> ExistingBookingControlStartResult:
        booking = await self.reads.get_booking(booking_id)
        if booking is None:
            return ExistingBookingControlStartResult(kind="booking_missing")
        if booking.clinic_id != clinic_id:
            return ExistingBookingControlStartResult(kind="clinic_mismatch", booking=booking)
        session = await self.start_new_existing_booking_session(clinic_id=clinic_id, telegram_user_id=telegram_user_id)
        attached = await self.orchestration.attach_resolved_patient_to_session(
            booking_session_id=session.booking_session_id,
            patient_id=booking.patient_id,
        )
        if not isinstance(attached, OrchestrationSuccess):
            return ExistingBookingControlStartResult(kind="session_attach_failed", booking=booking)
        return ExistingBookingControlStartResult(kind="ready", booking_session=attached.entity, booking=booking)

    async def start_patient_reschedule_session(
        self,
        *,
        clinic_id: str,
        telegram_user_id: int,
        booking_id: str,
    ) -> ExistingBookingControlStartResult:
        booking = await self.reads.get_booking(booking_id)
        if booking is None:
            return ExistingBookingControlStartResult(kind="booking_missing")
        if booking.clinic_id != clinic_id:
            return ExistingBookingControlStartResult(kind="clinic_mismatch", booking=booking)
        if not booking.doctor_id:
            return ExistingBookingControlStartResult(kind="session_prefill_failed", booking=booking)
        started = await self.orchestration.start_booking_session(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            route_type="reschedule_booking_control",
            branch_id=booking.branch_id,
        )
        session = started.entity
        attached = await self.orchestration.attach_resolved_patient_to_session(
            booking_session_id=session.booking_session_id,
            patient_id=booking.patient_id,
        )
        if not isinstance(attached, OrchestrationSuccess):
            return ExistingBookingControlStartResult(kind="session_attach_failed", booking=booking)
        prefilled = await self.orchestration.update_session_context(
            booking_session_id=attached.entity.booking_session_id,
            service_id=booking.service_id,
            doctor_preference_type="specific",
            doctor_id=booking.doctor_id,
        )
        if not isinstance(prefilled, OrchestrationSuccess):
            return ExistingBookingControlStartResult(kind="session_prefill_failed", booking=booking)
        return ExistingBookingControlStartResult(kind="ready", booking_session=prefilled.entity, booking=booking)

    async def determine_resume_panel(self, *, booking_session_id: str) -> BookingResumePanel | None:
        session = await self.reads.get_booking_session(booking_session_id)
        if session is None:
            return None
        return BookingResumePanel(panel_key=self._panel_for_session(session), booking_session=session)

    async def validate_active_session_callback(
        self,
        *,
        clinic_id: str,
        telegram_user_id: int,
        callback_session_id: str,
        allowed_route_types: frozenset[str] = NEW_BOOKING_ROUTE_TYPES,
    ) -> bool:
        latest = await self._latest_active_session(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            allowed_route_types=allowed_route_types,
        )
        if latest is None:
            return False
        return latest.booking_session_id == callback_session_id

    def list_services(self, *, clinic_id: str) -> list[Service]:
        return sorted(self.reference.list_services(clinic_id), key=lambda service: service.code)

    def list_doctors(self, *, clinic_id: str, branch_id: str | None = None) -> list[Doctor]:
        doctors = [doctor for doctor in self.reference.list_doctors(clinic_id, branch_id) if doctor.public_booking_enabled]
        return sorted(doctors, key=lambda row: row.display_name)

    async def update_service(self, *, booking_session_id: str, service_id: str) -> BookingSession:
        updated = await self.orchestration.update_session_context(booking_session_id=booking_session_id, service_id=service_id)
        if isinstance(updated, OrchestrationSuccess):
            return updated.entity
        raise ValueError(updated.reason)

    async def update_doctor_preference(
        self,
        *,
        booking_session_id: str,
        doctor_preference_type: str,
        doctor_id: str | None = None,
    ) -> BookingSession:
        updated = await self.orchestration.update_session_context(
            booking_session_id=booking_session_id,
            doctor_preference_type=doctor_preference_type,
            doctor_id=doctor_id,
        )
        if isinstance(updated, OrchestrationSuccess):
            return updated.entity
        raise ValueError(updated.reason)

    async def list_slots_for_session(self, *, booking_session_id: str, limit: int = 5) -> list[AvailabilitySlot]:
        session = await self.reads.get_booking_session(booking_session_id)
        if session is None:
            return []
        window_start = datetime.now(timezone.utc) - timedelta(minutes=1)
        window_end = window_start + timedelta(days=30)
        slots = await self.reads.list_open_slots(
            clinic_id=session.clinic_id,
            start_at=window_start,
            end_at=window_end,
            doctor_id=session.doctor_id if session.doctor_preference_type == "specific" else None,
            branch_id=session.branch_id,
            limit=limit * 5,
        )
        filtered = [slot for slot in slots if self._slot_matches_service(slot, service_id=session.service_id)]
        return sorted(filtered, key=lambda row: row.start_at)[:limit]

    async def select_slot(self, *, booking_session_id: str, slot_id: str):
        return await self.orchestration.select_slot_and_activate_hold(booking_session_id=booking_session_id, slot_id=slot_id)

    async def set_contact_phone(self, *, booking_session_id: str, phone: str) -> BookingSession:
        updated = await self.orchestration.update_session_context(
            booking_session_id=booking_session_id,
            contact_phone_snapshot=phone,
        )
        if isinstance(updated, OrchestrationSuccess):
            return updated.entity
        raise ValueError(updated.reason)

    async def resolve_patient_for_new_booking_contact(
        self,
        *,
        booking_session_id: str,
        phone: str,
        fallback_display_name: str,
    ) -> PatientResolutionFlowResult:
        outcome = await self.orchestration.resolve_patient_for_session(
            booking_session_id=booking_session_id,
            contact_type="phone",
            contact_value=phone,
        )
        if isinstance(outcome, OrchestrationSuccess):
            session = await self.reads.get_booking_session(booking_session_id)
            if session is not None and outcome.entity.resolved_patient_id is not None:
                await self.patient_creator.upsert_telegram_contact(
                    patient_id=outcome.entity.resolved_patient_id,
                    telegram_user_id=session.telegram_user_id,
                )
            return PatientResolutionFlowResult(kind="exact_match", booking_session=outcome.entity)

        if isinstance(outcome, NoMatchOutcome):
            session = await self.reads.get_booking_session(booking_session_id)
            if session is None:
                return PatientResolutionFlowResult(kind="invalid_state")
            created_patient_id = await self.patient_creator.create_minimal_patient(
                clinic_id=session.clinic_id,
                display_name=fallback_display_name,
                phone=phone,
            )
            attached = await self.orchestration.attach_resolved_patient_to_session(
                booking_session_id=booking_session_id,
                patient_id=created_patient_id,
            )
            if isinstance(attached, OrchestrationSuccess):
                await self.patient_creator.upsert_telegram_contact(
                    patient_id=created_patient_id,
                    telegram_user_id=session.telegram_user_id,
                )
                return PatientResolutionFlowResult(kind="new_patient_created", booking_session=attached.entity)
            return PatientResolutionFlowResult(kind="invalid_state")
        if isinstance(outcome, AmbiguousMatchOutcome):
            escalation = await self.orchestration.escalate_session_to_admin(
                booking_session_id=booking_session_id,
                reason_code="ambiguous_exact_contact",
                priority="high",
            )
            if escalation.kind == "escalated":
                return PatientResolutionFlowResult(kind="ambiguous_escalated", escalation=escalation.escalation)
            return PatientResolutionFlowResult(kind="ambiguous_escalated")
        return PatientResolutionFlowResult(kind="invalid_state")

    async def resolve_patient_for_existing_booking_contact(
        self,
        *,
        booking_session_id: str,
        phone: str,
    ) -> PatientResolutionFlowResult:
        outcome = await self.orchestration.resolve_patient_for_session(
            booking_session_id=booking_session_id,
            contact_type="phone",
            contact_value=phone,
        )
        if isinstance(outcome, OrchestrationSuccess):
            session = await self.reads.get_booking_session(booking_session_id)
            if session is not None and outcome.entity.resolved_patient_id is not None:
                await self.patient_creator.upsert_telegram_contact(
                    patient_id=outcome.entity.resolved_patient_id,
                    telegram_user_id=session.telegram_user_id,
                )
            return PatientResolutionFlowResult(kind="exact_match", booking_session=outcome.entity)
        if isinstance(outcome, NoMatchOutcome):
            session = await self.reads.get_booking_session(booking_session_id)
            return PatientResolutionFlowResult(kind="no_match", booking_session=session)
        if isinstance(outcome, AmbiguousMatchOutcome):
            escalation = await self.orchestration.escalate_session_to_admin(
                booking_session_id=booking_session_id,
                reason_code="ambiguous_exact_contact",
                priority="high",
            )
            if escalation.kind == "escalated":
                return PatientResolutionFlowResult(kind="ambiguous_escalated", escalation=escalation.escalation)
            return PatientResolutionFlowResult(kind="ambiguous_escalated")
        return PatientResolutionFlowResult(kind="invalid_state")

    async def resolve_patient_from_contact(
        self,
        *,
        booking_session_id: str,
        phone: str,
        fallback_display_name: str,
    ) -> PatientResolutionFlowResult:
        return await self.resolve_patient_for_new_booking_contact(
            booking_session_id=booking_session_id,
            phone=phone,
            fallback_display_name=fallback_display_name,
        )

    async def mark_review_ready(self, *, booking_session_id: str):
        return await self.orchestration.mark_session_review_ready(booking_session_id=booking_session_id)

    async def finalize(self, *, booking_session_id: str):
        return await self.orchestration.finalize_booking_from_session(booking_session_id=booking_session_id)

    async def get_booking_session(self, *, booking_session_id: str) -> BookingSession | None:
        return await self.reads.get_booking_session(booking_session_id)

    async def get_availability_slot(self, *, slot_id: str) -> AvailabilitySlot | None:
        return await self.reads.get_availability_slot(slot_id)

    async def get_booking(self, *, booking_id: str) -> Booking | None:
        return await self.reads.get_booking(booking_id)

    async def list_admin_escalations(self, *, clinic_id: str, limit: int = 10) -> list[AdminEscalation]:
        return await self.reads.list_open_admin_escalations(clinic_id=clinic_id, limit=limit)

    async def list_admin_new_bookings(self, *, clinic_id: str, limit: int = 10) -> list[Booking]:
        return await self.reads.list_recent_bookings_by_statuses(
            clinic_id=clinic_id,
            statuses=("pending_confirmation", "confirmed"),
            limit=limit,
        )

    async def resolve_existing_booking_for_known_patient(
        self,
        *,
        clinic_id: str,
        telegram_user_id: int,
        patient_id: str,
    ) -> BookingControlResolutionResult:
        session = await self.start_new_existing_booking_session(clinic_id=clinic_id, telegram_user_id=telegram_user_id)
        attached = await self.orchestration.attach_resolved_patient_to_session(
            booking_session_id=session.booking_session_id,
            patient_id=patient_id,
        )
        if not isinstance(attached, OrchestrationSuccess):
            return BookingControlResolutionResult(kind="invalid_state", booking_session=session)
        bookings = await self.reads.list_bookings_by_patient(patient_id=patient_id)
        live = tuple(sorted([row for row in bookings if row.status in LIVE_EXISTING_BOOKING_STATUSES], key=lambda row: row.scheduled_start_at))
        if not live:
            return BookingControlResolutionResult(kind="no_match", booking_session=attached.entity)
        return BookingControlResolutionResult(kind="exact_match", bookings=live, booking_session=attached.entity)

    async def resolve_existing_booking_by_contact(
        self,
        *,
        clinic_id: str,
        telegram_user_id: int,
        phone: str,
    ) -> BookingControlResolutionResult:
        session = await self.start_new_existing_booking_session(clinic_id=clinic_id, telegram_user_id=telegram_user_id)
        resolution = await self.resolve_patient_for_existing_booking_contact(
            booking_session_id=session.booking_session_id,
            phone=phone,
        )
        if resolution.kind == "no_match":
            return BookingControlResolutionResult(kind="no_match", booking_session=resolution.booking_session or session)
        if resolution.kind == "ambiguous_escalated":
            guard_session = await self.start_new_existing_booking_session(
                clinic_id=clinic_id,
                telegram_user_id=telegram_user_id,
            )
            return BookingControlResolutionResult(kind="ambiguous_escalated", booking_session=guard_session)
        if resolution.kind == "invalid_state":
            return BookingControlResolutionResult(kind="invalid_state", booking_session=session)
        resolved_session = resolution.booking_session
        if resolved_session is None or resolved_session.resolved_patient_id is None:
            return BookingControlResolutionResult(kind="invalid_state", booking_session=session)
        bookings = await self.reads.list_bookings_by_patient(patient_id=resolved_session.resolved_patient_id)
        live = tuple(sorted([row for row in bookings if row.status in LIVE_EXISTING_BOOKING_STATUSES], key=lambda row: row.scheduled_start_at))
        if not live:
            return BookingControlResolutionResult(kind="no_match", booking_session=resolved_session)
        return BookingControlResolutionResult(kind="exact_match", bookings=live, booking_session=resolved_session)

    async def validate_existing_booking_control_action(
        self,
        *,
        clinic_id: str,
        telegram_user_id: int,
        callback_session_id: str,
        booking_id: str,
        allowed_statuses: set[str] | None = None,
    ) -> ExistingBookingControlValidationResult:
        active = await self.reads.list_active_sessions_for_telegram_user(clinic_id=clinic_id, telegram_user_id=telegram_user_id)
        latest = self._latest_for_route_types(active, allowed_route_types=EXISTING_BOOKING_CONTROL_ROUTE_TYPES)
        if latest is None:
            return ExistingBookingControlValidationResult(kind="missing_session")
        if latest.booking_session_id != callback_session_id:
            return ExistingBookingControlValidationResult(kind="stale_or_mismatched_session", booking_session=latest)
        if not latest.resolved_patient_id:
            return ExistingBookingControlValidationResult(kind="missing_resolved_patient", booking_session=latest)
        booking = await self.reads.get_booking(booking_id)
        if booking is None:
            return ExistingBookingControlValidationResult(kind="booking_not_found", booking_session=latest)
        if booking.patient_id != latest.resolved_patient_id:
            return ExistingBookingControlValidationResult(kind="booking_patient_mismatch", booking_session=latest, booking=booking)
        if allowed_statuses is not None and booking.status not in allowed_statuses:
            return ExistingBookingControlValidationResult(kind="booking_ineligible", booking_session=latest, booking=booking)
        return ExistingBookingControlValidationResult(kind="valid", booking_session=latest, booking=booking)

    async def request_reschedule(self, *, clinic_id: str, telegram_user_id: int, callback_session_id: str, booking_id: str):
        validation = await self.validate_existing_booking_control_action(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            callback_session_id=callback_session_id,
            booking_id=booking_id,
            allowed_statuses={"pending_confirmation", "confirmed", "checked_in", "in_service"},
        )
        if validation.kind != "valid":
            return InvalidStateOutcome(kind="invalid_state", reason=validation.kind)
        return await self.orchestration.request_booking_reschedule(booking_id=booking_id, reason_code="patient_requested")

    async def complete_patient_reschedule(
        self,
        *,
        clinic_id: str,
        telegram_user_id: int,
        callback_session_id: str,
        source_booking_id: str,
    ):
        session = await self.reads.get_booking_session(callback_session_id)
        if session is None:
            return InvalidStateOutcome(kind="invalid_state", reason="session_missing")
        if session.clinic_id != clinic_id or session.telegram_user_id != telegram_user_id:
            return InvalidStateOutcome(kind="invalid_state", reason="session_scope_mismatch")
        if session.route_type not in RESCHEDULE_BOOKING_CONTROL_ROUTE_TYPES:
            return InvalidStateOutcome(kind="invalid_state", reason="session_route_mismatch")
        if not session.selected_slot_id or not session.selected_hold_id:
            return InvalidStateOutcome(kind="invalid_state", reason="missing_selected_slot_or_hold")
        if session.resolved_patient_id is None:
            return InvalidStateOutcome(kind="invalid_state", reason="missing_resolved_patient")

        source_booking = await self.reads.get_booking(source_booking_id)
        if source_booking is None:
            return InvalidStateOutcome(kind="invalid_state", reason="source_booking_missing")
        if source_booking.clinic_id != clinic_id:
            return InvalidStateOutcome(kind="invalid_state", reason="source_booking_clinic_mismatch")
        if source_booking.patient_id != session.resolved_patient_id:
            return InvalidStateOutcome(kind="invalid_state", reason="source_booking_patient_mismatch")
        if source_booking.service_id != (session.service_id or ""):
            return InvalidStateOutcome(kind="invalid_state", reason="source_booking_service_mismatch")
        if source_booking.doctor_id != (session.doctor_id or ""):
            return InvalidStateOutcome(kind="invalid_state", reason="source_booking_doctor_mismatch")
        if source_booking.branch_id != (session.branch_id or ""):
            return InvalidStateOutcome(kind="invalid_state", reason="source_booking_branch_mismatch")

        return await self.orchestration.complete_booking_reschedule_from_session(
            booking_id=source_booking_id,
            booking_session_id=callback_session_id,
            reason_code="patient_reschedule_completed",
        )

    async def confirm_existing_booking(self, *, clinic_id: str, telegram_user_id: int, callback_session_id: str, booking_id: str):
        validation = await self.validate_existing_booking_control_action(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            callback_session_id=callback_session_id,
            booking_id=booking_id,
            allowed_statuses={"pending_confirmation"},
        )
        if validation.kind != "valid":
            return InvalidStateOutcome(kind="invalid_state", reason=validation.kind)
        return await self.orchestration.confirm_booking(booking_id=booking_id, reason_code="patient_confirmed")

    async def cancel_booking(self, *, clinic_id: str, telegram_user_id: int, callback_session_id: str, booking_id: str):
        validation = await self.validate_existing_booking_control_action(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            callback_session_id=callback_session_id,
            booking_id=booking_id,
            allowed_statuses={"pending_confirmation", "confirmed", "reschedule_requested", "checked_in", "in_service"},
        )
        if validation.kind != "valid":
            return InvalidStateOutcome(kind="invalid_state", reason=validation.kind)
        return await self.orchestration.cancel_booking(booking_id=booking_id, reason_code="patient_requested")

    async def join_earlier_slot_waitlist(self, *, clinic_id: str, telegram_user_id: int, callback_session_id: str, booking_id: str):
        validation = await self.validate_existing_booking_control_action(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            callback_session_id=callback_session_id,
            booking_id=booking_id,
            allowed_statuses={"pending_confirmation", "confirmed", "reschedule_requested", "checked_in", "in_service"},
        )
        if validation.kind != "valid" or validation.booking is None:
            return InvalidStateOutcome(kind="invalid_state", reason=validation.kind)
        booking = validation.booking
        return await self.orchestration.create_waitlist_entry(
            clinic_id=booking.clinic_id,
            service_id=booking.service_id,
            branch_id=booking.branch_id,
            patient_id=booking.patient_id,
            telegram_user_id=telegram_user_id,
            notes=f"earlier_slot_for:{booking.booking_id}",
        )

    def build_booking_card(self, *, booking: Booking) -> BookingCardView:
        branch = self._branch_by_id(booking.clinic_id).get(booking.branch_id or "")
        doctor = self._doctor_by_id(booking.clinic_id).get(booking.doctor_id)
        service = self._service_by_id(booking.clinic_id).get(booking.service_id)
        timezone_name = self._resolve_timezone_name(clinic_id=booking.clinic_id, branch_id=booking.branch_id)
        zone = self._zone_or_utc(timezone_name)
        return BookingCardView(
            booking_id=booking.booking_id,
            doctor_label=doctor.display_name if doctor else booking.doctor_id,
            service_label=self._service_label(service, booking.service_id),
            datetime_label=booking.scheduled_start_at.astimezone(zone).strftime("%Y-%m-%d %H:%M %Z"),
            branch_label=branch.display_name if branch else (booking.branch_id or "-"),
            status_label=f"booking.status.{booking.status}",
            next_step_key=self._next_step_key_for_booking(booking.status),
        )

    def build_booking_snapshot(
        self,
        *,
        booking: Booking,
        role_variant: str,
        state_token: str | None = None,
        patient_label: str | None = None,
        patient_contact: str | None = None,
        chart_summary_entry: str | None = None,
        recommendation_summary: str | None = None,
        care_order_summary: str | None = None,
    ) -> BookingRuntimeSnapshot:
        card = self.build_booking_card(booking=booking)
        return BookingRuntimeSnapshot(
            booking_id=booking.booking_id,
            state_token=state_token or booking.booking_id,
            role_variant=role_variant,
            scheduled_start_at=booking.scheduled_start_at,
            timezone_name=self._resolve_timezone_name(clinic_id=booking.clinic_id, branch_id=booking.branch_id),
            patient_label=patient_label or booking.patient_id,
            doctor_label=card.doctor_label,
            service_label=card.service_label,
            branch_label=card.branch_label,
            status=booking.status,
            source_channel=booking.source_channel,
            patient_contact=patient_contact,
            chart_summary_entry=chart_summary_entry,
            recommendation_summary=recommendation_summary,
            care_order_summary=care_order_summary,
            next_step_note_key=card.next_step_key,
        )

    async def get_admin_escalation_detail(self, *, clinic_id: str, escalation_id: str) -> AdminEscalation | None:
        rows = await self.reads.list_open_admin_escalations(clinic_id=clinic_id, limit=200)
        for row in rows:
            if row.admin_escalation_id == escalation_id:
                return row
        return None

    async def take_admin_escalation(self, *, clinic_id: str, escalation_id: str, actor_id: str) -> AdminEscalation | None:
        escalation = await self.orchestration.repository.get_admin_escalation(escalation_id)  # type: ignore[attr-defined]
        if escalation is None or escalation.clinic_id != clinic_id:
            return None
        updated = AdminEscalation(
            **{
                **asdict(escalation),
                "status": "in_progress",
                "assigned_to_actor_id": actor_id,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        await self.orchestration.repository.upsert_admin_escalation(updated)  # type: ignore[attr-defined]
        return updated

    async def resolve_admin_escalation(self, *, clinic_id: str, escalation_id: str, actor_id: str) -> AdminEscalation | None:
        escalation = await self.orchestration.repository.get_admin_escalation(escalation_id)  # type: ignore[attr-defined]
        if escalation is None or escalation.clinic_id != clinic_id:
            return None
        payload = dict(escalation.payload_summary or {})
        payload["resolved_by"] = actor_id
        updated = AdminEscalation(
            **{
                **asdict(escalation),
                "status": "resolved",
                "assigned_to_actor_id": actor_id,
                "payload_summary": payload,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        await self.orchestration.repository.upsert_admin_escalation(updated)  # type: ignore[attr-defined]
        return updated

    async def get_admin_booking_detail(self, *, booking_id: str) -> BookingCardView | None:
        booking = await self.reads.get_booking(booking_id)
        if booking is None:
            return None
        return self.build_booking_card(booking=booking)

    def _slot_matches_service(self, slot: AvailabilitySlot, *, service_id: str | None) -> bool:
        if service_id is None:
            return True
        if slot.service_scope is None:
            return True
        service_ids = slot.service_scope.get("service_ids")
        if isinstance(service_ids, list):
            return service_id in service_ids
        return True

    def _panel_for_session(self, session: BookingSession) -> str:
        if session.status in {"admin_escalated", "completed", "canceled", "expired"}:
            return "session_terminal"
        if not session.service_id:
            return "service_selection"
        if session.doctor_preference_type not in {"any", "specific"}:
            return "doctor_preference_selection"
        if session.doctor_preference_type == "specific" and not session.doctor_id:
            return "doctor_preference_selection"
        if not session.selected_slot_id:
            return "slot_selection"
        if not session.contact_phone_snapshot or not session.resolved_patient_id:
            return "contact_collection"
        return "review_finalize"

    def _service_label(self, service: Service | None, fallback: str) -> str:
        if service is None:
            return fallback
        return service.code or fallback

    def _branch_by_id(self, clinic_id: str) -> dict[str, Branch]:
        return {row.branch_id: row for row in self.reference.list_branches(clinic_id)}

    def _doctor_by_id(self, clinic_id: str) -> dict[str, Doctor]:
        return {row.doctor_id: row for row in self.reference.list_doctors(clinic_id)}

    def _service_by_id(self, clinic_id: str) -> dict[str, Service]:
        return {row.service_id: row for row in self.reference.list_services(clinic_id)}

    def _next_step_key_for_booking(self, status: str) -> str:
        if status == "reschedule_requested":
            return "patient.booking.card.next.reschedule_requested"
        if status == "confirmed":
            return "patient.booking.card.next.confirmed"
        if status == "pending_confirmation":
            return "patient.booking.card.next.pending_confirmation"
        if status == "canceled":
            return "patient.booking.card.next.canceled"
        return "patient.booking.card.next.default"

    async def _latest_active_session(
        self,
        *,
        clinic_id: str,
        telegram_user_id: int,
        allowed_route_types: frozenset[str],
    ) -> BookingSession | None:
        active = await self.reads.list_active_sessions_for_telegram_user(clinic_id=clinic_id, telegram_user_id=telegram_user_id)
        return self._latest_for_route_types(active, allowed_route_types=allowed_route_types)

    def _latest_for_route_types(
        self,
        active_sessions: list[BookingSession],
        *,
        allowed_route_types: frozenset[str],
    ) -> BookingSession | None:
        matched = [row for row in active_sessions if row.route_type in allowed_route_types]
        if not matched:
            return None
        return sorted(matched, key=lambda row: row.updated_at, reverse=True)[0]

    def _resolve_timezone_name(self, *, clinic_id: str, branch_id: str | None) -> str:
        if branch_id:
            branch = self._branch_by_id(clinic_id).get(branch_id)
            if branch and branch.timezone:
                return branch.timezone
        clinic = self.reference.get_clinic(clinic_id)
        if clinic and clinic.timezone:
            return clinic.timezone
        return "UTC"

    def _zone_or_utc(self, timezone_name: str) -> ZoneInfo:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")
