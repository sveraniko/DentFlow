from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

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
from app.domain.clinic_reference.models import Doctor, Service

ACTIVE_SESSION_STATUSES: tuple[str, ...] = (
    "initiated",
    "in_progress",
    "awaiting_slot_selection",
    "awaiting_contact_confirmation",
    "review_ready",
)


class BookingFlowReadRepository(Protocol):
    async def get_booking_session(self, booking_session_id: str) -> BookingSession | None: ...
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


class CanonicalPatientCreator(Protocol):
    async def create_minimal_patient(self, *, clinic_id: str, display_name: str, phone: str) -> str: ...


@dataclass(slots=True, frozen=True)
class PatientResolutionFlowResult:
    kind: str
    booking_session: BookingSession | None = None
    escalation: AdminEscalation | None = None


@dataclass(slots=True)
class BookingPatientFlowService:
    orchestration: BookingOrchestrationService
    reads: BookingFlowReadRepository
    reference: ClinicReferenceService
    patient_creator: CanonicalPatientCreator

    async def start_or_resume_session(self, *, clinic_id: str, telegram_user_id: int, branch_id: str | None = None) -> BookingSession:
        active = await self.reads.list_active_sessions_for_telegram_user(clinic_id=clinic_id, telegram_user_id=telegram_user_id)
        if active:
            return sorted(active, key=lambda row: row.updated_at, reverse=True)[0]
        started = await self.orchestration.start_booking_session(
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            route_type="service_first",
            branch_id=branch_id,
        )
        return started.entity

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

    async def resolve_patient_from_contact(
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

        if isinstance(outcome, InvalidStateOutcome):
            return PatientResolutionFlowResult(kind="invalid_state")
        return PatientResolutionFlowResult(kind="invalid_state")

    async def mark_review_ready(self, *, booking_session_id: str):
        return await self.orchestration.mark_session_review_ready(booking_session_id=booking_session_id)

    async def finalize(self, *, booking_session_id: str):
        return await self.orchestration.finalize_booking_from_session(booking_session_id=booking_session_id)

    async def list_admin_escalations(self, *, clinic_id: str, limit: int = 10) -> list[AdminEscalation]:
        return await self.reads.list_open_admin_escalations(clinic_id=clinic_id, limit=limit)

    async def list_admin_new_bookings(self, *, clinic_id: str, limit: int = 10) -> list[Booking]:
        return await self.reads.list_recent_bookings_by_statuses(
            clinic_id=clinic_id,
            statuses=("pending_confirmation", "confirmed"),
            limit=limit,
        )

    def _slot_matches_service(self, slot: AvailabilitySlot, *, service_id: str | None) -> bool:
        if service_id is None:
            return True
        if slot.service_scope is None:
            return True
        service_ids = slot.service_scope.get("service_ids")
        if isinstance(service_ids, list):
            return service_id in service_ids
        return True

