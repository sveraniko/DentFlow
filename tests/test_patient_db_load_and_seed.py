from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytest.importorskip("sqlalchemy")

from app.application.patient import PatientRegistryService
from app.infrastructure.db import patient_repository


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _Conn:
    def __init__(self, rows_by_table: dict[str, list[dict]] | None = None):
        self.rows_by_table = rows_by_table or {}
        self.calls: list[tuple[str, dict | None]] = []

    async def execute(self, stmt, params=None):
        sql = " ".join(str(stmt).split())
        self.calls.append((sql, params))
        if "FROM core_patient.patients" in sql:
            return _Result(self.rows_by_table.get("patients", []))
        if "FROM core_patient.patient_contacts" in sql:
            return _Result(self.rows_by_table.get("contacts", []))
        if "FROM core_patient.patient_preferences" in sql:
            return _Result(self.rows_by_table.get("preferences", []))
        if "FROM core_patient.patient_flags" in sql:
            return _Result(self.rows_by_table.get("flags", []))
        if "FROM core_patient.patient_photos" in sql:
            return _Result(self.rows_by_table.get("photos", []))
        if "FROM core_patient.patient_medical_summaries" in sql:
            return _Result(self.rows_by_table.get("summaries", []))
        if "FROM core_patient.patient_external_ids" in sql:
            return _Result(self.rows_by_table.get("external_ids", []))
        return _Result([])


class _Ctx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Engine:
    def __init__(self, conn):
        self.conn = conn

    def begin(self):
        return _Ctx(self.conn)

    def connect(self):
        return _Ctx(self.conn)

    async def dispose(self):
        return None


def test_seed_stack2_defaults_timestamps_and_not_null_flag_set_at(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _Conn()
    monkeypatch.setattr(patient_repository, "create_engine", lambda _: _Engine(conn))

    payload = {
        "patients": [
            {
                "patient_id": "pat_1",
                "clinic_id": "clinic_main",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "full_name_legal": "Ada Lovelace",
                "display_name": "Ada",
            }
        ],
        "patient_flags": [
            {"patient_flag_id": "pf_1", "patient_id": "pat_1", "flag_type": "allergy", "flag_severity": "high"}
        ],
        "patient_medical_summaries": [{"patient_medical_summary_id": "pms_1", "patient_id": "pat_1"}],
    }
    import asyncio
    asyncio.run(patient_repository.seed_stack2_patients(object(), payload))

    flag_insert = [params for sql, params in conn.calls if "INSERT INTO core_patient.patient_flags" in sql][0]
    summary_insert = [params for sql, params in conn.calls if "INSERT INTO core_patient.patient_medical_summaries" in sql][0]
    assert flag_insert["set_at"] == patient_repository.DEFAULT_SEED_TIMESTAMP
    assert summary_insert["created_at"] == patient_repository.DEFAULT_SEED_TIMESTAMP
    assert summary_insert["last_updated_at"] == patient_repository.DEFAULT_SEED_TIMESTAMP


def test_patient_repository_load_hydrates_from_db_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = {
        "patients": [
            {
                "patient_id": "pat_1",
                "clinic_id": "clinic_main",
                "patient_number": "P-1",
                "full_name_legal": "Ada Lovelace",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "middle_name": None,
                "display_name": "Ada",
                "birth_date": None,
                "sex_marker": None,
                "status": "active",
                "first_seen_at": None,
                "last_seen_at": None,
            }
        ],
        "contacts": [
            {
                "patient_contact_id": "pc_1",
                "patient_id": "pat_1",
                "contact_type": "phone",
                "contact_value": "+1 (555) 100-2000",
                "normalized_value": "15551002000",
                "is_primary": True,
                "is_verified": True,
                "is_active": True,
                "notes": None,
            }
        ],
        "preferences": [
            {
                "patient_preference_id": "pp_1",
                "patient_id": "pat_1",
                "preferred_language": "en",
                "preferred_reminder_channel": "telegram",
                "allow_sms": True,
                "allow_telegram": True,
                "allow_call": False,
                "allow_email": False,
                "marketing_opt_in": False,
                "contact_time_window": {"from": "09:00", "to": "18:00"},
            }
        ],
        "flags": [
            {
                "patient_flag_id": "pf_1",
                "patient_id": "pat_1",
                "flag_type": "allergy",
                "flag_severity": "high",
                "is_active": True,
                "set_by_actor_id": None,
                "set_at": ts,
                "expires_at": None,
                "note": "note",
            }
        ],
        "photos": [
            {
                "patient_photo_id": "pho_1",
                "patient_id": "pat_1",
                "media_asset_id": None,
                "external_ref": "s3://a.jpg",
                "is_primary": True,
                "captured_at": None,
                "source_type": "manual_upload",
            }
        ],
        "summaries": [
            {
                "patient_medical_summary_id": "pms_1",
                "patient_id": "pat_1",
                "allergy_summary": "penicillin",
                "chronic_conditions_summary": None,
                "contraindication_summary": None,
                "current_primary_dental_issue_summary": None,
                "important_history_summary": None,
                "last_updated_by_actor_id": None,
                "last_updated_at": ts,
                "created_at": ts,
            }
        ],
        "external_ids": [
            {
                "patient_external_id_id": "pex_1",
                "patient_id": "pat_1",
                "external_system": "legacy",
                "external_id": "L-1",
                "is_primary": True,
                "last_synced_at": ts,
            }
        ],
    }
    conn = _Conn(rows)
    monkeypatch.setattr(patient_repository, "create_engine", lambda _: _Engine(conn))
    import asyncio
    repo = asyncio.run(patient_repository.DbPatientRegistryRepository.load(object()))
    service = PatientRegistryService(repo)

    assert service.get_patient("pat_1") is not None
    assert service.find_by_exact_contact(contact_type="phone", contact_value="+1 555 100 2000") is not None
    assert service.get_preferences("pat_1") is not None
    assert len(service.active_flags("pat_1")) == 1
    assert service.get_primary_photo("pat_1") is not None
    assert service.get_medical_summary("pat_1") is not None
    assert service.find_by_external_id(external_system="legacy", external_id="L-1") is not None
    assert all("SELECT *" not in sql for sql, _ in conn.calls)


def test_db_upsert_paths_use_patient_identity_conflicts(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _Conn()
    monkeypatch.setattr(patient_repository, "create_engine", lambda _: _Engine(conn))
    service = patient_repository.DbPatientRegistryService(patient_repository.DbPatientRegistryRepository(object()))
    import asyncio

    async def _run() -> None:
        patient = await service.create_patient_db(
            clinic_id="clinic_main",
            patient_id="pat_1",
            first_name="Ada",
            last_name="Lovelace",
            full_name_legal="Ada Lovelace",
            display_name="Ada",
        )
        await service.upsert_contact_db(patient_id=patient.patient_id, contact_type="phone", contact_value="+1 (555) 100-2000")
        await service.upsert_preferences_db(patient_id=patient.patient_id, preferred_language="en")
        await service.upsert_medical_summary_db(patient_id=patient.patient_id, allergy_summary="none")
        await service.upsert_external_id_db(patient_id=patient.patient_id, external_system="legacy", external_id="L-1")

    asyncio.run(_run())

    sql_text = "\n".join(sql for sql, _ in conn.calls)
    assert "ON CONFLICT (patient_id, contact_type, normalized_value) DO UPDATE SET" in sql_text
    assert "ON CONFLICT (patient_id) DO UPDATE SET" in sql_text
    assert "ON CONFLICT (patient_id, external_system) DO UPDATE SET" in sql_text
