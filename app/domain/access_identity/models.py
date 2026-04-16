from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ActorType(str, Enum):
    PATIENT = "patient"
    STAFF = "staff"
    SERVICE = "service"


class ActorStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class StaffStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class RoleCode(str, Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    OWNER = "owner"
    MANAGER = "manager"
    EXPORT_OPERATOR = "export_operator"
    ANALYTICS_VIEWER = "analytics_viewer"


@dataclass(slots=True, frozen=True)
class ActorIdentity:
    actor_id: str
    actor_type: ActorType
    display_name: str
    status: ActorStatus = ActorStatus.ACTIVE
    locale: str | None = None


@dataclass(slots=True, frozen=True)
class TelegramBinding:
    telegram_binding_id: str
    actor_id: str
    telegram_user_id: int
    telegram_username: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    is_primary: bool = True
    is_active: bool = True


@dataclass(slots=True, frozen=True)
class StaffMember:
    staff_id: str
    actor_id: str
    clinic_id: str
    full_name: str
    display_name: str
    staff_status: StaffStatus = StaffStatus.ACTIVE
    primary_branch_id: str | None = None


@dataclass(slots=True, frozen=True)
class ClinicRoleAssignment:
    role_assignment_id: str
    staff_id: str
    clinic_id: str
    role_code: RoleCode
    branch_id: str | None = None
    scope_type: str = "clinic"
    scope_ref: str | None = None
    granted_by_actor_id: str | None = None
    granted_at: datetime | None = None
    revoked_at: datetime | None = None
    is_active: bool = True


@dataclass(slots=True, frozen=True)
class DoctorProfile:
    doctor_profile_id: str
    doctor_id: str
    staff_id: str
    clinic_id: str
    branch_id: str | None = None
    specialty_code: str | None = None
    active_for_booking: bool = True
    active_for_clinical_work: bool = True


@dataclass(slots=True, frozen=True)
class OwnerProfile:
    owner_profile_id: str
    staff_id: str
    clinic_id: str
    owner_scope_kind: str = "clinic"
    analytics_scope: str = "clinic"
    cross_branch_enabled: bool = True


@dataclass(slots=True, frozen=True)
class ServicePrincipal:
    service_principal_id: str
    principal_code: str
    description: str
    status: ActorStatus = ActorStatus.ACTIVE
