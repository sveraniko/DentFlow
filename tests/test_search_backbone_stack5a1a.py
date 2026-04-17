from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from app.application.search.models import SearchQuery
from app.infrastructure.search import postgres_backend as pg_backend
from app.projections.search.rebuilder import SearchProjectionRebuilder


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _Conn:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append(sql)
        if "FROM core_patient.patients" in sql:
            return _Result(
                [
                    {
                        "patient_id": "p1",
                        "clinic_id": "c1",
                        "patient_number": "PT-1",
                        "display_name": "Иван Иванов",
                        "full_name_legal": "Иван Иванов",
                        "first_name": "Иван",
                        "last_name": "Иванов",
                        "middle_name": None,
                        "status": "active",
                        "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                        "preferred_language": "ru",
                        "primary_phone_normalized": "+7 (999) 111-22-33",
                        "external_id_normalized": "ext-1",
                        "primary_photo_ref": "photo-1",
                        "active_flags_summary": "vip",
                    }
                ]
            )
        if "FROM core_reference.doctors" in sql:
            return _Result(
                [
                    {
                        "doctor_id": "d1",
                        "clinic_id": "c1",
                        "branch_id": "b1",
                        "display_name": "Доктор А",
                        "specialty_code": "ortho",
                        "specialty_label": "ortho",
                        "public_booking_enabled": True,
                        "status": "active",
                        "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                    }
                ]
            )
        if "FROM core_reference.services" in sql:
            return _Result(
                [
                    {
                        "service_id": "s1",
                        "clinic_id": "c1",
                        "code": "S1",
                        "title_key": "svc.cleaning",
                        "specialty_required": False,
                        "status": "active",
                        "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                    }
                ]
            )
        if "FROM search.patient_search_projection" in sql:
            rows = [
                {
                    "patient_id": "p_scope",
                    "clinic_id": params["clinic_id"],
                    "display_name": "Ivan",
                    "patient_number": "PT-9",
                    "primary_phone_normalized": "79991112233",
                    "active_flags_summary": "vip",
                    "status": "active",
                }
            ]
            return _Result(rows)
        if "FROM search.doctor_search_projection" in sql:
            return _Result([])
        if "FROM search.service_search_projection" in sql:
            return _Result([])
        return _Result([])


class _Ctx:
    def __init__(self, conn: _Conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Engine:
    def __init__(self):
        self.conn = _Conn()

    def begin(self):
        return _Ctx(self.conn)

    def connect(self):
        return _Ctx(self.conn)

    async def dispose(self):
        return None


def test_projection_rebuild_populates_all_tables(monkeypatch) -> None:
    engine = _Engine()
    monkeypatch.setattr("app.projections.search.rebuilder.create_engine", lambda _: engine)
    rebuilder = SearchProjectionRebuilder(db_config=object(), locales_path=Path("locales"))
    counts = asyncio.run(rebuilder.rebuild_all())
    assert counts == {"patients": 1, "doctors": 1, "services": 1}
    ddl = "\n".join(engine.conn.calls)
    assert "TRUNCATE TABLE search.patient_search_projection" in ddl
    assert "INSERT INTO search.patient_search_projection" in ddl
    assert "INSERT INTO search.doctor_search_projection" in ddl
    assert "INSERT INTO search.service_search_projection" in ddl


def test_postgres_search_is_clinic_scoped_and_supports_strict_and_fallback(monkeypatch) -> None:
    engine = _Engine()
    monkeypatch.setattr(pg_backend, "create_engine", lambda _: engine)
    backend = pg_backend.PostgresSearchBackend(db_config=object())

    strict = asyncio.run(backend.search_patients_strict(SearchQuery(clinic_id="clinic-x", query="PT-9")))
    fallback = asyncio.run(backend.search_patients(SearchQuery(clinic_id="clinic-x", query="ivan")))
    translit = asyncio.run(backend.search_patients(SearchQuery(clinic_id="clinic-x", query="ivanov")))

    assert strict and strict[0].clinic_id == "clinic-x"
    assert strict[0].patient_number == "PT-9"
    assert fallback and fallback[0].active_flags_summary == "vip"
    assert translit and translit[0].origin.value == "postgres_fallback"
