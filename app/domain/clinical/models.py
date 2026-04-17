from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class PatientChart:
    chart_id: str
    patient_id: str
    clinic_id: str
    opened_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime
    chart_number: str | None = None
    primary_doctor_id: str | None = None
    notes_summary: str | None = None


@dataclass(slots=True, frozen=True)
class PresentingComplaint:
    complaint_id: str
    chart_id: str
    complaint_text: str
    recorded_at: datetime
    created_at: datetime
    encounter_id: str | None = None
    booking_id: str | None = None
    onset_description: str | None = None
    context_note: str | None = None
    recorded_by_actor_id: str | None = None


@dataclass(slots=True, frozen=True)
class ClinicalEncounter:
    encounter_id: str
    chart_id: str
    doctor_id: str
    opened_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime
    booking_id: str | None = None
    closed_at: datetime | None = None
    chief_complaint_snapshot: str | None = None
    findings_summary: str | None = None
    assessment_summary: str | None = None
    plan_summary: str | None = None


@dataclass(slots=True, frozen=True)
class EncounterNote:
    encounter_note_id: str
    encounter_id: str
    note_type: str
    note_text: str
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime
    recorded_by_actor_id: str | None = None


@dataclass(slots=True, frozen=True)
class Diagnosis:
    diagnosis_id: str
    chart_id: str
    diagnosis_text: str
    is_primary: bool
    status: str
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime
    encounter_id: str | None = None
    diagnosis_code: str | None = None
    recorded_by_actor_id: str | None = None


@dataclass(slots=True, frozen=True)
class TreatmentPlan:
    treatment_plan_id: str
    chart_id: str
    title: str
    plan_text: str
    status: str
    created_at: datetime
    updated_at: datetime
    encounter_id: str | None = None
    estimated_cost_amount: float | None = None
    currency_code: str | None = None
    approved_by_patient_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class ImagingReference:
    imaging_ref_id: str
    chart_id: str
    imaging_type: str
    uploaded_at: datetime
    is_primary_for_case: bool
    created_at: datetime
    updated_at: datetime
    encounter_id: str | None = None
    media_asset_id: str | None = None
    external_url: str | None = None
    description: str | None = None
    taken_at: datetime | None = None
    uploaded_by_actor_id: str | None = None


@dataclass(slots=True, frozen=True)
class OdontogramSnapshot:
    odontogram_snapshot_id: str
    chart_id: str
    snapshot_payload_json: dict[str, object]
    recorded_at: datetime
    created_at: datetime
    encounter_id: str | None = None
    recorded_by_actor_id: str | None = None
