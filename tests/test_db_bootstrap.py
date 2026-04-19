import asyncio

import pytest

pytest.importorskip("sqlalchemy")

from app.infrastructure.db import bootstrap as db_bootstrap


class _Conn:
    def __init__(self) -> None:
        self.executed: list[str] = []

    async def execute(self, statement) -> None:
        self.executed.append(str(statement))


class _BeginCtx:
    def __init__(self, conn: _Conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Engine:
    def __init__(self) -> None:
        self.conn = _Conn()

    def begin(self):
        return _BeginCtx(self.conn)

    async def dispose(self) -> None:
        return None


def test_db_bootstrap_creates_all_schemas_and_stack1_stack2_stack3a_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine()
    monkeypatch.setattr(db_bootstrap, "create_engine", lambda config: engine)

    asyncio.run(db_bootstrap.bootstrap_database(object()))

    executed = "\n".join(engine.conn.executed)
    assert len(engine.conn.executed) == len(db_bootstrap.SCHEMAS) + len(db_bootstrap.STACK1_TABLES)
    assert "CREATE SCHEMA IF NOT EXISTS \"core_reference\"" in executed
    assert "CREATE TABLE IF NOT EXISTS core_reference.clinics" in executed
    assert "CREATE TABLE IF NOT EXISTS access_identity.actor_identities" in executed
    assert "CREATE TABLE IF NOT EXISTS policy_config.policy_sets" in executed



def test_stack2_patient_tables_declared() -> None:
    ddl = "\n".join(db_bootstrap.STACK1_TABLES)
    assert "CREATE TABLE IF NOT EXISTS core_patient.patients" in ddl
    assert "CREATE TABLE IF NOT EXISTS core_patient.patient_contacts" in ddl
    assert "CREATE TABLE IF NOT EXISTS core_patient.patient_preferences" in ddl
    assert "CREATE TABLE IF NOT EXISTS core_patient.patient_flags" in ddl
    assert "CREATE TABLE IF NOT EXISTS core_patient.patient_photos" in ddl
    assert "CREATE TABLE IF NOT EXISTS core_patient.patient_medical_summaries" in ddl
    assert "CREATE TABLE IF NOT EXISTS core_patient.patient_external_ids" in ddl
    assert "UNIQUE(patient_id, contact_type, normalized_value)" in ddl
    assert "patient_id TEXT NOT NULL UNIQUE REFERENCES core_patient.patients(patient_id)" in ddl
    assert "patient_id TEXT NOT NULL UNIQUE REFERENCES core_patient.patients(patient_id)" in ddl
    assert "UNIQUE(patient_id, external_system)" in ddl


def test_search_schema_and_projection_tables_declared() -> None:
    ddl = "\n".join(db_bootstrap.STACK1_TABLES)
    assert "search" in db_bootstrap.SCHEMAS
    assert "CREATE TABLE IF NOT EXISTS search.patient_search_projection" in ddl
    assert "CREATE TABLE IF NOT EXISTS search.doctor_search_projection" in ddl
    assert "CREATE TABLE IF NOT EXISTS search.service_search_projection" in ddl


def test_stack3a_booking_tables_declared() -> None:
    ddl = "\n".join(db_bootstrap.STACK1_TABLES)
    assert "CREATE TABLE IF NOT EXISTS booking.booking_sessions" in ddl
    assert "CREATE TABLE IF NOT EXISTS booking.session_events" in ddl
    assert "CREATE TABLE IF NOT EXISTS booking.availability_slots" in ddl
    assert "CREATE TABLE IF NOT EXISTS booking.slot_holds" in ddl
    assert "CREATE TABLE IF NOT EXISTS booking.bookings" in ddl
    assert "CREATE TABLE IF NOT EXISTS booking.booking_status_history" in ddl
    assert "CREATE TABLE IF NOT EXISTS booking.waitlist_entries" in ddl
    assert "CREATE TABLE IF NOT EXISTS booking.admin_escalations" in ddl
    assert "CHECK (status IN ('pending_confirmation', 'confirmed', 'reschedule_requested', 'canceled', 'checked_in', 'in_service', 'completed', 'no_show'))" in ddl
    assert "REFERENCES core_patient.patients(patient_id)" in ddl
    assert "CREATE TABLE IF NOT EXISTS booking.booking_patients" not in ddl
    assert "CREATE TABLE IF NOT EXISTS booking.patient_profiles" not in ddl

def test_stack7a_clinical_tables_declared() -> None:
    ddl = "\n".join(db_bootstrap.STACK1_TABLES)
    assert "CREATE TABLE IF NOT EXISTS clinical.patient_charts" in ddl
    assert "CREATE TABLE IF NOT EXISTS clinical.presenting_complaints" in ddl
    assert "CREATE TABLE IF NOT EXISTS clinical.clinical_encounters" in ddl
    assert "CREATE TABLE IF NOT EXISTS clinical.encounter_notes" in ddl
    assert "CREATE TABLE IF NOT EXISTS clinical.diagnoses" in ddl
    assert "CREATE TABLE IF NOT EXISTS clinical.treatment_plans" in ddl
    assert "CREATE TABLE IF NOT EXISTS clinical.imaging_references" in ddl
    assert "CREATE TABLE IF NOT EXISTS clinical.odontogram_snapshots" in ddl
    assert "WHERE status='active'" in ddl
    assert "version_no INTEGER NOT NULL DEFAULT 1" in ddl
    assert "is_current BOOLEAN NOT NULL DEFAULT TRUE" in ddl
    assert "uq_diagnoses_current_primary_per_chart" in ddl
    assert "uq_treatment_plans_current_per_chart" in ddl


def test_stack8a_runtime_event_tables_declared() -> None:
    ddl = "\n".join(db_bootstrap.STACK1_TABLES)
    assert "system_runtime" in db_bootstrap.SCHEMAS
    assert "CREATE TABLE IF NOT EXISTS system_runtime.event_outbox" in ddl
    assert "CREATE TABLE IF NOT EXISTS system_runtime.projector_checkpoints" in ddl
    assert "CREATE TABLE IF NOT EXISTS analytics_raw.event_ledger" in ddl


def test_stack9a_owner_projection_tables_declared() -> None:
    ddl = "\n".join(db_bootstrap.STACK1_TABLES)
    assert "CREATE TABLE IF NOT EXISTS owner_views.daily_clinic_metrics" in ddl
    assert "CREATE TABLE IF NOT EXISTS owner_views.daily_doctor_metrics" in ddl
    assert "CREATE TABLE IF NOT EXISTS owner_views.daily_service_metrics" in ddl
    assert "CREATE TABLE IF NOT EXISTS owner_views.owner_alerts" in ddl
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_owner_alerts_open_dedupe" in ddl


def test_aw1_admin_projection_tables_declared() -> None:
    ddl = "\n".join(db_bootstrap.STACK1_TABLES)
    assert "admin_views" in db_bootstrap.SCHEMAS
    assert "CREATE TABLE IF NOT EXISTS admin_views.today_schedule" in ddl
    assert "CREATE TABLE IF NOT EXISTS admin_views.confirmation_queue" in ddl
    assert "CREATE TABLE IF NOT EXISTS admin_views.reschedule_queue" in ddl
    assert "CREATE TABLE IF NOT EXISTS admin_views.waitlist_queue" in ddl
    assert "CREATE TABLE IF NOT EXISTS admin_views.care_pickup_queue" in ddl
    assert "CREATE TABLE IF NOT EXISTS admin_views.ops_issue_queue" in ddl


def test_aw5_google_calendar_projection_tables_declared() -> None:
    ddl = "\n".join(db_bootstrap.STACK1_TABLES)
    assert "integration" in db_bootstrap.SCHEMAS
    assert "CREATE TABLE IF NOT EXISTS integration.google_calendar_doctor_calendars" in ddl
    assert "CREATE TABLE IF NOT EXISTS integration.google_calendar_booking_event_map" in ddl
    assert "CHECK (sync_status IN ('synced', 'failed', 'canceled', 'cancel_failed'))" in ddl
