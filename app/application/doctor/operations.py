from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.application.access import AccessResolver
from app.application.booking.orchestration import BookingOrchestrationService
from app.application.booking.orchestration_outcomes import InvalidStateOutcome, OrchestrationSuccess
from app.application.booking.state_services import BookingStateService
from app.application.booking.services import BookingService
from app.application.clinic_reference import ClinicReferenceService
from app.application.clinical import ChartSummary, ClinicalChartService
from app.application.doctor.patient_read import DoctorPatientReader
from app.domain.booking import Booking
from app.domain.booking.errors import InvalidBookingTransitionError
from app.domain.clinical import ClinicalEncounter, EncounterNote, ImagingReference, OdontogramSnapshot

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


@dataclass(frozen=True)
class DoctorChartSummaryCard:
    chart_id: str
    patient_id: str
    status: str
    latest_diagnosis_text: str | None
    latest_treatment_plan_text: str | None
    latest_note_snippet: str | None
    note_count: int
    imaging_count: int
    updated_at_label: str


class DoctorOperationResult(Protocol):
    kind: str


@dataclass(slots=True)
class DoctorOperationsService:
    access_resolver: AccessResolver
    booking_service: BookingService
    booking_state_service: BookingStateService
    booking_orchestration: BookingOrchestrationService
    reference_service: ClinicReferenceService
    patient_reader: DoctorPatientReader
    clinical_service: ClinicalChartService | None = None

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

    async def build_patient_quick_card(
        self,
        *,
        patient_id: str,
        doctor_id: str,
        require_visibility_guard: bool = True,
    ) -> DoctorPatientQuickCard | None:
        if require_visibility_guard and not await self._doctor_can_view_patient(doctor_id=doctor_id, patient_id=patient_id):
            return None
        patient = await self.patient_reader.read_snapshot(patient_id=patient_id)
        if patient is None:
            return None
        upcoming = await self._upcoming_booking_snippet(patient_id=patient_id, doctor_id=doctor_id)
        return DoctorPatientQuickCard(
            patient_id=patient.patient_id,
            display_name=patient.display_name,
            patient_number=patient.patient_number,
            phone_hint=self._mask_phone(patient.phone_raw),
            has_photo=patient.has_photo,
            active_flags_summary=patient.active_flags_summary,
            upcoming_booking_snippet=upcoming,
        )

    async def open_chart_summary(
        self,
        *,
        doctor_id: str,
        clinic_id: str,
        patient_id: str,
    ) -> DoctorChartSummaryCard | None:
        if self.clinical_service is None:
            return None
        if not await self._doctor_can_view_patient(doctor_id=doctor_id, patient_id=patient_id):
            return None
        chart = await self.clinical_service.open_or_get_chart(patient_id=patient_id, clinic_id=clinic_id, primary_doctor_id=doctor_id)
        summary = await self.clinical_service.load_chart_summary(chart_id=chart.chart_id)
        if summary is None:
            return None
        return self._build_chart_summary_card(summary)

    async def open_or_get_encounter(
        self,
        *,
        doctor_id: str,
        clinic_id: str,
        patient_id: str,
        booking_id: str | None = None,
    ) -> ClinicalEncounter | None:
        if self.clinical_service is None:
            return None
        if booking_id:
            booking = await self.booking_service.load_booking(booking_id)
            if booking is None or booking.doctor_id != doctor_id or booking.patient_id != patient_id:
                return None
        elif not await self._doctor_can_view_patient(doctor_id=doctor_id, patient_id=patient_id):
            return None
        chart = await self.clinical_service.open_or_get_chart(patient_id=patient_id, clinic_id=clinic_id, primary_doctor_id=doctor_id)
        return await self.clinical_service.open_or_get_encounter(chart_id=chart.chart_id, doctor_id=doctor_id, booking_id=booking_id)

    async def add_encounter_note(self, *, doctor_id: str, encounter_id: str, note_type: str, note_text: str) -> EncounterNote | None:
        if self.clinical_service is None:
            return None
        encounter = await self.clinical_service.repository.get_encounter(encounter_id)
        if encounter is None or encounter.doctor_id != doctor_id:
            return None
        return await self.clinical_service.add_encounter_note(encounter_id=encounter_id, note_type=note_type, note_text=note_text)

    async def set_chart_diagnosis(self, *, doctor_id: str, clinic_id: str, patient_id: str, diagnosis_text: str, encounter_id: str | None = None) -> str | None:
        if self.clinical_service is None:
            return None
        if not await self._doctor_can_view_patient(doctor_id=doctor_id, patient_id=patient_id):
            return None
        chart = await self.clinical_service.open_or_get_chart(patient_id=patient_id, clinic_id=clinic_id, primary_doctor_id=doctor_id)
        diagnosis = await self.clinical_service.set_diagnosis(chart_id=chart.chart_id, diagnosis_text=diagnosis_text, encounter_id=encounter_id)
        return diagnosis.diagnosis_id

    async def set_chart_treatment_plan(self, *, doctor_id: str, clinic_id: str, patient_id: str, title: str, plan_text: str, encounter_id: str | None = None) -> str | None:
        if self.clinical_service is None:
            return None
        if not await self._doctor_can_view_patient(doctor_id=doctor_id, patient_id=patient_id):
            return None
        chart = await self.clinical_service.open_or_get_chart(patient_id=patient_id, clinic_id=clinic_id, primary_doctor_id=doctor_id)
        plan = await self.clinical_service.set_treatment_plan(chart_id=chart.chart_id, title=title, plan_text=plan_text, encounter_id=encounter_id)
        return plan.treatment_plan_id

    async def attach_chart_imaging(self, *, doctor_id: str, clinic_id: str, patient_id: str, imaging_type: str, media_asset_id: str | None = None, external_url: str | None = None, description: str | None = None, encounter_id: str | None = None) -> ImagingReference | None:
        if self.clinical_service is None:
            return None
        if not await self._doctor_can_view_patient(doctor_id=doctor_id, patient_id=patient_id):
            return None
        chart = await self.clinical_service.open_or_get_chart(patient_id=patient_id, clinic_id=clinic_id, primary_doctor_id=doctor_id)
        return await self.clinical_service.attach_imaging_reference(
            chart_id=chart.chart_id,
            encounter_id=encounter_id,
            imaging_type=imaging_type,
            media_asset_id=media_asset_id,
            external_url=external_url,
            description=description,
        )

    async def save_chart_odontogram(self, *, doctor_id: str, clinic_id: str, patient_id: str, snapshot_payload_json: dict[str, object], encounter_id: str | None = None) -> OdontogramSnapshot | None:
        if self.clinical_service is None:
            return None
        if not await self._doctor_can_view_patient(doctor_id=doctor_id, patient_id=patient_id):
            return None
        chart = await self.clinical_service.open_or_get_chart(patient_id=patient_id, clinic_id=clinic_id, primary_doctor_id=doctor_id)
        return await self.clinical_service.save_odontogram_snapshot(
            chart_id=chart.chart_id,
            encounter_id=encounter_id,
            snapshot_payload_json=snapshot_payload_json,
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

    def _build_chart_summary_card(self, summary: ChartSummary) -> DoctorChartSummaryCard:
        latest_note_snippet = None
        if summary.latest_note:
            latest_note_snippet = summary.latest_note.note_text[:120]
        return DoctorChartSummaryCard(
            chart_id=summary.chart.chart_id,
            patient_id=summary.chart.patient_id,
            status=summary.chart.status,
            latest_diagnosis_text=summary.latest_diagnosis.diagnosis_text if summary.latest_diagnosis else None,
            latest_treatment_plan_text=summary.latest_treatment_plan.title if summary.latest_treatment_plan else None,
            latest_note_snippet=latest_note_snippet,
            note_count=summary.note_count,
            imaging_count=summary.imaging_count,
            updated_at_label=summary.updated_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )

    async def _build_queue_item(self, booking: Booking) -> DoctorQueueItem:
        patient_card = await self.build_patient_quick_card(
            patient_id=booking.patient_id,
            doctor_id=booking.doctor_id,
            require_visibility_guard=False,
        )
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
        card = await self.build_patient_quick_card(
            patient_id=booking.patient_id,
            doctor_id=booking.doctor_id,
            require_visibility_guard=False,
        )
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

    async def _doctor_can_view_patient(self, *, doctor_id: str, patient_id: str) -> bool:
        rows = await self.booking_service.list_by_patient(patient_id=patient_id)
        return any(row.doctor_id == doctor_id for row in rows)

    def _mask_phone(self, raw: str | None) -> str | None:
        if not raw:
            return None
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) <= 4:
            return f"***{digits}"
        return f"***{digits[-4:]}"
