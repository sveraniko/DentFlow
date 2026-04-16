import logging

from sqlalchemy import text

from app.infrastructure.db.engine import create_engine

SCHEMAS: tuple[str, ...] = (
    "core_reference",
    "access_identity",
    "policy_config",
    "core_patient",
    "booking",
    "communication",
    "clinical",
    "care_commerce",
    "media_docs",
    "integration",
    "analytics_raw",
    "owner_views",
    "platform",
)

STACK1_TABLES: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS core_reference.clinics (
      clinic_id TEXT PRIMARY KEY,
      code TEXT NOT NULL UNIQUE,
      display_name TEXT NOT NULL,
      timezone TEXT NOT NULL,
      default_locale TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS core_reference.branches (
      branch_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      display_name TEXT NOT NULL,
      address_text TEXT NOT NULL,
      timezone TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(clinic_id, display_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS core_reference.doctors (
      doctor_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      branch_id TEXT NULL REFERENCES core_reference.branches(branch_id),
      display_name TEXT NOT NULL,
      specialty_code TEXT NOT NULL,
      public_booking_enabled BOOLEAN NOT NULL DEFAULT TRUE,
      status TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(clinic_id, display_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS core_reference.services (
      service_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      code TEXT NOT NULL,
      title_key TEXT NOT NULL,
      duration_minutes INTEGER NOT NULL,
      specialty_required TEXT NULL,
      status TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(clinic_id, code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS core_reference.doctor_access_codes (
      doctor_access_code_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      doctor_id TEXT NOT NULL REFERENCES core_reference.doctors(doctor_id),
      code TEXT NOT NULL,
      status TEXT NOT NULL,
      expires_at TIMESTAMPTZ NULL,
      max_uses INTEGER NULL,
      service_scope JSONB NULL,
      branch_scope JSONB NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(clinic_id, code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS access_identity.actor_identities (
      actor_id TEXT PRIMARY KEY,
      actor_type TEXT NOT NULL,
      display_name TEXT NOT NULL,
      locale TEXT NULL,
      status TEXT NOT NULL DEFAULT 'active',
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS access_identity.telegram_bindings (
      telegram_binding_id TEXT PRIMARY KEY,
      actor_id TEXT NOT NULL REFERENCES access_identity.actor_identities(actor_id),
      telegram_user_id BIGINT NOT NULL UNIQUE,
      telegram_username TEXT NULL,
      first_seen_at TIMESTAMPTZ NULL,
      last_seen_at TIMESTAMPTZ NULL,
      is_primary BOOLEAN NOT NULL DEFAULT TRUE,
      is_active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS access_identity.staff_members (
      staff_id TEXT PRIMARY KEY,
      actor_id TEXT NOT NULL UNIQUE REFERENCES access_identity.actor_identities(actor_id),
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      full_name TEXT NOT NULL,
      display_name TEXT NOT NULL,
      staff_status TEXT NOT NULL DEFAULT 'active',
      primary_branch_id TEXT NULL REFERENCES core_reference.branches(branch_id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS access_identity.clinic_role_assignments (
      role_assignment_id TEXT PRIMARY KEY,
      staff_id TEXT NOT NULL REFERENCES access_identity.staff_members(staff_id),
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      branch_id TEXT NULL REFERENCES core_reference.branches(branch_id),
      role_code TEXT NOT NULL,
      scope_type TEXT NOT NULL DEFAULT 'clinic',
      scope_ref TEXT NULL,
      granted_by_actor_id TEXT NULL REFERENCES access_identity.actor_identities(actor_id),
      granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      revoked_at TIMESTAMPTZ NULL,
      is_active BOOLEAN NOT NULL DEFAULT TRUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS access_identity.doctor_profiles (
      doctor_profile_id TEXT PRIMARY KEY,
      doctor_id TEXT NOT NULL REFERENCES core_reference.doctors(doctor_id),
      staff_id TEXT NOT NULL UNIQUE REFERENCES access_identity.staff_members(staff_id),
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      branch_id TEXT NULL REFERENCES core_reference.branches(branch_id),
      specialty_code TEXT NULL,
      active_for_booking BOOLEAN NOT NULL DEFAULT TRUE,
      active_for_clinical_work BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS access_identity.owner_profiles (
      owner_profile_id TEXT PRIMARY KEY,
      staff_id TEXT NOT NULL UNIQUE REFERENCES access_identity.staff_members(staff_id),
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      owner_scope_kind TEXT NOT NULL DEFAULT 'clinic',
      analytics_scope TEXT NOT NULL DEFAULT 'clinic',
      cross_branch_enabled BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS access_identity.service_principals (
      service_principal_id TEXT PRIMARY KEY,
      principal_code TEXT NOT NULL UNIQUE,
      description TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active',
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS policy_config.policy_sets (
      policy_set_id TEXT PRIMARY KEY,
      policy_family TEXT NOT NULL,
      scope_type TEXT NOT NULL,
      scope_ref TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'active',
      version INTEGER NOT NULL DEFAULT 1,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(scope_type, scope_ref, policy_family)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS policy_config.policy_values (
      policy_value_id TEXT PRIMARY KEY,
      policy_set_id TEXT NOT NULL REFERENCES policy_config.policy_sets(policy_set_id),
      policy_key TEXT NOT NULL,
      value_type TEXT NOT NULL,
      value_json JSONB NOT NULL,
      is_override BOOLEAN NOT NULL DEFAULT FALSE,
      effective_from TIMESTAMPTZ NULL,
      effective_to TIMESTAMPTZ NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(policy_set_id, policy_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS policy_config.feature_flags (
      feature_flag_id TEXT PRIMARY KEY,
      scope_type TEXT NOT NULL,
      scope_ref TEXT NOT NULL,
      flag_key TEXT NOT NULL,
      enabled BOOLEAN NOT NULL,
      reason TEXT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(scope_type, scope_ref, flag_key)
    )
    """,
)


async def bootstrap_database(db_config) -> None:
    logger = logging.getLogger("dentflow.db.bootstrap")
    engine = create_engine(db_config)
    async with engine.begin() as conn:
        for schema in SCHEMAS:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            logger.info("schema ensured", extra={"extra": {"schema": schema}})
        for ddl in STACK1_TABLES:
            await conn.execute(text(ddl))
    await engine.dispose()
