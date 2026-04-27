from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import date, datetime, timezone
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


def _minimal_payload() -> dict:
    return {
        "booking_sessions": [
            {
                "booking_session_id": "bks_1",
                "requested_date": "2026-04-20",
                "expires_at": "2026-04-20T09:30:00Z",
                "created_at": "2026-04-20T09:00:00Z",
                "updated_at": "2026-04-20T09:10:00Z",
            }
        ],
        "availability_slots": [
            {
                "slot_id": "slot_anna_20260420_1000",
                "start_at": "2026-04-20T10:00:00Z",
                "end_at": "2026-04-20T10:30:00Z",
                "updated_at": "2026-04-20T08:00:00Z",
            }
        ],
        "bookings": [
            {
                "booking_id": "bkg_1",
                "scheduled_start_at": "2026-04-20T10:00:00Z",
                "scheduled_end_at": "2026-04-20T10:30:00Z",
                "created_at": "2026-04-20T09:11:00Z",
                "updated_at": "2026-04-20T09:12:00Z",
            }
        ],
        "waitlist_entries": [
            {
                "waitlist_entry_id": "wle_1",
                "date_window": {"from": "2026-04-21", "to": "2026-04-23"},
                "created_at": "2026-04-20T09:00:00Z",
                "updated_at": "2026-04-20T09:00:00Z",
            }
        ],
    }


def test_seed_stack3_default_static_mode_does_not_transform_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine()
    monkeypatch.setattr(booking_repository, "create_engine", lambda _: engine)

    asyncio.run(booking_repository.seed_stack3_booking(object(), Path("seeds/stack3_booking.json")))

    session_insert = next(params for sql, params in engine.conn.executed if "booking.booking_sessions" in sql)
    booking_insert = next(params for sql, params in engine.conn.executed if "booking.bookings" in sql)
    slot_insert = next(params for sql, params in engine.conn.executed if "booking.availability_slots" in sql)

    assert session_insert["requested_date"].isoformat() == "2026-04-20"
    assert booking_insert["scheduled_start_at"].isoformat().endswith("07:00:00+00:00")
    assert slot_insert["start_at"].isoformat().endswith("07:00:00+00:00")


def test_shift_stack3_seed_dates_shifts_datetime_and_date_fields() -> None:
    payload = _minimal_payload()
    shifted = booking_repository._shift_stack3_seed_dates(
        payload,
        now=datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc),
        start_offset_days=1,
    )

    shifted_slot = shifted["availability_slots"][0]
    shifted_booking = shifted["bookings"][0]
    shifted_session = shifted["booking_sessions"][0]
    shifted_waitlist = shifted["waitlist_entries"][0]

    assert shifted_slot["start_at"] == "2026-04-28T10:00:00Z"
    assert shifted_slot["end_at"] == "2026-04-28T10:30:00Z"
    assert shifted_booking["scheduled_start_at"] == "2026-04-28T10:00:00Z"
    assert shifted_booking["scheduled_end_at"] == "2026-04-28T10:30:00Z"
    assert shifted_session["requested_date"] == "2026-04-28"
    assert shifted_waitlist["date_window"]["from"] == "2026-04-29"
    assert shifted_waitlist["date_window"]["to"] == "2026-05-01"

    slot_start = datetime.fromisoformat(shifted_slot["start_at"].replace("Z", "+00:00"))
    slot_end = datetime.fromisoformat(shifted_slot["end_at"].replace("Z", "+00:00"))
    booking_start = datetime.fromisoformat(shifted_booking["scheduled_start_at"].replace("Z", "+00:00"))
    booking_end = datetime.fromisoformat(shifted_booking["scheduled_end_at"].replace("Z", "+00:00"))

    assert (slot_end - slot_start).total_seconds() == 30 * 60
    assert (booking_end - booking_start).total_seconds() == 30 * 60


def test_shift_stack3_seed_dates_does_not_mutate_original_payload() -> None:
    payload = _minimal_payload()
    original = deepcopy(payload)

    _ = booking_repository._shift_stack3_seed_dates(
        payload,
        now=datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc),
        start_offset_days=1,
    )

    assert payload == original


def test_shift_stack3_seed_dates_does_not_modify_ids() -> None:
    payload = _minimal_payload()

    shifted = booking_repository._shift_stack3_seed_dates(
        payload,
        now=datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc),
        start_offset_days=1,
    )

    assert shifted["availability_slots"][0]["slot_id"] == "slot_anna_20260420_1000"
    assert shifted["booking_sessions"][0]["booking_session_id"] == "bks_1"


def test_shift_stack3_seed_dates_respects_explicit_source_anchor_date() -> None:
    payload = _minimal_payload()

    shifted = booking_repository._shift_stack3_seed_dates(
        payload,
        now=datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc),
        start_offset_days=2,
        source_anchor_date=date(2026, 4, 22),
    )

    assert shifted["booking_sessions"][0]["requested_date"] == "2026-04-27"
