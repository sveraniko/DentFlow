from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RecordStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass(slots=True, frozen=True)
class Clinic:
    clinic_id: str
    code: str
    display_name: str
    timezone: str
    default_locale: str
    status: RecordStatus = RecordStatus.ACTIVE


@dataclass(slots=True, frozen=True)
class Branch:
    branch_id: str
    clinic_id: str
    display_name: str
    address_text: str
    timezone: str
    status: RecordStatus = RecordStatus.ACTIVE


@dataclass(slots=True, frozen=True)
class Doctor:
    doctor_id: str
    clinic_id: str
    display_name: str
    specialty_code: str
    branch_id: str | None = None
    public_booking_enabled: bool = True
    status: RecordStatus = RecordStatus.ACTIVE


@dataclass(slots=True, frozen=True)
class Service:
    service_id: str
    clinic_id: str
    code: str
    title_key: str
    duration_minutes: int
    specialty_required: str | None = None
    status: RecordStatus = RecordStatus.ACTIVE


@dataclass(slots=True, frozen=True)
class DoctorAccessCode:
    doctor_access_code_id: str
    clinic_id: str
    doctor_id: str
    code: str
    status: RecordStatus
    expires_at: datetime | None = None
    max_uses: int | None = None
    service_scope: list[str] | None = None
    branch_scope: list[str] | None = None
