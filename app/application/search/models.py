from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SearchResultOrigin(str, Enum):
    POSTGRES_STRICT = "postgres_strict"
    POSTGRES_FALLBACK = "postgres_fallback"
    MEILI = "meili"


@dataclass(frozen=True)
class PatientSearchResult:
    patient_id: str
    clinic_id: str
    display_name: str
    patient_number: str | None
    primary_phone_normalized: str | None
    status: str | None
    origin: SearchResultOrigin


@dataclass(frozen=True)
class DoctorSearchResult:
    doctor_id: str
    clinic_id: str
    branch_id: str | None
    display_name: str
    specialty_code: str | None
    specialty_label: str | None
    public_booking_enabled: bool
    status: str | None
    origin: SearchResultOrigin


@dataclass(frozen=True)
class ServiceSearchResult:
    service_id: str
    clinic_id: str
    code: str | None
    title_key: str | None
    localized_search_text_ru: str | None
    localized_search_text_en: str | None
    specialty_required: bool
    status: str | None
    origin: SearchResultOrigin


@dataclass(frozen=True)
class PatientSearchResponse:
    exact_matches: list[PatientSearchResult]
    suggestions: list[PatientSearchResult]


@dataclass(frozen=True)
class SearchQuery:
    clinic_id: str
    query: str
    limit: int = 10
    locale: str | None = None


@dataclass(frozen=True)
class PatientProjectionRow:
    patient_id: str
    clinic_id: str
    display_name: str
    patient_number: str | None
    name_tokens_normalized: str | None
    translit_tokens: str | None
    primary_phone_normalized: str | None
    preferred_language: str | None
    primary_photo_ref: str | None
    active_flags_summary: str | None
    status: str | None
    updated_at: datetime


@dataclass(frozen=True)
class DoctorProjectionRow:
    doctor_id: str
    clinic_id: str
    branch_id: str | None
    display_name: str
    name_tokens_normalized: str | None
    translit_tokens: str | None
    specialty_code: str | None
    specialty_label: str | None
    public_booking_enabled: bool
    status: str | None
    updated_at: datetime


@dataclass(frozen=True)
class ServiceProjectionRow:
    service_id: str
    clinic_id: str
    code: str | None
    title_key: str | None
    localized_search_text_ru: str | None
    localized_search_text_en: str | None
    specialty_required: bool
    status: str | None
    updated_at: datetime
