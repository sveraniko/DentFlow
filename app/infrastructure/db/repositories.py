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
    RoleCode,
    StaffMember,
    StaffStatus,
    TelegramBinding,
)
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, DoctorAccessCode, RecordStatus, Service
from app.domain.policy_config.models import FeatureFlag, PolicySet, PolicyValue
from app.infrastructure.db.engine import create_engine


class DbClinicReferenceRepository(InMemoryClinicReferenceRepository):
    @classmethod
    async def load(cls, db_config) -> "DbClinicReferenceRepository":
        repo = cls()
        engine = create_engine(db_config)
        async with engine.connect() as conn:
            for row in (await conn.execute(text("SELECT * FROM core_reference.clinics"))).mappings():
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
            for row in (await conn.execute(text("SELECT * FROM core_reference.branches"))).mappings():
                repo.upsert_branch(Branch(**{**row, "status": RecordStatus(row["status"])}))
            for row in (await conn.execute(text("SELECT * FROM core_reference.doctors"))).mappings():
                repo.upsert_doctor(Doctor(**{**row, "status": RecordStatus(row["status"])}))
            for row in (await conn.execute(text("SELECT * FROM core_reference.services"))).mappings():
                repo.upsert_service(Service(**{**row, "status": RecordStatus(row["status"])}))
            for row in (await conn.execute(text("SELECT * FROM core_reference.doctor_access_codes"))).mappings():
                repo.upsert_doctor_access_code(
                    DoctorAccessCode(
                        **{**row, "status": RecordStatus(row["status"]), "service_scope": row["service_scope"], "branch_scope": row["branch_scope"]}
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
            for row in (await conn.execute(text("SELECT * FROM access_identity.actor_identities"))).mappings():
                repo.upsert_actor_identity(
                    ActorIdentity(
                        actor_id=row["actor_id"],
                        actor_type=ActorType(row["actor_type"]),
                        display_name=row["display_name"],
                        status=ActorStatus(row["status"]),
                        locale=row["locale"],
                    )
                )
            for row in (await conn.execute(text("SELECT * FROM access_identity.telegram_bindings"))).mappings():
                repo.upsert_telegram_binding(TelegramBinding(**row))
            for row in (await conn.execute(text("SELECT * FROM access_identity.staff_members"))).mappings():
                repo.upsert_staff_member(
                    StaffMember(
                        **{**row, "staff_status": StaffStatus(row["staff_status"])},
                    )
                )
            for row in (await conn.execute(text("SELECT * FROM access_identity.clinic_role_assignments"))).mappings():
                repo.upsert_role_assignment(ClinicRoleAssignment(**{**row, "role_code": RoleCode(row["role_code"])}))
        await engine.dispose()
        return repo


class DbPolicyRepository(InMemoryPolicyRepository):
    @classmethod
    async def load(cls, db_config) -> "DbPolicyRepository":
        repo = cls()
        engine = create_engine(db_config)
        async with engine.connect() as conn:
            for row in (await conn.execute(text("SELECT * FROM policy_config.policy_sets"))).mappings():
                repo.upsert_policy_set(PolicySet(**row))
            for row in (await conn.execute(text("SELECT * FROM policy_config.policy_values"))).mappings():
                repo.add_policy_value(PolicyValue(**row))
            for row in (await conn.execute(text("SELECT * FROM policy_config.feature_flags"))).mappings():
                repo.add_feature_flag(FeatureFlag(**row))
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
