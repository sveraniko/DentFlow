from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True, frozen=True)
class ExportPatientIdentity043:
    patient_id: str
    display_name: str
    full_name_legal: str
    patient_number: str | None
    preferred_language: str | None
    preferred_reminder_channel: str | None
    primary_contact_hint: str | None
    external_reference: str | None


@dataclass(slots=True, frozen=True)
class ExportBookingContext043:
    booking_id: str | None
    booking_status: str | None
    scheduled_start_at_utc: datetime | None
    scheduled_start_local_label: str | None
    scheduled_end_local_label: str | None
    doctor_label: str | None
    service_label: str | None
    branch_label: str | None


@dataclass(slots=True, frozen=True)
class ExportChartContext043:
    chart_id: str
    chart_number: str | None
    chart_opened_at: datetime
    chart_notes_summary: str | None
    encounter_id: str | None
    encounter_opened_at: datetime | None
    encounter_status: str | None


@dataclass(slots=True, frozen=True)
class ExportDiagnosis043:
    diagnosis_id: str | None
    diagnosis_text: str | None
    diagnosis_code: str | None
    is_primary: bool | None
    version_no: int | None
    recorded_at: datetime | None


@dataclass(slots=True, frozen=True)
class ExportTreatmentPlan043:
    treatment_plan_id: str | None
    title: str | None
    plan_text: str | None
    version_no: int | None
    estimated_cost_amount: float | None
    currency_code: str | None
    approved_by_patient_at: datetime | None


@dataclass(slots=True, frozen=True)
class ExportNoteSummary043:
    note_count: int
    latest_note_type: str | None
    latest_note_text: str | None
    latest_note_recorded_at: datetime | None


@dataclass(slots=True, frozen=True)
class ExportImagingSummary043:
    total_count: int
    primary_imaging_ref_id: str | None
    latest_imaging_ref_id: str | None
    latest_imaging_type: str | None
    latest_imaging_description: str | None


@dataclass(slots=True, frozen=True)
class ExportOdontogramSummary043:
    has_snapshot: bool
    odontogram_snapshot_id: str | None
    recorded_at: datetime | None
    surface_count_hint: int | None


@dataclass(slots=True, frozen=True)
class ExportMetadata043:
    assembled_at: datetime
    assembled_by_actor_id: str | None
    template_type: str
    template_locale: str
    template_version: int | None


@dataclass(slots=True, frozen=True)
class Structured043ExportPayload:
    patient: ExportPatientIdentity043
    booking: ExportBookingContext043
    chart: ExportChartContext043
    diagnosis: ExportDiagnosis043
    treatment_plan: ExportTreatmentPlan043
    complaint_and_notes: ExportNoteSummary043
    imaging: ExportImagingSummary043
    odontogram: ExportOdontogramSummary043
    metadata: ExportMetadata043
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True, frozen=True)
class ExportAssemblyRequest:
    clinic_id: str
    patient_id: str
    chart_id: str
    template_type: str
    template_locale: str
    booking_id: str | None = None
    encounter_id: str | None = None
    assembled_by_actor_id: str | None = None
    template_version: int | None = None


@dataclass(slots=True, frozen=True)
class ExportAssemblyResult:
    generated_document_id: str
    document_template_id: str
    payload: Structured043ExportPayload
