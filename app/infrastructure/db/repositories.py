from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from app.application.access import InMemoryAccessRepository
from app.application.clinic_reference import InMemoryClinicReferenceRepository
from app.application.policy import InMemoryPolicyRepository
from app.domain.access_identity.models import (
    ActorIdentity,
    ActorStatus,
    ActorType,
    ClinicRoleAssignment,
    DoctorProfile,
    RoleCode,
    StaffMember,
    StaffStatus,
    TelegramBinding,
)
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, DoctorAccessCode, RecordStatus, Service
from app.domain.policy_config.models import FeatureFlag, PolicySet, PolicyStatus, PolicyValue
from app.infrastructure.db.engine import create_engine


class DbClinicReferenceRepository(InMemoryClinicReferenceRepository):
    @classmethod
    async def load(cls, db_config) -> "DbClinicReferenceRepository":
        repo = cls()
        engine = create_engine(db_config)
        async with engine.connect() as conn:
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT clinic_id, code, display_name, timezone, default_locale, status
                        FROM core_reference.clinics
                        """
                    )
                )
            ).mappings():
                repo.upsert_clinic(
                    Clinic(
                        clinic_id=row["clinic_id"],
                        code=row["code"],
                        display_name=row["display_name"],
                        timezone=row["timezone"],
                        default_locale=row["default_locale"],
                        status=RecordStatus(row["status"]),
                    )
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT branch_id, clinic_id, display_name, address_text, timezone, status
                        FROM core_reference.branches
                        """
                    )
                )
            ).mappings():
                repo.upsert_branch(
                    Branch(
                        branch_id=row["branch_id"],
                        clinic_id=row["clinic_id"],
                        display_name=row["display_name"],
                        address_text=row["address_text"],
                        timezone=row["timezone"],
                        status=RecordStatus(row["status"]),
                    )
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT doctor_id, clinic_id, branch_id, display_name, specialty_code, public_booking_enabled, status
                        FROM core_reference.doctors
                        """
                    )
                )
            ).mappings():
                repo.upsert_doctor(
                    Doctor(
                        doctor_id=row["doctor_id"],
                        clinic_id=row["clinic_id"],
                        branch_id=row["branch_id"],
                        display_name=row["display_name"],
                        specialty_code=row["specialty_code"],
                        public_booking_enabled=row["public_booking_enabled"],
                        status=RecordStatus(row["status"]),
                    )
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT service_id, clinic_id, code, title_key, duration_minutes, specialty_required, status
                        FROM core_reference.services
                        """
                    )
                )
            ).mappings():
                repo.upsert_service(
                    Service(
                        service_id=row["service_id"],
                        clinic_id=row["clinic_id"],
                        code=row["code"],
                        title_key=row["title_key"],
                        duration_minutes=row["duration_minutes"],
                        specialty_required=row["specialty_required"],
                        status=RecordStatus(row["status"]),
                    )
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT doctor_access_code_id, clinic_id, doctor_id, code, status, expires_at, max_uses, service_scope, branch_scope
                        FROM core_reference.doctor_access_codes
                        """
                    )
                )
            ).mappings():
                repo.upsert_doctor_access_code(
                    DoctorAccessCode(
                        doctor_access_code_id=row["doctor_access_code_id"],
                        clinic_id=row["clinic_id"],
                        doctor_id=row["doctor_id"],
                        code=row["code"],
                        status=RecordStatus(row["status"]),
                        expires_at=row["expires_at"],
                        max_uses=row["max_uses"],
                        service_scope=row["service_scope"],
                        branch_scope=row["branch_scope"],
                    )
                )
        await engine.dispose()
        return repo


class DbAccessRepository(InMemoryAccessRepository):
    @classmethod
    async def load(cls, db_config) -> "DbAccessRepository":
        repo = cls()
        engine = create_engine(db_config)
        async with engine.connect() as conn:
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT actor_id, actor_type, display_name, status, locale
                        FROM access_identity.actor_identities
                        """
                    )
                )
            ).mappings():
                repo.upsert_actor_identity(
                    ActorIdentity(
                        actor_id=row["actor_id"],
                        actor_type=ActorType(row["actor_type"]),
                        display_name=row["display_name"],
                        status=ActorStatus(row["status"]),
                        locale=row["locale"],
                    )
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT telegram_binding_id, actor_id, telegram_user_id, telegram_username, first_seen_at, last_seen_at, is_primary, is_active
                        FROM access_identity.telegram_bindings
                        """
                    )
                )
            ).mappings():
                repo.upsert_telegram_binding(
                    TelegramBinding(
                        telegram_binding_id=row["telegram_binding_id"],
                        actor_id=row["actor_id"],
                        telegram_user_id=row["telegram_user_id"],
                        telegram_username=row["telegram_username"],
                        first_seen_at=row["first_seen_at"],
                        last_seen_at=row["last_seen_at"],
                        is_primary=row["is_primary"],
                        is_active=row["is_active"],
                    )
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT staff_id, actor_id, clinic_id, full_name, display_name, staff_status, primary_branch_id
                        FROM access_identity.staff_members
                        """
                    )
                )
            ).mappings():
                repo.upsert_staff_member(
                    StaffMember(
                        staff_id=row["staff_id"],
                        actor_id=row["actor_id"],
                        clinic_id=row["clinic_id"],
                        full_name=row["full_name"],
                        display_name=row["display_name"],
                        staff_status=StaffStatus(row["staff_status"]),
                        primary_branch_id=row["primary_branch_id"],
                    )
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT role_assignment_id, staff_id, clinic_id, role_code, branch_id, scope_type, scope_ref, granted_by_actor_id, granted_at, revoked_at, is_active
                        FROM access_identity.clinic_role_assignments
                        """
                    )
                )
            ).mappings():
                repo.upsert_role_assignment(
                    ClinicRoleAssignment(
                        role_assignment_id=row["role_assignment_id"],
                        staff_id=row["staff_id"],
                        clinic_id=row["clinic_id"],
                        role_code=RoleCode(row["role_code"]),
                        branch_id=row["branch_id"],
                        scope_type=row["scope_type"],
                        scope_ref=row["scope_ref"],
                        granted_by_actor_id=row["granted_by_actor_id"],
                        granted_at=row["granted_at"],
                        revoked_at=row["revoked_at"],
                        is_active=row["is_active"],
                    )
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT doctor_profile_id, doctor_id, staff_id, clinic_id, branch_id, specialty_code,
                               active_for_booking, active_for_clinical_work
                        FROM access_identity.doctor_profiles
                        """
                    )
                )
            ).mappings():
                repo.upsert_doctor_profile(
                    DoctorProfile(
                        doctor_profile_id=row["doctor_profile_id"],
                        doctor_id=row["doctor_id"],
                        staff_id=row["staff_id"],
                        clinic_id=row["clinic_id"],
                        branch_id=row["branch_id"],
                        specialty_code=row["specialty_code"],
                        active_for_booking=row["active_for_booking"],
                        active_for_clinical_work=row["active_for_clinical_work"],
                    )
                )
        await engine.dispose()
        return repo


