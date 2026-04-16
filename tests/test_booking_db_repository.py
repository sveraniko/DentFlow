from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

pytest.importorskip("sqlalchemy")

from app.domain.booking import Booking, BookingSession, BookingStatusHistory
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


def test_db_booking_repository_upserts_core_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine()
    monkeypatch.setattr(booking_repository, "create_engine", lambda _: engine)

    repo = booking_repository.DbBookingRepository(object())

    session = BookingSession(
        booking_session_id="s1",
        clinic_id="clinic_main",
        branch_id="branch_central",
        telegram_user_id=3001,
        resolved_patient_id="patient_sergey_ivanov",
        status="active",
        route_type="service_first",
        service_id="service_consult",
        urgency_type=None,
        requested_date_type=None,
        requested_date=None,
        time_window=None,
        doctor_preference_type=None,
        doctor_id=None,
        doctor_code_raw=None,
        selected_slot_id=None,
        selected_hold_id=None,
        contact_phone_snapshot=None,
        notes=None,
        expires_at=datetime(2026, 4, 20, 9, 30, tzinfo=timezone.utc),
        created_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
    )
    asyncio.run(repo.upsert_booking_session(session))

    booking = Booking(
        booking_id="b1",
        clinic_id="clinic_main",
        branch_id="branch_central",
        patient_id="patient_sergey_ivanov",
        doctor_id="doctor_anna",
        service_id="service_consult",
        slot_id=None,
        booking_mode="patient_bot",
        source_channel="telegram",
        scheduled_start_at=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
        scheduled_end_at=datetime(2026, 4, 20, 10, 30, tzinfo=timezone.utc),
        status="pending_confirmation",
        reason_for_visit_short=None,
        patient_note=None,
        confirmation_required=True,
        confirmed_at=None,
        canceled_at=None,
        checked_in_at=None,
        in_service_at=None,
        completed_at=None,
        no_show_at=None,
        created_at=datetime(2026, 4, 20, 9, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 20, 9, 1, tzinfo=timezone.utc),
    )
    asyncio.run(repo.upsert_booking(booking))

    asyncio.run(
        repo.append_booking_status_history(
        BookingStatusHistory(
            booking_status_history_id="h1",
            booking_id="b1",
            old_status=None,
            new_status="pending_confirmation",
            reason_code="created",
            actor_type="system",
            actor_id="seed",
            occurred_at=datetime(2026, 4, 20, 9, 1, tzinfo=timezone.utc),
        )
    )
    )

    sql_blob = "\n".join(s for s, _ in engine.conn.executed)
    assert "INSERT INTO booking.booking_sessions" in sql_blob
    assert "INSERT INTO booking.bookings" in sql_blob
    assert "INSERT INTO booking.booking_status_history" in sql_blob
    assert engine.conn.executed[1][1]["patient_id"] == "patient_sergey_ivanov"


def test_db_booking_repository_load_and_list_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    session_row = {
        "booking_session_id": "s1",
        "clinic_id": "clinic_main",
        "branch_id": "branch_central",
        "telegram_user_id": 3001,
        "resolved_patient_id": "patient_sergey_ivanov",
        "status": "active",
        "route_type": "service_first",
        "service_id": "service_consult",
        "urgency_type": None,
        "requested_date_type": None,
        "requested_date": None,
        "time_window": None,
        "doctor_preference_type": None,
        "doctor_id": None,
        "doctor_code_raw": None,
        "selected_slot_id": None,
        "selected_hold_id": None,
        "contact_phone_snapshot": None,
        "notes": None,
        "expires_at": datetime(2026, 4, 20, 9, 30, tzinfo=timezone.utc),
        "created_at": datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
    }
    booking_row = {
        "booking_id": "b1",
        "clinic_id": "clinic_main",
        "branch_id": "branch_central",
        "patient_id": "patient_sergey_ivanov",
        "doctor_id": "doctor_anna",
        "service_id": "service_consult",
        "slot_id": None,
        "booking_mode": "patient_bot",
        "source_channel": "telegram",
        "scheduled_start_at": datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
        "scheduled_end_at": datetime(2026, 4, 20, 10, 30, tzinfo=timezone.utc),
        "status": "pending_confirmation",
        "reason_for_visit_short": None,
        "patient_note": None,
        "confirmation_required": True,
        "confirmed_at": None,
        "canceled_at": None,
        "checked_in_at": None,
        "in_service_at": None,
        "completed_at": None,
        "no_show_at": None,
        "created_at": datetime(2026, 4, 20, 9, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 4, 20, 9, 1, tzinfo=timezone.utc),
    }

    async def _fetch_one(_, sql: str, __):
        if "booking.booking_sessions" in sql:
            return session_row
        if "FROM booking.bookings" in sql:
            return booking_row
        return None

    async def _fetch_all(_, sql: str, __):
        if "FROM booking.bookings" in sql:
            return [booking_row]
        return []

    monkeypatch.setattr(booking_repository, "_fetch_one", _fetch_one)
    monkeypatch.setattr(booking_repository, "_fetch_all", _fetch_all)

    repo = booking_repository.DbBookingRepository(object())
    session = asyncio.run(repo.get_booking_session("s1"))
    booking = asyncio.run(repo.get_booking("b1"))
    by_patient = asyncio.run(repo.list_bookings_by_patient(patient_id="patient_sergey_ivanov"))

    assert session and session.booking_session_id == "s1"
    assert booking and booking.booking_id == "b1"
    assert by_patient and by_patient[0].status == "pending_confirmation"
