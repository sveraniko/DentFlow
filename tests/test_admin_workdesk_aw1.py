from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

import pytest

from app.application.admin.workdesk import AdminWorkdeskReadService, TodayScheduleRow, _resolve_timezone_from_conn
from app.domain.events import build_event
from app.projections.admin.workdesk_projector import AdminWorkdeskProjector


class _MappingsResult:
    def __init__(self, row=None, rows=None, scalar=None):
        self._row = row
        self._rows = rows or []
        self._scalar = scalar

    def mappings(self):
        return self

    def first(self):
        return self._row

    def all(self):
        return self._rows

    def scalar_one(self):
        return self._scalar


class _Conn:
    def __init__(self, *, rows=None):
        self.sql: list[str] = []
        self.params: list[dict[str, object]] = []
        self.rows = rows or []

    async def execute(self, statement, params=None):
        self.sql.append(str(statement))
        self.params.append(params or {})
        if "FROM core_reference.branches" in str(statement):
            return _MappingsResult(row={"branch_timezone": "Asia/Yekaterinburg", "clinic_timezone": "Europe/Moscow"})
        if "FROM core_reference.clinics" in str(statement):
            return _MappingsResult(row={"timezone": "Europe/Moscow"})
        if "FROM admin_views.today_schedule" in str(statement):
            return _MappingsResult(rows=self.rows)
        return _MappingsResult(rows=[])


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

    def connect(self):
        return _Ctx(self.conn)

    def begin(self):
        return _Ctx(self.conn)

    async def dispose(self):
        return None


def test_timezone_precedence_branch_then_clinic_then_default() -> None:
    conn = _Conn()
    tz = asyncio.run(_resolve_timezone_from_conn(conn, clinic_id="c1", branch_id="b1", app_default_timezone="UTC"))
    assert tz == "Asia/Yekaterinburg"


def test_today_schedule_returns_typed_rows_and_applies_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    row = {
        "clinic_id": "c1",
        "branch_id": "b1",
        "booking_id": "bk1",
        "patient_id": "p1",
        "doctor_id": "d1",
        "service_id": "s1",
        "local_service_date": date(2026, 4, 19),
        "local_service_time": "10:00",
        "scheduled_start_at_utc": datetime(2026, 4, 19, 7, 0, tzinfo=timezone.utc),
        "scheduled_end_at_utc": datetime(2026, 4, 19, 7, 30, tzinfo=timezone.utc),
        "booking_status": "pending_confirmation",
        "confirmation_state": "pending",
        "checkin_state": "not_arrived",
        "no_show_flag": False,
        "reschedule_requested_flag": False,
        "waitlist_linked_flag": False,
        "recommendation_linked_flag": False,
        "care_order_linked_flag": True,
        "patient_display_name": "Alice",
        "doctor_display_name": "Dr. Who",
        "service_label": "svc.cleaning",
        "branch_label": "Main",
        "compact_flags_summary": "needs_confirmation,care",
        "updated_at": datetime(2026, 4, 19, 6, 0, tzinfo=timezone.utc),
    }
    conn = _Conn(rows=[row])
    monkeypatch.setattr("app.application.admin.workdesk.create_engine", lambda _: _Engine(conn))

    service = AdminWorkdeskReadService(db_config=object())
    out = asyncio.run(
        service.get_today_schedule(
            clinic_id="c1",
            branch_id="b1",
            doctor_id="d1",
            local_day=date(2026, 4, 19),
            statuses=("pending_confirmation",),
        )
    )

    assert len(out) == 1
    assert isinstance(out[0], TodayScheduleRow)
    assert conn.params[-1]["branch_id"] == "b1"
    assert conn.params[-1]["doctor_id"] == "d1"
    assert conn.params[-1]["statuses"] == ["pending_confirmation"]


class _Store:
    def __init__(self):
        self.called: list[tuple[str, str]] = []

    async def refresh_booking(self, *, booking_id: str):
        self.called.append(("booking", booking_id))

    async def refresh_waitlist_entry(self, *, waitlist_entry_id: str):
        self.called.append(("waitlist", waitlist_entry_id))

    async def refresh_care_order(self, *, care_order_id: str):
        self.called.append(("care", care_order_id))


def test_admin_projector_routes_event_families(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()
    monkeypatch.setattr("app.projections.admin.workdesk_projector.AdminWorkdeskProjectionStore", lambda *args, **kwargs: store)

    projector = AdminWorkdeskProjector(db_config=object())

    booking_event = build_event(
        event_name="booking.confirmed",
        producer_context="tests",
        clinic_id="c1",
        entity_type="booking",
        entity_id="b1",
        payload={},
    )
    waitlist_event = build_event(
        event_name="waitlist.entry_created",
        producer_context="tests",
        clinic_id="c1",
        entity_type="waitlist_entry",
        entity_id="w1",
        payload={},
    )
    reminder_event = build_event(
        event_name="reminder.failed",
        producer_context="tests",
        clinic_id="c1",
        entity_type="reminder",
        entity_id="r1",
        payload={"booking_id": "b9"},
    )

    assert asyncio.run(projector.handle(booking_event, outbox_event_id=1)) is True
    assert asyncio.run(projector.handle(waitlist_event, outbox_event_id=2)) is True
    assert asyncio.run(projector.handle(reminder_event, outbox_event_id=3)) is True

    assert ("booking", "b1") in store.called
    assert ("waitlist", "w1") in store.called
    assert ("booking", "b9") in store.called