class DbPolicyRepository(InMemoryPolicyRepository):
    @classmethod
    async def load(cls, db_config) -> "DbPolicyRepository":
        repo = cls()
        engine = create_engine(db_config)
        async with engine.connect() as conn:
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT policy_set_id, policy_family, scope_type, scope_ref, status, version
                        FROM policy_config.policy_sets
                        """
                    )
                )
            ).mappings():
                repo.upsert_policy_set(
                    PolicySet(
                        policy_set_id=row["policy_set_id"],
                        policy_family=row["policy_family"],
                        scope_type=row["scope_type"],
                        scope_ref=row["scope_ref"],
                        status=PolicyStatus(row["status"]),
                        version=row["version"],
                    )
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT policy_value_id, policy_set_id, policy_key, value_type, value_json, is_override
                        FROM policy_config.policy_values
                        """
                    )
                )
            ).mappings():
                repo.add_policy_value(
                    PolicyValue(
                        policy_value_id=row["policy_value_id"],
                        policy_set_id=row["policy_set_id"],
                        policy_key=row["policy_key"],
                        value_type=row["value_type"],
                        value_json=row["value_json"],
                        is_override=row["is_override"],
                    )
                )
            for row in (
                await conn.execute(
                    text(
                        """
                        SELECT feature_flag_id, scope_type, scope_ref, flag_key, enabled, reason
                        FROM policy_config.feature_flags
                        """
                    )
                )
            ).mappings():
                repo.add_feature_flag(
                    FeatureFlag(
                        feature_flag_id=row["feature_flag_id"],
                        scope_type=row["scope_type"],
                        scope_ref=row["scope_ref"],
                        flag_key=row["flag_key"],
                        enabled=row["enabled"],
                        reason=row["reason"],
                    )
                )
        await engine.dispose()
        return repo


