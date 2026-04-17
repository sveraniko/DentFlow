from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.application.access import AccessResolver
from app.application.booking.orchestration import BookingOrchestrationService
from app.application.booking.orchestration_outcomes import InvalidStateOutcome, OrchestrationSuccess
from app.domain.booking.errors import InvalidBookingTransitionError
from app.application.booking.state_services import BookingStateService
from app.application.booking.services import BookingService
from app.application.clinic_reference import ClinicReferenceService
from app.application.patient.registry import PatientRegistryService
from app.domain.booking import Booking

LIVE_QUEUE_STATUSES = {"pending_confirmation", "confirmed", "reschedule_requested", "checked_in", "in_service"}
DOCTOR_ALLOWED_ACTIONS = {"checked_in", "in_service", "completed"}


@dataclass(frozen=True)
class DoctorQueueItem:
    booking_id: str
    patient_display_name: str
    patient_number: str | None
    phone_hint: str | None
    has_photo: bool
    active_flags_summary: str | None
    service_label: str
    branch_label: str
    booking_status: str
    scheduled_label: str
    scheduled_start_at: datetime


@dataclass(frozen=True)
class DoctorPatientQuickCard:
    patient_id: str
    display_name: str
    patient_number: str | None
    phone_hint: str | None
    has_photo: bool
    active_flags_summary: str | None
    upcoming_booking_snippet: str | None


@dataclass(frozen=True)
class DoctorBookingDetail:
    booking_id: str
    patient_card: DoctorPatientQuickCard
    service_label: str
    branch_label: str
    booking_status: str
    scheduled_label: str


class DoctorOperationResult(Protocol):
    kind: str


