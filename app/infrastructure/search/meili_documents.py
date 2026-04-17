from __future__ import annotations

from dataclasses import asdict, dataclass

from app.application.search.models import DoctorProjectionRow, PatientProjectionRow, ServiceProjectionRow


@dataclass(frozen=True)
class MeiliPatientDocument:
    id: str
    patient_id: str
    clinic_id: str
    display_name: str
    patient_number: str | None
    name_normalized: str | None
    name_tokens_normalized: str | None
    translit_tokens: str | None
    external_id_normalized: str | None
    primary_phone_normalized: str | None
    preferred_language: str | None
    primary_photo_ref: str | None
    active_flags_summary: str | None
    status: str | None
    updated_at: str


@dataclass(frozen=True)
class MeiliDoctorDocument:
    id: str
    doctor_id: str
    clinic_id: str
    branch_id: str | None
    display_name: str
    name_normalized: str | None
    name_tokens_normalized: str | None
    translit_tokens: str | None
    specialty_code: str | None
    specialty_label: str | None
    public_booking_enabled: bool
    status: str | None
    updated_at: str


@dataclass(frozen=True)
class MeiliServiceDocument:
    id: str
    service_id: str
    clinic_id: str
    code: str | None
    title_key: str | None
    localized_search_text_ru: str | None
    localized_search_text_en: str | None
    specialty_required: bool
    status: str | None
    updated_at: str


def patient_projection_to_document(row: PatientProjectionRow) -> dict:
    return asdict(
        MeiliPatientDocument(
            id=row.patient_id,
            patient_id=row.patient_id,
            clinic_id=row.clinic_id,
            display_name=row.display_name,
            patient_number=row.patient_number,
            name_normalized=row.name_normalized,
            name_tokens_normalized=row.name_tokens_normalized,
            translit_tokens=row.translit_tokens,
            external_id_normalized=row.external_id_normalized,
            primary_phone_normalized=row.primary_phone_normalized,
            preferred_language=row.preferred_language,
            primary_photo_ref=row.primary_photo_ref,
            active_flags_summary=row.active_flags_summary,
            status=row.status,
            updated_at=row.updated_at.isoformat(),
        )
    )


def doctor_projection_to_document(row: DoctorProjectionRow) -> dict:
    return asdict(
        MeiliDoctorDocument(
            id=row.doctor_id,
            doctor_id=row.doctor_id,
            clinic_id=row.clinic_id,
            branch_id=row.branch_id,
            display_name=row.display_name,
            name_normalized=row.name_normalized,
            name_tokens_normalized=row.name_tokens_normalized,
            translit_tokens=row.translit_tokens,
            specialty_code=row.specialty_code,
            specialty_label=row.specialty_label,
            public_booking_enabled=row.public_booking_enabled,
            status=row.status,
            updated_at=row.updated_at.isoformat(),
        )
    )


def service_projection_to_document(row: ServiceProjectionRow) -> dict:
    return asdict(
        MeiliServiceDocument(
            id=row.service_id,
            service_id=row.service_id,
            clinic_id=row.clinic_id,
            code=row.code,
            title_key=row.title_key,
            localized_search_text_ru=row.localized_search_text_ru,
            localized_search_text_en=row.localized_search_text_en,
            specialty_required=row.specialty_required,
            status=row.status,
            updated_at=row.updated_at.isoformat(),
        )
    )
