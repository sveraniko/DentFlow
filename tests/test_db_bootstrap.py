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


@pytest.mark.asyncio
async def test_db_bootstrap_creates_all_schemas_and_stack1_stack2_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine()
    monkeypatch.setattr(db_bootstrap, "create_engine", lambda config: engine)

    await db_bootstrap.bootstrap_database(object())

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