@dataclass(slots=True)
class DoctorOperationsService:
    access_resolver: AccessResolver
    booking_service: BookingService
    booking_state_service: BookingStateService
    booking_orchestration: BookingOrchestrationService
    reference_service: ClinicReferenceService
    patient_registry: PatientRegistryService

    def resolve_doctor_identity(self, telegram_user_id: int) -> tuple[str | None, str | None]:
        return self.access_resolver.resolve_doctor_id(telegram_user_id)

    async def list_today_queue(self, *, doctor_id: str, now: datetime | None = None) -> list[DoctorQueueItem]:
        point = now or datetime.now(timezone.utc)
        day_start = datetime(point.year, point.month, point.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        rows = await self.booking_service.list_by_doctor_time_window(doctor_id=doctor_id, start_at=day_start, end_at=day_end)
        live = sorted((row for row in rows if row.status in LIVE_QUEUE_STATUSES), key=lambda row: row.scheduled_start_at)
        items: list[DoctorQueueItem] = []
        for row in live:
            items.append(await self._build_queue_item(row))
        return items

    async def get_next_patient(self, *, doctor_id: str, now: datetime | None = None) -> DoctorQueueItem | None:
        point = now or datetime.now(timezone.utc)
        queue = await self.list_today_queue(doctor_id=doctor_id, now=point)
        for row in queue:
            if row.scheduled_start_at >= point:
                return row
        return queue[0] if queue else None

    async def get_booking_detail(self, *, doctor_id: str, booking_id: str) -> DoctorBookingDetail | None:
        booking = await self.booking_service.load_booking(booking_id)
        if booking is None or booking.doctor_id != doctor_id:
            return None
        return await self._build_booking_detail(booking)

    async def build_patient_quick_card(self, *, patient_id: str, doctor_id: str) -> DoctorPatientQuickCard | None:
        patient = self.patient_registry.get_patient(patient_id)
        if patient is None:
            return None
        primary_phone = next(
            (c for c in self.patient_registry.repository.contacts.values() if c.patient_id == patient_id and c.contact_type == "phone" and c.is_primary and c.is_active),
            None,
        )
        has_photo = self.patient_registry.get_primary_photo(patient_id) is not None
        flags = self.patient_registry.active_flags(patient_id)
        upcoming = await self._upcoming_booking_snippet(patient_id=patient_id, doctor_id=doctor_id)
        return DoctorPatientQuickCard(
            patient_id=patient.patient_id,
            display_name=patient.display_name,
            patient_number=patient.patient_number,
            phone_hint=self._mask_phone(primary_phone.contact_value if primary_phone else None),
            has_photo=has_photo,
            active_flags_summary=", ".join(sorted({f.flag_type for f in flags})) if flags else None,
            upcoming_booking_snippet=upcoming,
        )

    async def apply_booking_action(self, *, doctor_id: str, booking_id: str, action: str) -> DoctorOperationResult:
        if action not in DOCTOR_ALLOWED_ACTIONS:
            return InvalidStateOutcome(kind="invalid_state", reason="unsupported_action")
        booking = await self.booking_service.load_booking(booking_id)
        if booking is None or booking.doctor_id != doctor_id:
            return InvalidStateOutcome(kind="invalid_state", reason="booking_not_accessible")
        if action == "completed":
            return await self.booking_orchestration.complete_booking(booking_id=booking_id, reason_code="doctor_marked_completed")
        try:
            changed = await self.booking_state_service.transition_booking(
                booking_id=booking_id,
                to_status=action,
                reason_code=f"doctor_marked_{action}",
            )
        except InvalidBookingTransitionError:
            return InvalidStateOutcome(kind="invalid_state", reason=f"booking cannot transition to {action}")
        return OrchestrationSuccess(kind="success", entity=changed.entity)

    async def _build_queue_item(self, booking: Booking) -> DoctorQueueItem:
        patient_card = await self.build_patient_quick_card(patient_id=booking.patient_id, doctor_id=booking.doctor_id)
        service = self.reference_service.list_services(booking.clinic_id)
        services_by_id = {row.service_id: row for row in service}
        service_row = services_by_id.get(booking.service_id)
        branch_by_id = {row.branch_id: row for row in self.reference_service.list_branches(booking.clinic_id)}
        branch_row = branch_by_id.get(booking.branch_id or "")
        return DoctorQueueItem(
            booking_id=booking.booking_id,
            patient_display_name=patient_card.display_name if patient_card else booking.patient_id,
            patient_number=patient_card.patient_number if patient_card else None,
            phone_hint=patient_card.phone_hint if patient_card else None,
            has_photo=patient_card.has_photo if patient_card else False,
            active_flags_summary=patient_card.active_flags_summary if patient_card else None,
            service_label=(f"{service_row.code} ({service_row.title_key})" if service_row else booking.service_id),
            branch_label=(branch_row.display_name if branch_row else (booking.branch_id or "-")),
            booking_status=booking.status,
            scheduled_label=booking.scheduled_start_at.astimezone(timezone.utc).strftime("%H:%M UTC"),
            scheduled_start_at=booking.scheduled_start_at,
        )

    async def _build_booking_detail(self, booking: Booking) -> DoctorBookingDetail:
        card = await self.build_patient_quick_card(patient_id=booking.patient_id, doctor_id=booking.doctor_id)
        if card is None:
            card = DoctorPatientQuickCard(
                patient_id=booking.patient_id,
                display_name=booking.patient_id,
                patient_number=None,
                phone_hint=None,
                has_photo=False,
                active_flags_summary=None,
                upcoming_booking_snippet=None,
            )
        queue_item = await self._build_queue_item(booking)
        return DoctorBookingDetail(
            booking_id=booking.booking_id,
            patient_card=card,
            service_label=queue_item.service_label,
            branch_label=queue_item.branch_label,
            booking_status=booking.status,
            scheduled_label=booking.scheduled_start_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )

    async def _upcoming_booking_snippet(self, *, patient_id: str, doctor_id: str) -> str | None:
        now = datetime.now(timezone.utc)
        rows = await self.booking_service.list_by_patient(patient_id=patient_id)
        future = sorted((row for row in rows if row.doctor_id == doctor_id and row.status in LIVE_QUEUE_STATUSES and row.scheduled_start_at >= now), key=lambda row: row.scheduled_start_at)
        if not future:
            return None
        row = future[0]
        return f"{row.scheduled_start_at.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · {row.status}"

    def _mask_phone(self, raw: str | None) -> str | None:
        if not raw:
            return None
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) <= 4:
            return f"***{digits}"
        return f"***{digits[-4:]}"
