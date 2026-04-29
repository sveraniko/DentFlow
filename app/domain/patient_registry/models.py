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
    notification_recipient_strategy: str | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    quiet_hours_timezone: str | None = None
    default_branch_id: str | None = None
    allow_any_branch: bool = True


@dataclass(slots=True, frozen=True)
class PatientProfileDetails:
    patient_id: str
    clinic_id: str
    profile_completion_state: str = "missing"
    email: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    postal_code: str | None = None
    country_code: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    profile_completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class PatientRelationship:
    relationship_id: str
    clinic_id: str
    manager_patient_id: str
    related_patient_id: str
    relationship_type: str
    consent_status: str = "active"
    authority_scope: str | None = None
    is_default_for_booking: bool = False
    is_default_notification_recipient: bool = False
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class LinkedPatientProfile:
    patient_id: str
    clinic_id: str
    display_name: str
    relationship_type: str
    is_self: bool = False
    is_default_for_booking: bool = False
    is_default_notification_recipient: bool = False
    phone: str | None = None
    telegram_user_id: int | None = None
    status: str = "active"


@dataclass(slots=True, frozen=True)
class PreVisitQuestionnaire:
    questionnaire_id: str
    clinic_id: str
    patient_id: str
    questionnaire_type: str
    status: str
    booking_id: str | None = None
    version: int = 1
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class PreVisitQuestionnaireAnswer:
    answer_id: str
    questionnaire_id: str
    question_key: str
    answer_value: dict[str, object]
    answer_type: str
    visibility: str = "staff_only"
    created_at: datetime | None = None
    updated_at: datetime | None = None


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
