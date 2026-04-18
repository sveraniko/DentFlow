from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from app.application.access import AccessResolver
from app.application.booking.orchestration import BookingOrchestrationService
from app.application.booking.orchestration_outcomes import InvalidStateOutcome, OrchestrationSuccess
from app.application.booking.state_services import BookingStateService
from app.application.booking.services import BookingService
from app.application.clinic_reference import ClinicReferenceService
from app.application.clinical import ChartSummary, ClinicalChartService
from app.application.care_commerce import CareCommerceService
from app.application.doctor.patient_read import DoctorPatientReader
from app.common.i18n import I18nService
from app.application.recommendation import RecommendationService
from app.application.timezone import DoctorTimezoneFormatter
from app.domain.booking import Booking
from app.domain.booking.errors import InvalidBookingTransitionError
from app.domain.clinical import ClinicalEncounter, EncounterNote, ImagingReference, OdontogramSnapshot

LIVE_QUEUE_STATUSES = {"pending_confirmation", "confirmed", "reschedule_requested", "checked_in", "in_service"}
DOCTOR_ALLOWED_ACTIONS = {"checked_in", "in_service", "completed"}
_AFTERCARE_TITLE_KEY = "recommendation.aftercare.booking_complete.title"
_AFTERCARE_BODY_KEY = "recommendation.aftercare.booking_complete.body"


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
    recommendation_service: RecommendationService | None = None
    care_commerce_service: CareCommerceService | None = None
    i18n: I18nService | None = None
    app_default_timezone: str = "UTC"

    def resolve_doctor_identity(self, telegram_user_id: int) -> tuple[str | None, str | None]:
        return self.access_resolver.resolve_doctor_id(telegram_user_id)

    async def list_today_queue(self, *, doctor_id: str, now: datetime | None = None) -> list[DoctorQueueItem]:
        point = now or datetime.now(timezone.utc)
        tz = DoctorTimezoneFormatter(reference_service=self.reference_service, app_default_timezone=self.app_default_timezone)
        clinic_id, branch_id = self._resolve_doctor_scope(doctor_id=doctor_id)
        day_start, day_end = tz.local_day_utc_window(clinic_id=clinic_id, branch_id=branch_id, point=point)
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
        return self._build_chart_summary_card(summary, clinic_id=clinic_id)

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
            result = await self.booking_orchestration.complete_booking(booking_id=booking_id, reason_code="doctor_marked_completed")
            if (
                result.kind == "success"
                and self.recommendation_service is not None
                and booking.status in {"in_service", "checked_in", "confirmed", "pending_confirmation"}
            ):
                await self._create_completion_aftercare(booking=booking)
            return result
        try:
            changed = await self.booking_state_service.transition_booking(
                booking_id=booking_id,
                to_status=action,
                reason_code=f"doctor_marked_{action}",
            )
        except InvalidBookingTransitionError:
            return InvalidStateOutcome(kind="invalid_state", reason=f"booking cannot transition to {action}")
        return OrchestrationSuccess(kind="success", entity=changed.entity)

    def _build_chart_summary_card(self, summary: ChartSummary, *, clinic_id: str) -> DoctorChartSummaryCard:
        tz = DoctorTimezoneFormatter(reference_service=self.reference_service, app_default_timezone=self.app_default_timezone)
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
            updated_at_label=tz.format_clinic_time(clinic_id=clinic_id, when=summary.updated_at, fmt="%Y-%m-%d %H:%M %Z"),
        )

    async def _build_queue_item(self, booking: Booking) -> DoctorQueueItem:
        tz = DoctorTimezoneFormatter(reference_service=self.reference_service, app_default_timezone=self.app_default_timezone)
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
            scheduled_label=tz.format_booking_time(clinic_id=booking.clinic_id, branch_id=booking.branch_id, when=booking.scheduled_start_at, fmt="%H:%M %Z"),
            scheduled_start_at=booking.scheduled_start_at,
        )


    def _resolve_doctor_scope(self, *, doctor_id: str) -> tuple[str, str | None]:
        for clinic in self.reference_service.list_clinics():
            doctor = self.reference_service.get_doctor(clinic.clinic_id, doctor_id)
            if doctor is not None:
                return clinic.clinic_id, doctor.branch_id
        raise KeyError(f"Doctor not found: {doctor_id}")

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
        tz = DoctorTimezoneFormatter(reference_service=self.reference_service, app_default_timezone=self.app_default_timezone)
        return DoctorBookingDetail(
            booking_id=booking.booking_id,
            patient_card=card,
            service_label=queue_item.service_label,
            branch_label=queue_item.branch_label,
            booking_status=booking.status,
            scheduled_label=tz.format_booking_time(clinic_id=booking.clinic_id, branch_id=booking.branch_id, when=booking.scheduled_start_at, fmt="%Y-%m-%d %H:%M %Z"),
        )

    async def _upcoming_booking_snippet(self, *, patient_id: str, doctor_id: str) -> str | None:
        now = datetime.now(timezone.utc)
        rows = await self.booking_service.list_by_patient(patient_id=patient_id)
        future = sorted((row for row in rows if row.doctor_id == doctor_id and row.status in LIVE_QUEUE_STATUSES and row.scheduled_start_at >= now), key=lambda row: row.scheduled_start_at)
        if not future:
            return None
        row = future[0]
        tz = DoctorTimezoneFormatter(reference_service=self.reference_service, app_default_timezone=self.app_default_timezone)
        return f"{tz.format_booking_time(clinic_id=row.clinic_id, branch_id=row.branch_id, when=row.scheduled_start_at, fmt='%Y-%m-%d %H:%M %Z')} · {row.status}"

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

    async def issue_recommendation(
        self,
        *,
        doctor_id: str,
        clinic_id: str,
        patient_id: str,
        recommendation_type: str,
        title: str,
        body_text: str,
        rationale_text: str | None = None,
        booking_id: str | None = None,
        encounter_id: str | None = None,
        chart_id: str | None = None,
        target_kind: str | None = None,
        target_code: str | None = None,
        target_justification_text: str | None = None,
    ):
        if self.recommendation_service is None:
            return None
        if booking_id:
            booking = await self.booking_service.load_booking(booking_id)
            if booking is None or booking.patient_id != patient_id or booking.doctor_id != doctor_id:
                return None
        elif not await self._doctor_can_view_patient(doctor_id=doctor_id, patient_id=patient_id):
            return None
        issued = await self.recommendation_service.create_recommendation(
            clinic_id=clinic_id,
            patient_id=patient_id,
            recommendation_type=recommendation_type,
            source_kind="doctor_manual",
            title=title,
            body_text=body_text,
            rationale_text=rationale_text,
            booking_id=booking_id,
            encounter_id=encounter_id,
            chart_id=chart_id,
            issued_by_actor_id=None,
            prepared=True,
        )
        issued_recommendation = await self.recommendation_service.issue(
            recommendation_id=issued.recommendation_id,
            issued_by_actor_id=None,
        )
        if (
            issued_recommendation is not None
            and self.care_commerce_service is not None
            and target_kind
            and target_code
        ):
            await self.care_commerce_service.set_manual_recommendation_target(
                recommendation_id=issued_recommendation.recommendation_id,
                target_kind=target_kind,
                target_code=target_code,
                justification_text=target_justification_text,
            )
        return issued_recommendation

    async def _create_completion_aftercare(self, *, booking: Booking) -> None:
        if self.recommendation_service is None:
            return
        clinic = self.reference_service.get_clinic(booking.clinic_id) if self.reference_service else None
        locale = clinic.default_locale if clinic else None
        title = self.i18n.t(_AFTERCARE_TITLE_KEY, locale) if self.i18n else _AFTERCARE_TITLE_KEY
        body = self.i18n.t(_AFTERCARE_BODY_KEY, locale) if self.i18n else _AFTERCARE_BODY_KEY
        created = await self.recommendation_service.create_recommendation(
            clinic_id=booking.clinic_id,
            patient_id=booking.patient_id,
            booking_id=booking.booking_id,
            recommendation_type="aftercare",
            source_kind="booking_trigger",
            title=title,
            body_text=body,
            rationale_text=None,
            prepared=True,
        )
        await self.recommendation_service.issue(recommendation_id=created.recommendation_id)
