import asyncio

import pytest

pytest.importorskip("sqlalchemy")

from app.infrastructure.db import patient_repository


class _Result:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def __iter__(self):
        if self._row is None:
            return iter(())
        if isinstance(self._row, list):
            return iter(self._row)
        return iter([self._row])

    def first(self):
        if isinstance(self._row, list):
            return self._row[0] if self._row else None
        return self._row


class _Conn:
    def __init__(self, row):
        self.row = row
        self.executed: list[tuple[str, dict]] = []

    async def execute(self, stmt, params):
        self.executed.append((str(stmt), params))
        return _Result(self.row)


class _Ctx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Engine:
    def __init__(self, row):
        self.conn = _Conn(row)

    def connect(self):
        return _Ctx(self.conn)

    async def dispose(self):
        return None


def test_find_by_exact_contact_uses_normalized_value(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine({"patient_id": "p1", "display_name": "Test"})
    monkeypatch.setattr(patient_repository, "create_engine", lambda _: engine)

    row = asyncio.run(patient_repository.find_patient_by_exact_contact(object(), contact_type="phone", contact_value="+7 (901) 222-33-44"))

    assert row and row["patient_id"] == "p1"
    assert engine.conn.executed[0][1]["normalized"] == "79012223344"


def test_find_by_external_id(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine({"patient_id": "p2"})
    monkeypatch.setattr(patient_repository, "create_engine", lambda _: engine)

    row = asyncio.run(patient_repository.find_patient_by_external_id(object(), external_system="legacy", external_id="X-1"))

    assert row and row["patient_id"] == "p2"


def test_find_patients_by_exact_contact_returns_all_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine(
        [
            {"patient_id": "p1", "clinic_id": "clinic_main", "display_name": "Parent", "normalized_lookup_value": "79012223344"},
            {"patient_id": "p2", "clinic_id": "clinic_main", "display_name": "Child", "normalized_lookup_value": "79012223344"},
        ]
    )
    monkeypatch.setattr(patient_repository, "create_engine", lambda _: engine)

    rows = asyncio.run(
        patient_repository.find_patients_by_exact_contact(object(), contact_type="phone", contact_value="+7 (901) 222-33-44")
    )

    assert [r["patient_id"] for r in rows] == ["p1", "p2"]
