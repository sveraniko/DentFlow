from __future__ import annotations

from dataclasses import dataclass

from app.domain.access_identity.models import (
    ActorIdentity,
    ActorStatus,
    ActorType,
    ClinicRoleAssignment,
    DoctorProfile,
    RoleCode,
    StaffMember,
    TelegramBinding,
)


@dataclass(slots=True, frozen=True)
class ActorContext:
    actor_id: str
    clinic_id: str
    role_codes: frozenset[RoleCode]
    locale: str | None = None


@dataclass(slots=True, frozen=True)
class AccessDecision:
    allowed: bool
    reason: str


class InMemoryAccessRepository:
    def __init__(self) -> None:
        self.actor_identities: dict[str, ActorIdentity] = {}
        self.telegram_bindings: dict[int, TelegramBinding] = {}
        self.staff_members: dict[str, StaffMember] = {}
        self.role_assignments: dict[str, ClinicRoleAssignment] = {}
        self.doctor_profiles: dict[str, DoctorProfile] = {}

    def upsert_actor_identity(self, actor: ActorIdentity) -> None:
        self.actor_identities[actor.actor_id] = actor

    def upsert_telegram_binding(self, binding: TelegramBinding) -> None:
        self.telegram_bindings[binding.telegram_user_id] = binding

    def upsert_staff_member(self, staff_member: StaffMember) -> None:
        self.staff_members[staff_member.staff_id] = staff_member

    def upsert_role_assignment(self, role_assignment: ClinicRoleAssignment) -> None:
        self.role_assignments[role_assignment.role_assignment_id] = role_assignment

    def upsert_doctor_profile(self, doctor_profile: DoctorProfile) -> None:
        self.doctor_profiles[doctor_profile.doctor_profile_id] = doctor_profile


class AccessResolver:
    def __init__(self, repository: InMemoryAccessRepository) -> None:
        self.repository = repository

    def resolve_actor_context(self, telegram_user_id: int) -> ActorContext | None:
        binding = self.repository.telegram_bindings.get(telegram_user_id)
        if not binding or not binding.is_active:
            return None
        actor = self.repository.actor_identities.get(binding.actor_id)
        if not actor or actor.status != ActorStatus.ACTIVE:
            return None
        if actor.actor_type != ActorType.STAFF:
            return None

        staff = next(
            (
                item
                for item in self.repository.staff_members.values()
                if item.actor_id == actor.actor_id and item.staff_status.value == "active"
            ),
            None,
        )
        if not staff:
            return None

        roles = frozenset(
            assignment.role_code
            for assignment in self.repository.role_assignments.values()
            if assignment.staff_id == staff.staff_id and assignment.is_active
        )
        return ActorContext(actor_id=actor.actor_id, clinic_id=staff.clinic_id, role_codes=roles, locale=actor.locale)

    def check_roles(self, actor_context: ActorContext | None, allowed_roles: set[RoleCode]) -> AccessDecision:
        if actor_context is None:
            return AccessDecision(allowed=False, reason="access.denied.unbound")
        if actor_context.role_codes.intersection(allowed_roles):
            return AccessDecision(allowed=True, reason="access.allowed")
        return AccessDecision(allowed=False, reason="access.denied.role")

    def resolve_doctor_id(self, telegram_user_id: int) -> tuple[str | None, str | None]:
        actor_context = self.resolve_actor_context(telegram_user_id)
        if actor_context is None:
            return None, "access.denied.unbound"
        if RoleCode.DOCTOR not in actor_context.role_codes:
            return None, "access.denied.role"
        staff = next(
            (
                item
                for item in self.repository.staff_members.values()
                if item.actor_id == actor_context.actor_id and item.staff_status.value == "active"
            ),
            None,
        )
        if staff is None:
            return None, "doctor.identity.unavailable"
        rows = [
            row
            for row in self.repository.doctor_profiles.values()
            if row.staff_id == staff.staff_id and row.clinic_id == staff.clinic_id and row.active_for_clinical_work
        ]
        if not rows:
            return None, "doctor.identity.missing_profile"
        doctor_ids = sorted({row.doctor_id for row in rows})
        if len(doctor_ids) != 1:
            return None, "doctor.identity.ambiguous_profile"
        return doctor_ids[0], None
