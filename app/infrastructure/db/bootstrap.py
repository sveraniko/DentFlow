import logging

from sqlalchemy import text

from app.infrastructure.db.engine import create_engine

SCHEMAS: tuple[str, ...] = (
    "core_reference",
    "access_identity",
    "policy_config",
    "core_patient",
    "search",
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
    CREATE TABLE IF NOT EXISTS core_patient.patients (
      patient_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      patient_number TEXT NULL,
      full_name_legal TEXT NOT NULL,
      first_name TEXT NOT NULL,
      last_name TEXT NOT NULL,
      middle_name TEXT NULL,
      display_name TEXT NOT NULL,
      birth_date DATE NULL,
      sex_marker TEXT NULL,
      status TEXT NOT NULL DEFAULT 'active',
      first_seen_at TIMESTAMPTZ NULL,
      last_seen_at TIMESTAMPTZ NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(clinic_id, patient_number)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS core_patient.patient_contacts (
      patient_contact_id TEXT PRIMARY KEY,
      patient_id TEXT NOT NULL REFERENCES core_patient.patients(patient_id),
      contact_type TEXT NOT NULL,
      contact_value TEXT NOT NULL,
      normalized_value TEXT NOT NULL,
      is_primary BOOLEAN NOT NULL DEFAULT FALSE,
      is_verified BOOLEAN NOT NULL DEFAULT FALSE,
      is_active BOOLEAN NOT NULL DEFAULT TRUE,
      notes TEXT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(patient_id, contact_type, normalized_value)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS core_patient.patient_preferences (
      patient_preference_id TEXT PRIMARY KEY,
      patient_id TEXT NOT NULL UNIQUE REFERENCES core_patient.patients(patient_id),
      preferred_language TEXT NULL,
      preferred_reminder_channel TEXT NULL,
      allow_sms BOOLEAN NOT NULL DEFAULT TRUE,
      allow_telegram BOOLEAN NOT NULL DEFAULT TRUE,
      allow_call BOOLEAN NOT NULL DEFAULT FALSE,
      allow_email BOOLEAN NOT NULL DEFAULT FALSE,
      marketing_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
      contact_time_window JSONB NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS core_patient.patient_flags (
      patient_flag_id TEXT PRIMARY KEY,
      patient_id TEXT NOT NULL REFERENCES core_patient.patients(patient_id),
      flag_type TEXT NOT NULL,
      flag_severity TEXT NOT NULL,
      is_active BOOLEAN NOT NULL DEFAULT TRUE,
      set_by_actor_id TEXT NULL REFERENCES access_identity.actor_identities(actor_id),
      set_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      expires_at TIMESTAMPTZ NULL,
      note TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS core_patient.patient_photos (
      patient_photo_id TEXT PRIMARY KEY,
      patient_id TEXT NOT NULL REFERENCES core_patient.patients(patient_id),
      media_asset_id TEXT NULL,
      external_ref TEXT NULL,
      is_primary BOOLEAN NOT NULL DEFAULT FALSE,
      captured_at TIMESTAMPTZ NULL,
      source_type TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS core_patient.patient_medical_summaries (
      patient_medical_summary_id TEXT PRIMARY KEY,
      patient_id TEXT NOT NULL UNIQUE REFERENCES core_patient.patients(patient_id),
      allergy_summary TEXT NULL,
      chronic_conditions_summary TEXT NULL,
      contraindication_summary TEXT NULL,
      current_primary_dental_issue_summary TEXT NULL,
      important_history_summary TEXT NULL,
      last_updated_by_actor_id TEXT NULL REFERENCES access_identity.actor_identities(actor_id),
      last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS core_patient.patient_external_ids (
      patient_external_id_id TEXT PRIMARY KEY,
      patient_id TEXT NOT NULL REFERENCES core_patient.patients(patient_id),
      external_system TEXT NOT NULL,
      external_id TEXT NOT NULL,
      is_primary BOOLEAN NOT NULL DEFAULT FALSE,
      last_synced_at TIMESTAMPTZ NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(external_system, external_id),
      UNIQUE(patient_id, external_system)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS search.patient_search_projection (
      patient_id TEXT PRIMARY KEY REFERENCES core_patient.patients(patient_id) ON DELETE CASCADE,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      patient_number TEXT NULL,
      display_name TEXT NOT NULL,
      full_name_legal TEXT NULL,
      first_name TEXT NULL,
      last_name TEXT NULL,
      middle_name TEXT NULL,
      name_normalized TEXT NOT NULL,
      name_tokens_normalized TEXT NOT NULL,
      translit_tokens TEXT NOT NULL,
      external_id_normalized TEXT NULL,
      primary_phone_normalized TEXT NULL,
      preferred_language TEXT NULL,
      primary_photo_ref TEXT NULL,
      active_flags_summary TEXT NULL,
      status TEXT NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_patient_search_projection_clinic_updated
    ON search.patient_search_projection (clinic_id, updated_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_patient_search_projection_phone
    ON search.patient_search_projection (clinic_id, primary_phone_normalized)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_patient_search_projection_number
    ON search.patient_search_projection (clinic_id, patient_number)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_patient_search_projection_external_id
    ON search.patient_search_projection (clinic_id, external_id_normalized)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_patient_search_projection_name_norm
    ON search.patient_search_projection (clinic_id, name_normalized)
    """,
    """
    CREATE TABLE IF NOT EXISTS search.doctor_search_projection (
      doctor_id TEXT PRIMARY KEY REFERENCES core_reference.doctors(doctor_id) ON DELETE CASCADE,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      branch_id TEXT NULL REFERENCES core_reference.branches(branch_id),
      display_name TEXT NOT NULL,
      name_normalized TEXT NOT NULL,
      name_tokens_normalized TEXT NOT NULL,
      translit_tokens TEXT NOT NULL,
      specialty_code TEXT NULL,
      specialty_label TEXT NULL,
      public_booking_enabled BOOLEAN NOT NULL DEFAULT TRUE,
      status TEXT NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_doctor_search_projection_clinic_updated
    ON search.doctor_search_projection (clinic_id, updated_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_doctor_search_projection_name_norm
    ON search.doctor_search_projection (clinic_id, name_normalized)
    """,
    """
    CREATE TABLE IF NOT EXISTS search.service_search_projection (
      service_id TEXT PRIMARY KEY REFERENCES core_reference.services(service_id) ON DELETE CASCADE,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      code TEXT NOT NULL,
      title_key TEXT NOT NULL,
      localized_search_text_ru TEXT NOT NULL,
      localized_search_text_en TEXT NOT NULL,
      specialty_required BOOLEAN NOT NULL DEFAULT FALSE,
      status TEXT NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_service_search_projection_clinic_updated
    ON search.service_search_projection (clinic_id, updated_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_service_search_projection_code
    ON search.service_search_projection (clinic_id, code)
    """,
    """
    CREATE TABLE IF NOT EXISTS booking.booking_sessions (
      booking_session_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      branch_id TEXT NULL REFERENCES core_reference.branches(branch_id),
      telegram_user_id BIGINT NOT NULL,
      resolved_patient_id TEXT NULL REFERENCES core_patient.patients(patient_id),
      status TEXT NOT NULL,
      route_type TEXT NOT NULL,
      service_id TEXT NULL REFERENCES core_reference.services(service_id),
      urgency_type TEXT NULL,
      requested_date_type TEXT NULL,
      requested_date DATE NULL,
      time_window TEXT NULL,
      doctor_preference_type TEXT NULL,
      doctor_id TEXT NULL REFERENCES core_reference.doctors(doctor_id),
      doctor_code_raw TEXT NULL,
      selected_slot_id TEXT NULL,
      selected_hold_id TEXT NULL,
      contact_phone_snapshot TEXT NULL,
      notes TEXT NULL,
      expires_at TIMESTAMPTZ NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_booking_sessions_telegram
    ON booking.booking_sessions (clinic_id, telegram_user_id, updated_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_booking_sessions_status_expires
    ON booking.booking_sessions (status, expires_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS booking.session_events (
      session_event_id TEXT PRIMARY KEY,
      booking_session_id TEXT NOT NULL REFERENCES booking.booking_sessions(booking_session_id) ON DELETE CASCADE,
      event_name TEXT NOT NULL,
      payload_json JSONB NULL,
      actor_type TEXT NULL,
      actor_id TEXT NULL,
      occurred_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_session_events_session
    ON booking.session_events (booking_session_id, occurred_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS booking.availability_slots (
      slot_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      branch_id TEXT NULL REFERENCES core_reference.branches(branch_id),
      doctor_id TEXT NOT NULL REFERENCES core_reference.doctors(doctor_id),
      start_at TIMESTAMPTZ NOT NULL,
      end_at TIMESTAMPTZ NOT NULL,
      status TEXT NOT NULL,
      visibility_policy TEXT NOT NULL,
      service_scope JSONB NULL,
      source_ref TEXT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      CHECK (end_at > start_at)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_availability_slots_doctor_start
    ON booking.availability_slots (clinic_id, doctor_id, start_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS booking.slot_holds (
      slot_hold_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      slot_id TEXT NOT NULL REFERENCES booking.availability_slots(slot_id) ON DELETE CASCADE,
      booking_session_id TEXT NOT NULL REFERENCES booking.booking_sessions(booking_session_id) ON DELETE CASCADE,
      telegram_user_id BIGINT NOT NULL,
      status TEXT NOT NULL,
      expires_at TIMESTAMPTZ NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_slot_holds_slot_status
    ON booking.slot_holds (slot_id, status)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_slot_holds_active_slot
    ON booking.slot_holds (slot_id)
    WHERE status = 'active'
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_slot_holds_active_session
    ON booking.slot_holds (booking_session_id)
    WHERE status = 'active'
    """,
    """
    CREATE TABLE IF NOT EXISTS booking.bookings (
      booking_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      branch_id TEXT NULL REFERENCES core_reference.branches(branch_id),
      patient_id TEXT NOT NULL REFERENCES core_patient.patients(patient_id),
      doctor_id TEXT NOT NULL REFERENCES core_reference.doctors(doctor_id),
      service_id TEXT NOT NULL REFERENCES core_reference.services(service_id),
      slot_id TEXT NULL REFERENCES booking.availability_slots(slot_id),
      booking_mode TEXT NOT NULL,
      source_channel TEXT NOT NULL,
      scheduled_start_at TIMESTAMPTZ NOT NULL,
      scheduled_end_at TIMESTAMPTZ NOT NULL,
      status TEXT NOT NULL,
      reason_for_visit_short TEXT NULL,
      patient_note TEXT NULL,
      confirmation_required BOOLEAN NOT NULL DEFAULT TRUE,
      confirmed_at TIMESTAMPTZ NULL,
      canceled_at TIMESTAMPTZ NULL,
      checked_in_at TIMESTAMPTZ NULL,
      in_service_at TIMESTAMPTZ NULL,
      completed_at TIMESTAMPTZ NULL,
      no_show_at TIMESTAMPTZ NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      CHECK (scheduled_end_at > scheduled_start_at),
      CHECK (status IN ('pending_confirmation', 'confirmed', 'reschedule_requested', 'canceled', 'checked_in', 'in_service', 'completed', 'no_show'))
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_bookings_patient_start
    ON booking.bookings (clinic_id, patient_id, scheduled_start_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_bookings_doctor_start
    ON booking.bookings (clinic_id, doctor_id, scheduled_start_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_bookings_status_start
    ON booking.bookings (clinic_id, status, scheduled_start_at)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_bookings_live_slot
    ON booking.bookings (slot_id)
    WHERE slot_id IS NOT NULL
      AND status IN ('pending_confirmation', 'confirmed', 'reschedule_requested', 'checked_in', 'in_service')
    """,
    """
    CREATE TABLE IF NOT EXISTS booking.booking_status_history (
      booking_status_history_id TEXT PRIMARY KEY,
      booking_id TEXT NOT NULL REFERENCES booking.bookings(booking_id) ON DELETE CASCADE,
      old_status TEXT NULL,
      new_status TEXT NOT NULL,
      reason_code TEXT NULL,
      actor_type TEXT NULL,
      actor_id TEXT NULL,
      occurred_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_booking_status_history_booking
    ON booking.booking_status_history (booking_id, occurred_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS booking.waitlist_entries (
      waitlist_entry_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      branch_id TEXT NULL REFERENCES core_reference.branches(branch_id),
      patient_id TEXT NULL REFERENCES core_patient.patients(patient_id),
      telegram_user_id BIGINT NULL,
      service_id TEXT NOT NULL REFERENCES core_reference.services(service_id),
      doctor_id TEXT NULL REFERENCES core_reference.doctors(doctor_id),
      date_window JSONB NULL,
      time_window TEXT NULL,
      priority INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL,
      source_session_id TEXT NULL REFERENCES booking.booking_sessions(booking_session_id),
      notes TEXT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS booking.admin_escalations (
      admin_escalation_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      booking_session_id TEXT NOT NULL REFERENCES booking.booking_sessions(booking_session_id),
      patient_id TEXT NULL REFERENCES core_patient.patients(patient_id),
      reason_code TEXT NOT NULL,
      priority TEXT NOT NULL,
      status TEXT NOT NULL,
      assigned_to_actor_id TEXT NULL REFERENCES access_identity.actor_identities(actor_id),
      payload_summary JSONB NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
    """
    CREATE TABLE IF NOT EXISTS communication.reminder_jobs (
      reminder_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      patient_id TEXT NOT NULL REFERENCES core_patient.patients(patient_id),
      booking_id TEXT NULL REFERENCES booking.bookings(booking_id) ON DELETE SET NULL,
      care_order_id TEXT NULL,
      recommendation_id TEXT NULL,
      reminder_type TEXT NOT NULL,
      channel TEXT NOT NULL,
      status TEXT NOT NULL,
      scheduled_for TIMESTAMPTZ NOT NULL,
      payload_key TEXT NOT NULL,
      locale_at_send_time TEXT NULL,
      planning_group TEXT NULL,
      supersedes_reminder_id TEXT NULL REFERENCES communication.reminder_jobs(reminder_id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      queued_at TIMESTAMPTZ NULL,
      delivery_attempts_count INTEGER NOT NULL DEFAULT 0,
      last_error_code TEXT NULL,
      last_error_text TEXT NULL,
      last_failed_at TIMESTAMPTZ NULL,
      sent_at TIMESTAMPTZ NULL,
      acknowledged_at TIMESTAMPTZ NULL,
      canceled_at TIMESTAMPTZ NULL,
      cancel_reason_code TEXT NULL,
      CHECK (status IN ('scheduled', 'queued', 'sent', 'failed', 'acknowledged', 'canceled', 'expired'))
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_reminder_jobs_booking_status_scheduled
    ON communication.reminder_jobs (booking_id, status, scheduled_for)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_reminder_jobs_planning_group
    ON communication.reminder_jobs (planning_group, status, scheduled_for)
    """,
    """
    CREATE TABLE IF NOT EXISTS communication.message_deliveries (
      message_delivery_id TEXT PRIMARY KEY,
      reminder_id TEXT NULL REFERENCES communication.reminder_jobs(reminder_id) ON DELETE SET NULL,
      patient_id TEXT NOT NULL REFERENCES core_patient.patients(patient_id),
      channel TEXT NOT NULL,
      delivery_status TEXT NOT NULL,
      provider_message_id TEXT NULL,
      attempt_no INTEGER NOT NULL DEFAULT 1,
      error_text TEXT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_message_deliveries_reminder
    ON communication.message_deliveries (reminder_id, created_at DESC)
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
