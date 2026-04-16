from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True, frozen=True)
class Patient:
    patient_id: str
    clinic_id: str
    full_name_legal: str
    first_name: str
    last_name: str
    display_name: str
    status: str = "active"
    patient_number: str | None = None
    middle_name: str | None = None
    birth_date: date | None = None
    sex_marker: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class PatientContact:
    patient_contact_id: str
    patient_id: str
    contact_type: str
    contact_value: str
    normalized_value: str
    is_primary: bool = False
    is_verified: bool = False
    is_active: bool = True
    notes: str | None = None


@dataclass(slots=True, frozen=True)
class PatientPreference:
    patient_preference_id: str
    patient_id: str
    preferred_language: str | None = None
    preferred_reminder_channel: str | None = None
    allow_sms: bool = True
    allow_telegram: bool = True
    allow_call: bool = False
    allow_email: bool = False
    marketing_opt_in: bool = False
    contact_time_window: dict[str, object] | None = None


@dataclass(slots=True, frozen=True)
class PatientFlag:
    patient_flag_id: str
    patient_id: str
    flag_type: str
    flag_severity: str
    is_active: bool = True
    set_by_actor_id: str | None = None
    set_at: datetime | None = None
    expires_at: datetime | None = None
    note: str | None = None


@dataclass(slots=True, frozen=True)
class PatientPhoto:
    patient_photo_id: str
    patient_id: str
    source_type: str
    media_asset_id: str | None = None
    external_ref: str | None = None
    is_primary: bool = False
    captured_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class PatientMedicalSummary:
    patient_medical_summary_id: str
    patient_id: str
    last_updated_at: datetime
    created_at: datetime
    allergy_summary: str | None = None
    chronic_conditions_summary: str | None = None
    contraindication_summary: str | None = None
    current_primary_dental_issue_summary: str | None = None
    important_history_summary: str | None = None
    last_updated_by_actor_id: str | None = None


@dataclass(slots=True, frozen=True)
class PatientExternalId:
    patient_external_id_id: str
    patient_id: str
    external_system: str
    external_id: str
    is_primary: bool = False
    last_synced_at: datetime | None = None
