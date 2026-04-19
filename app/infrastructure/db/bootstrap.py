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
    "recommendation",
    "care_commerce",
    "media_docs",
    "integration",
    "analytics_raw",
    "owner_views",
    "admin_views",
    "platform",
    "system_runtime",
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
    CREATE TABLE IF NOT EXISTS clinical.patient_charts (
      chart_id TEXT PRIMARY KEY,
      patient_id TEXT NOT NULL REFERENCES core_patient.patients(patient_id),
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      chart_number TEXT NULL,
      opened_at TIMESTAMPTZ NOT NULL,
      status TEXT NOT NULL,
      primary_doctor_id TEXT NULL REFERENCES core_reference.doctors(doctor_id),
      notes_summary TEXT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_patient_charts_active_patient_clinic
    ON clinical.patient_charts (patient_id, clinic_id)
    WHERE status='active'
    """,
    """
    CREATE TABLE IF NOT EXISTS clinical.clinical_encounters (
      encounter_id TEXT PRIMARY KEY,
      chart_id TEXT NOT NULL REFERENCES clinical.patient_charts(chart_id) ON DELETE CASCADE,
      booking_id TEXT NULL REFERENCES booking.bookings(booking_id) ON DELETE SET NULL,
      doctor_id TEXT NOT NULL REFERENCES core_reference.doctors(doctor_id),
      opened_at TIMESTAMPTZ NOT NULL,
      closed_at TIMESTAMPTZ NULL,
      status TEXT NOT NULL,
      chief_complaint_snapshot TEXT NULL,
      findings_summary TEXT NULL,
      assessment_summary TEXT NULL,
      plan_summary TEXT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_clinical_encounters_chart_status_opened
    ON clinical.clinical_encounters (chart_id, status, opened_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS clinical.presenting_complaints (
      complaint_id TEXT PRIMARY KEY,
      chart_id TEXT NOT NULL REFERENCES clinical.patient_charts(chart_id) ON DELETE CASCADE,
      encounter_id TEXT NULL REFERENCES clinical.clinical_encounters(encounter_id) ON DELETE SET NULL,
      booking_id TEXT NULL REFERENCES booking.bookings(booking_id) ON DELETE SET NULL,
      complaint_text TEXT NOT NULL,
      onset_description TEXT NULL,
      context_note TEXT NULL,
      recorded_by_actor_id TEXT NULL REFERENCES access_identity.actor_identities(actor_id),
      recorded_at TIMESTAMPTZ NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_presenting_complaints_chart_recorded
    ON clinical.presenting_complaints (chart_id, recorded_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS clinical.encounter_notes (
      encounter_note_id TEXT PRIMARY KEY,
      encounter_id TEXT NOT NULL REFERENCES clinical.clinical_encounters(encounter_id) ON DELETE CASCADE,
      note_type TEXT NOT NULL,
      note_text TEXT NOT NULL,
      recorded_by_actor_id TEXT NULL REFERENCES access_identity.actor_identities(actor_id),
      recorded_at TIMESTAMPTZ NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_encounter_notes_encounter_recorded
    ON clinical.encounter_notes (encounter_id, recorded_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS clinical.diagnoses (
      diagnosis_id TEXT PRIMARY KEY,
      chart_id TEXT NOT NULL REFERENCES clinical.patient_charts(chart_id) ON DELETE CASCADE,
      encounter_id TEXT NULL REFERENCES clinical.clinical_encounters(encounter_id) ON DELETE SET NULL,
      diagnosis_code TEXT NULL,
      diagnosis_text TEXT NOT NULL,
      is_primary BOOLEAN NOT NULL DEFAULT FALSE,
      version_no INTEGER NOT NULL DEFAULT 1,
      is_current BOOLEAN NOT NULL DEFAULT TRUE,
      status TEXT NOT NULL,
      supersedes_diagnosis_id TEXT NULL REFERENCES clinical.diagnoses(diagnosis_id),
      superseded_at TIMESTAMPTZ NULL,
      recorded_by_actor_id TEXT NULL REFERENCES access_identity.actor_identities(actor_id),
      recorded_at TIMESTAMPTZ NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_diagnoses_chart_primary_recorded
    ON clinical.diagnoses (chart_id, is_primary, recorded_at DESC)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_diagnoses_current_primary_per_chart
    ON clinical.diagnoses (chart_id)
    WHERE is_primary=TRUE AND is_current=TRUE
    """,
    """
    CREATE TABLE IF NOT EXISTS clinical.treatment_plans (
      treatment_plan_id TEXT PRIMARY KEY,
      chart_id TEXT NOT NULL REFERENCES clinical.patient_charts(chart_id) ON DELETE CASCADE,
      encounter_id TEXT NULL REFERENCES clinical.clinical_encounters(encounter_id) ON DELETE SET NULL,
      title TEXT NOT NULL,
      plan_text TEXT NOT NULL,
      version_no INTEGER NOT NULL DEFAULT 1,
      is_current BOOLEAN NOT NULL DEFAULT TRUE,
      status TEXT NOT NULL,
      supersedes_treatment_plan_id TEXT NULL REFERENCES clinical.treatment_plans(treatment_plan_id),
      superseded_at TIMESTAMPTZ NULL,
      estimated_cost_amount NUMERIC(12,2) NULL,
      currency_code TEXT NULL,
      approved_by_patient_at TIMESTAMPTZ NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_treatment_plans_chart_status_updated
    ON clinical.treatment_plans (chart_id, status, updated_at DESC)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_treatment_plans_current_per_chart
    ON clinical.treatment_plans (chart_id)
    WHERE is_current=TRUE
    """,
    """
    CREATE TABLE IF NOT EXISTS clinical.imaging_references (
      imaging_ref_id TEXT PRIMARY KEY,
      chart_id TEXT NOT NULL REFERENCES clinical.patient_charts(chart_id) ON DELETE CASCADE,
      encounter_id TEXT NULL REFERENCES clinical.clinical_encounters(encounter_id) ON DELETE SET NULL,
      imaging_type TEXT NOT NULL,
      media_asset_id TEXT NULL,
      external_url TEXT NULL,
      description TEXT NULL,
      taken_at TIMESTAMPTZ NULL,
      uploaded_at TIMESTAMPTZ NOT NULL,
      uploaded_by_actor_id TEXT NULL REFERENCES access_identity.actor_identities(actor_id),
      is_primary_for_case BOOLEAN NOT NULL DEFAULT FALSE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      CHECK (media_asset_id IS NOT NULL OR external_url IS NOT NULL)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_imaging_references_chart_uploaded
    ON clinical.imaging_references (chart_id, uploaded_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS clinical.odontogram_snapshots (
      odontogram_snapshot_id TEXT PRIMARY KEY,
      chart_id TEXT NOT NULL REFERENCES clinical.patient_charts(chart_id) ON DELETE CASCADE,
      encounter_id TEXT NULL REFERENCES clinical.clinical_encounters(encounter_id) ON DELETE SET NULL,
      snapshot_payload_json JSONB NOT NULL,
      recorded_at TIMESTAMPTZ NOT NULL,
      recorded_by_actor_id TEXT NULL REFERENCES access_identity.actor_identities(actor_id),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_odontogram_snapshots_chart_recorded
    ON clinical.odontogram_snapshots (chart_id, recorded_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS recommendation.recommendations (
      recommendation_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      patient_id TEXT NOT NULL REFERENCES core_patient.patients(patient_id),
      booking_id TEXT NULL REFERENCES booking.bookings(booking_id) ON DELETE SET NULL,
      encounter_id TEXT NULL REFERENCES clinical.clinical_encounters(encounter_id) ON DELETE SET NULL,
      chart_id TEXT NULL REFERENCES clinical.patient_charts(chart_id) ON DELETE SET NULL,
      issued_by_actor_id TEXT NULL REFERENCES access_identity.actor_identities(actor_id),
      source_kind TEXT NOT NULL,
      recommendation_type TEXT NOT NULL,
      title TEXT NOT NULL,
      body_text TEXT NOT NULL,
      rationale_text TEXT NULL,
      status TEXT NOT NULL,
      issued_at TIMESTAMPTZ NULL,
      viewed_at TIMESTAMPTZ NULL,
      acknowledged_at TIMESTAMPTZ NULL,
      accepted_at TIMESTAMPTZ NULL,
      declined_at TIMESTAMPTZ NULL,
      expired_at TIMESTAMPTZ NULL,
      withdrawn_at TIMESTAMPTZ NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_recommendations_patient_created
    ON recommendation.recommendations (patient_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_recommendations_booking_created
    ON recommendation.recommendations (booking_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_recommendations_chart_created
    ON recommendation.recommendations (chart_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS care_commerce.products (
      care_product_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      sku TEXT NOT NULL,
      product_code TEXT NULL,
      title_key TEXT NOT NULL,
      description_key TEXT NULL,
      category TEXT NOT NULL,
      use_case_tag TEXT NULL,
      price_amount INTEGER NOT NULL,
      currency_code TEXT NOT NULL,
      status TEXT NOT NULL,
      pickup_supported BOOLEAN NOT NULL DEFAULT TRUE,
      delivery_supported BOOLEAN NOT NULL DEFAULT FALSE,
      sort_order INTEGER NULL,
      available_qty INTEGER NULL,
      media_asset_id TEXT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE (clinic_id, sku)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_care_products_clinic_status
    ON care_commerce.products (clinic_id, status, sort_order)
    """,
    """
    CREATE TABLE IF NOT EXISTS care_commerce.recommendation_product_links (
      recommendation_product_link_id TEXT PRIMARY KEY,
      recommendation_id TEXT NOT NULL REFERENCES recommendation.recommendations(recommendation_id) ON DELETE CASCADE,
      care_product_id TEXT NOT NULL REFERENCES care_commerce.products(care_product_id) ON DELETE CASCADE,
      relevance_rank INTEGER NOT NULL DEFAULT 100,
      justification_key TEXT NULL,
      justification_text_key TEXT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(recommendation_id, care_product_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_recommendation_product_links_recommendation
    ON care_commerce.recommendation_product_links (recommendation_id, relevance_rank, created_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS care_commerce.care_orders (
      care_order_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      patient_id TEXT NOT NULL REFERENCES core_patient.patients(patient_id),
      booking_id TEXT NULL REFERENCES booking.bookings(booking_id) ON DELETE SET NULL,
      recommendation_id TEXT NULL REFERENCES recommendation.recommendations(recommendation_id) ON DELETE SET NULL,
      status TEXT NOT NULL,
      payment_mode TEXT NOT NULL,
      pickup_branch_id TEXT NULL REFERENCES core_reference.branches(branch_id) ON DELETE SET NULL,
      total_amount INTEGER NOT NULL,
      currency_code TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      confirmed_at TIMESTAMPTZ NULL,
      paid_at TIMESTAMPTZ NULL,
      ready_for_pickup_at TIMESTAMPTZ NULL,
      issued_at TIMESTAMPTZ NULL,
      fulfilled_at TIMESTAMPTZ NULL,
      canceled_at TIMESTAMPTZ NULL,
      expired_at TIMESTAMPTZ NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_care_orders_patient_created
    ON care_commerce.care_orders (clinic_id, patient_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_care_orders_status_created
    ON care_commerce.care_orders (clinic_id, status, created_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS care_commerce.care_order_items (
      care_order_item_id TEXT PRIMARY KEY,
      care_order_id TEXT NOT NULL REFERENCES care_commerce.care_orders(care_order_id) ON DELETE CASCADE,
      care_product_id TEXT NOT NULL REFERENCES care_commerce.products(care_product_id),
      quantity INTEGER NOT NULL CHECK (quantity > 0),
      unit_price INTEGER NOT NULL,
      line_total INTEGER NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS care_commerce.care_reservations (
      care_reservation_id TEXT PRIMARY KEY,
      care_order_id TEXT NOT NULL REFERENCES care_commerce.care_orders(care_order_id) ON DELETE CASCADE,
      care_product_id TEXT NOT NULL REFERENCES care_commerce.products(care_product_id),
      branch_id TEXT NOT NULL REFERENCES core_reference.branches(branch_id),
      status TEXT NOT NULL,
      reserved_qty INTEGER NOT NULL CHECK (reserved_qty > 0),
      expires_at TIMESTAMPTZ NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      released_at TIMESTAMPTZ NULL,
      consumed_at TIMESTAMPTZ NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_care_reservations_order_status
    ON care_commerce.care_reservations (care_order_id, status, created_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS care_commerce.branch_product_availability (
      branch_product_availability_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      branch_id TEXT NOT NULL REFERENCES core_reference.branches(branch_id) ON DELETE CASCADE,
      care_product_id TEXT NOT NULL REFERENCES care_commerce.products(care_product_id) ON DELETE CASCADE,
      available_qty INTEGER NOT NULL DEFAULT 0 CHECK (available_qty >= 0),
      reserved_qty INTEGER NOT NULL DEFAULT 0 CHECK (reserved_qty >= 0),
      status TEXT NOT NULL DEFAULT 'active',
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(branch_id, care_product_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_branch_product_availability_branch_status
    ON care_commerce.branch_product_availability (branch_id, status, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS care_commerce.product_i18n (
      care_product_i18n_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      care_product_id TEXT NOT NULL REFERENCES care_commerce.products(care_product_id) ON DELETE CASCADE,
      locale TEXT NOT NULL,
      title TEXT NOT NULL,
      description TEXT NOT NULL,
      short_label TEXT NULL,
      justification_text TEXT NULL,
      usage_hint TEXT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(care_product_id, locale)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS care_commerce.recommendation_sets (
      care_recommendation_set_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      set_code TEXT NOT NULL,
      status TEXT NOT NULL,
      title_ru TEXT NULL,
      title_en TEXT NULL,
      description_ru TEXT NULL,
      description_en TEXT NULL,
      sort_order INTEGER NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(clinic_id, set_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS care_commerce.recommendation_set_items (
      care_recommendation_set_item_id TEXT PRIMARY KEY,
      care_recommendation_set_id TEXT NOT NULL REFERENCES care_commerce.recommendation_sets(care_recommendation_set_id) ON DELETE CASCADE,
      care_product_id TEXT NOT NULL REFERENCES care_commerce.products(care_product_id) ON DELETE CASCADE,
      position INTEGER NOT NULL,
      quantity INTEGER NOT NULL DEFAULT 1,
      notes TEXT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(care_recommendation_set_id, care_product_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS care_commerce.recommendation_links (
      care_recommendation_link_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      recommendation_type TEXT NOT NULL,
      target_kind TEXT NOT NULL,
      target_code TEXT NOT NULL,
      relevance_rank INTEGER NOT NULL,
      active BOOLEAN NOT NULL DEFAULT TRUE,
      justification_key TEXT NULL,
      justification_text_ru TEXT NULL,
      justification_text_en TEXT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(clinic_id, recommendation_type, target_kind, target_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS care_commerce.recommendation_manual_targets (
      recommendation_id TEXT PRIMARY KEY REFERENCES recommendation.recommendations(recommendation_id) ON DELETE CASCADE,
      target_kind TEXT NOT NULL,
      target_code TEXT NOT NULL,
      justification_text TEXT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS care_commerce.catalog_settings (
      care_catalog_setting_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL REFERENCES core_reference.clinics(clinic_id),
      key TEXT NOT NULL,
      value TEXT NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(clinic_id, key)
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
    """
    CREATE TABLE IF NOT EXISTS system_runtime.event_outbox (
      outbox_event_id BIGSERIAL PRIMARY KEY,
      event_id TEXT NOT NULL UNIQUE,
      event_name TEXT NOT NULL,
      event_version INTEGER NOT NULL DEFAULT 1,
      producer_context TEXT NOT NULL,
      clinic_id TEXT NULL,
      entity_type TEXT NOT NULL,
      entity_id TEXT NOT NULL,
      actor_type TEXT NULL,
      actor_id TEXT NULL,
      correlation_id TEXT NULL,
      causation_id TEXT NULL,
      payload_json JSONB NOT NULL,
      occurred_at TIMESTAMPTZ NOT NULL,
      produced_at TIMESTAMPTZ NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      last_error_text TEXT NULL,
      dispatched_at TIMESTAMPTZ NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      CHECK (status IN ('pending','processing','processed','failed'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS system_runtime.projector_checkpoints (
      projector_name TEXT PRIMARY KEY,
      last_outbox_event_id BIGINT NOT NULL DEFAULT 0,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS system_runtime.projector_failures (
      projector_failure_id BIGSERIAL PRIMARY KEY,
      projector_name TEXT NOT NULL,
      outbox_event_id BIGINT NOT NULL,
      event_id TEXT NOT NULL,
      error_text TEXT NOT NULL,
      failed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,


    """
    CREATE TABLE IF NOT EXISTS admin_views.today_schedule (
      clinic_id TEXT NOT NULL,
      branch_id TEXT NULL,
      booking_id TEXT PRIMARY KEY,
      patient_id TEXT NOT NULL,
      doctor_id TEXT NOT NULL,
      service_id TEXT NOT NULL,
      local_service_date DATE NOT NULL,
      local_service_time TEXT NOT NULL,
      scheduled_start_at_utc TIMESTAMPTZ NOT NULL,
      scheduled_end_at_utc TIMESTAMPTZ NULL,
      booking_status TEXT NOT NULL,
      confirmation_state TEXT NOT NULL,
      checkin_state TEXT NOT NULL,
      no_show_flag BOOLEAN NOT NULL DEFAULT FALSE,
      reschedule_requested_flag BOOLEAN NOT NULL DEFAULT FALSE,
      waitlist_linked_flag BOOLEAN NULL,
      recommendation_linked_flag BOOLEAN NULL,
      care_order_linked_flag BOOLEAN NULL,
      patient_display_name TEXT NOT NULL,
      doctor_display_name TEXT NOT NULL,
      service_label TEXT NOT NULL,
      branch_label TEXT NOT NULL,
      compact_flags_summary TEXT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_today_schedule_clinic_day
    ON admin_views.today_schedule (clinic_id, local_service_date, scheduled_start_at_utc)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_today_schedule_clinic_branch_day
    ON admin_views.today_schedule (clinic_id, branch_id, local_service_date, scheduled_start_at_utc)
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_views.confirmation_queue (
      clinic_id TEXT NOT NULL,
      branch_id TEXT NULL,
      booking_id TEXT PRIMARY KEY,
      patient_id TEXT NOT NULL,
      doctor_id TEXT NOT NULL,
      local_service_date DATE NOT NULL,
      local_service_time TEXT NOT NULL,
      booking_status TEXT NOT NULL,
      confirmation_signal TEXT NOT NULL,
      reminder_state_summary TEXT NULL,
      no_response_flag BOOLEAN NOT NULL DEFAULT FALSE,
      patient_display_name TEXT NOT NULL,
      doctor_display_name TEXT NOT NULL,
      service_label TEXT NOT NULL,
      branch_label TEXT NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_confirmation_queue_clinic_day
    ON admin_views.confirmation_queue (clinic_id, local_service_date, no_response_flag, local_service_time)
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_views.reschedule_queue (
      clinic_id TEXT NOT NULL,
      branch_id TEXT NULL,
      booking_id TEXT PRIMARY KEY,
      patient_id TEXT NOT NULL,
      doctor_id TEXT NOT NULL,
      local_service_date DATE NOT NULL,
      local_service_time TEXT NOT NULL,
      booking_status TEXT NOT NULL,
      reschedule_context TEXT NULL,
      patient_display_name TEXT NOT NULL,
      doctor_display_name TEXT NOT NULL,
      service_label TEXT NOT NULL,
      branch_label TEXT NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_reschedule_queue_clinic_day
    ON admin_views.reschedule_queue (clinic_id, local_service_date, local_service_time)
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_views.waitlist_queue (
      clinic_id TEXT NOT NULL,
      branch_id TEXT NULL,
      waitlist_entry_id TEXT PRIMARY KEY,
      patient_id TEXT NULL,
      preferred_doctor_id TEXT NULL,
      preferred_service_id TEXT NULL,
      preferred_time_window_summary TEXT NULL,
      status TEXT NOT NULL,
      patient_display_name TEXT NOT NULL,
      doctor_display_name TEXT NULL,
      service_label TEXT NULL,
      priority_rank INTEGER NOT NULL DEFAULT 0,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_waitlist_queue_clinic_status
    ON admin_views.waitlist_queue (clinic_id, status, priority_rank DESC, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_views.care_pickup_queue (
      clinic_id TEXT NOT NULL,
      branch_id TEXT NULL,
      care_order_id TEXT PRIMARY KEY,
      patient_id TEXT NOT NULL,
      pickup_status TEXT NOT NULL,
      local_ready_date DATE NULL,
      local_ready_time TEXT NULL,
      patient_display_name TEXT NOT NULL,
      branch_label TEXT NOT NULL,
      compact_item_summary TEXT NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_care_pickup_queue_clinic_branch_status
    ON admin_views.care_pickup_queue (clinic_id, branch_id, pickup_status, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_views.ops_issue_queue (
      clinic_id TEXT NOT NULL,
      branch_id TEXT NULL,
      issue_type TEXT NOT NULL,
      issue_ref_id TEXT NOT NULL,
      issue_status TEXT NOT NULL,
      severity TEXT NOT NULL,
      patient_id TEXT NULL,
      booking_id TEXT NULL,
      care_order_id TEXT NULL,
      local_related_date DATE NULL,
      local_related_time TEXT NULL,
      summary_text TEXT NOT NULL,
      patient_display_name TEXT NULL,
      severity_rank INTEGER NOT NULL DEFAULT 1,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(issue_type, issue_ref_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_admin_ops_issue_queue_clinic_status
    ON admin_views.ops_issue_queue (clinic_id, issue_status, severity_rank DESC, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS owner_views.daily_clinic_metrics (
      clinic_id TEXT NOT NULL,
      metrics_date DATE NOT NULL,
      new_patients_count INTEGER NOT NULL DEFAULT 0,
      bookings_created_count INTEGER NOT NULL DEFAULT 0,
      bookings_confirmed_count INTEGER NOT NULL DEFAULT 0,
      bookings_canceled_count INTEGER NOT NULL DEFAULT 0,
      bookings_completed_count INTEGER NOT NULL DEFAULT 0,
      bookings_no_show_count INTEGER NOT NULL DEFAULT 0,
      bookings_reschedule_requested_count INTEGER NOT NULL DEFAULT 0,
      reminders_scheduled_count INTEGER NOT NULL DEFAULT 0,
      reminders_sent_count INTEGER NOT NULL DEFAULT 0,
      reminders_acknowledged_count INTEGER NOT NULL DEFAULT 0,
      reminders_failed_count INTEGER NOT NULL DEFAULT 0,
      charts_opened_count INTEGER NOT NULL DEFAULT 0,
      encounters_created_count INTEGER NOT NULL DEFAULT 0,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (clinic_id, metrics_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS owner_views.daily_doctor_metrics (
      clinic_id TEXT NOT NULL,
      metrics_date DATE NOT NULL,
      doctor_id TEXT NOT NULL,
      bookings_created_count INTEGER NOT NULL DEFAULT 0,
      bookings_confirmed_count INTEGER NOT NULL DEFAULT 0,
      bookings_completed_count INTEGER NOT NULL DEFAULT 0,
      bookings_no_show_count INTEGER NOT NULL DEFAULT 0,
      bookings_reschedule_requested_count INTEGER NOT NULL DEFAULT 0,
      reminders_sent_count INTEGER NOT NULL DEFAULT 0,
      reminders_failed_count INTEGER NOT NULL DEFAULT 0,
      encounters_created_count INTEGER NOT NULL DEFAULT 0,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (clinic_id, metrics_date, doctor_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS owner_views.daily_service_metrics (
      clinic_id TEXT NOT NULL,
      metrics_date DATE NOT NULL,
      service_id TEXT NOT NULL,
      bookings_created_count INTEGER NOT NULL DEFAULT 0,
      bookings_confirmed_count INTEGER NOT NULL DEFAULT 0,
      bookings_completed_count INTEGER NOT NULL DEFAULT 0,
      bookings_no_show_count INTEGER NOT NULL DEFAULT 0,
      bookings_reschedule_requested_count INTEGER NOT NULL DEFAULT 0,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (clinic_id, metrics_date, service_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS owner_views.owner_alerts (
      owner_alert_id TEXT PRIMARY KEY,
      clinic_id TEXT NOT NULL,
      alert_type TEXT NOT NULL,
      severity TEXT NOT NULL,
      status TEXT NOT NULL,
      entity_type TEXT NULL,
      entity_id TEXT NULL,
      alert_date DATE NOT NULL,
      summary_text TEXT NOT NULL,
      details_json JSONB NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_owner_alerts_clinic_status_date
    ON owner_views.owner_alerts (clinic_id, status, alert_date DESC)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_owner_alerts_open_dedupe
    ON owner_views.owner_alerts (clinic_id, alert_type, alert_date, COALESCE(entity_type,''), COALESCE(entity_id,''))
    WHERE status='open'
    """,
    """
    CREATE TABLE IF NOT EXISTS analytics_raw.event_ledger (
      ledger_event_id BIGSERIAL PRIMARY KEY,
      event_id TEXT NOT NULL UNIQUE,
      event_name TEXT NOT NULL,
      clinic_id TEXT NULL,
      entity_type TEXT NOT NULL,
      entity_id TEXT NOT NULL,
      actor_type TEXT NULL,
      actor_id TEXT NULL,
      occurred_at TIMESTAMPTZ NOT NULL,
      payload_summary_json JSONB NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