async def seed_stack_data(db_config, path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    engine = create_engine(db_config)
    async with engine.begin() as conn:
        for row in payload.get("clinics", []):
            await conn.execute(
                text(
                    """
                INSERT INTO core_reference.clinics (clinic_id, code, display_name, timezone, default_locale, status)
                VALUES (:clinic_id, :code, :display_name, :timezone, :default_locale, :status)
                ON CONFLICT (clinic_id) DO UPDATE SET
                  code=EXCLUDED.code,
                  display_name=EXCLUDED.display_name,
                  timezone=EXCLUDED.timezone,
                  default_locale=EXCLUDED.default_locale,
                  status=EXCLUDED.status,
                  updated_at=NOW()
                """
                ),
                row,
            )
        await _seed_rows(conn, payload)
    await engine.dispose()
    return {key: len(payload.get(key, [])) for key in payload}


async def _seed_rows(conn, payload: dict) -> None:
    statements = {
        "branches": ("core_reference.branches", ["branch_id", "clinic_id", "display_name", "address_text", "timezone", "status"]),
        "doctors": (
            "core_reference.doctors",
            ["doctor_id", "clinic_id", "branch_id", "display_name", "specialty_code", "public_booking_enabled", "status"],
        ),
        "services": (
            "core_reference.services",
            ["service_id", "clinic_id", "code", "title_key", "duration_minutes", "specialty_required", "status"],
        ),
        "doctor_access_codes": (
            "core_reference.doctor_access_codes",
            ["doctor_access_code_id", "clinic_id", "doctor_id", "code", "status", "expires_at", "max_uses", "service_scope", "branch_scope"],
        ),
        "actor_identities": ("access_identity.actor_identities", ["actor_id", "actor_type", "display_name", "locale", "status"]),
        "telegram_bindings": (
            "access_identity.telegram_bindings",
            [
                "telegram_binding_id",
                "actor_id",
                "telegram_user_id",
                "telegram_username",
                "first_seen_at",
                "last_seen_at",
                "is_primary",
                "is_active",
            ],
        ),
        "staff_members": (
            "access_identity.staff_members",
            ["staff_id", "actor_id", "clinic_id", "full_name", "display_name", "staff_status", "primary_branch_id"],
        ),
        "clinic_role_assignments": (
            "access_identity.clinic_role_assignments",
            [
                "role_assignment_id",
                "staff_id",
                "clinic_id",
                "branch_id",
                "role_code",
                "scope_type",
                "scope_ref",
                "granted_by_actor_id",
                "granted_at",
                "revoked_at",
                "is_active",
            ],
        ),
        "policy_sets": (
            "policy_config.policy_sets",
            ["policy_set_id", "policy_family", "scope_type", "scope_ref", "status", "version"],
        ),
        "policy_values": (
            "policy_config.policy_values",
            [
                "policy_value_id",
                "policy_set_id",
                "policy_key",
                "value_type",
                "value_json",
                "is_override",
                "effective_from",
                "effective_to",
            ],
        ),
        "feature_flags": ("policy_config.feature_flags", ["feature_flag_id", "scope_type", "scope_ref", "flag_key", "enabled", "reason"]),
    }

    for key, (table, columns) in statements.items():
        for row in payload.get(key, []):
            col_csv = ", ".join(columns)
            values = ", ".join(f":{name}" for name in columns)
            updates = ", ".join(f"{name}=EXCLUDED.{name}" for name in columns if name not in {columns[0]})
            await conn.execute(
                text(f"INSERT INTO {table} ({col_csv}) VALUES ({values}) ON CONFLICT ({columns[0]}) DO UPDATE SET {updates}"),
                {name: row.get(name) for name in columns},
            )
