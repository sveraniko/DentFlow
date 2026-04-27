from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

from app.infrastructure.db import booking_repository


class _Conn:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict]] = []

    async def execute(self, stmt, params):
        self.executed.append((str(stmt), params))


class _Ctx:
    def __init__(self, conn):
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

    async def dispose(self):
        return None


def test_stack3_seed_bootstrap_path_is_coherent(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine()
    monkeypatch.setattr(booking_repository, "create_engine", lambda _: engine)

    counts = asyncio.run(booking_repository.seed_stack3_booking(object(), Path("seeds/stack3_booking.json")))

    assert counts["booking_sessions"] >= 1
    assert counts["bookings"] >= 4
    assert counts["booking_status_history"] >= 4
    inserts = "\n".join(sql for sql, _ in engine.conn.executed)
    assert "INSERT INTO booking.bookings" in inserts
    assert "INSERT INTO booking.booking_status_history" in inserts
