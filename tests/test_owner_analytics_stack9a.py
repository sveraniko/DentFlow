from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.application.owner.service import OwnerAnalyticsService
from app.common.i18n import I18nService
from app.domain.access_identity.models import ActorIdentity, ActorStatus, ActorType, ClinicRoleAssignment, RoleCode, StaffMember, StaffStatus, TelegramBinding
from app.domain.events import build_event
from app.interfaces.bots.owner.router import make_router
from app.projections.owner.daily_metrics_projector import OwnerDailyMetricsProjector, _refresh_alerts, _upsert_open_alert


class _Message:
    def __init__(self, text: str, *, user_id: int = 501) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _OwnerAnalyticsStub:
    async def get_today_snapshot(self, *, clinic_id: str):
        return SimpleNamespace(
            local_date=date(2026, 4, 17),
            bookings_today=12,
            pending_confirmations_today=4,
            completed_today=6,
            canceled_today=1,
            no_show_today=1,
            charts_opened_today=3,
            reminder_failures_today=2,
            open_alerts_count=2,
        )

    async def get_latest_digest(self, *, clinic_id: str):
        return SimpleNamespace(
            metrics_date=date(2026, 4, 16),
            bookings_created_count=14,
            bookings_confirmed_count=11,
            bookings_completed_count=9,
            bookings_canceled_count=2,
            bookings_no_show_count=1,
            reminders_failed_count=2,
            open_alerts_count=2,
        )

    async def list_open_alerts(self, *, clinic_id: str, limit: int = 10):
        return [
            SimpleNamespace(
                owner_alert_id="o1",
                alert_type="no_show_spike",
                severity="high",
                alert_date=date(2026, 4, 17),
                summary_text="No-show spike",
            )
        ]

    async def get_alert(self, *, clinic_id: str, owner_alert_id: str):
        if owner_alert_id != "o1":
            return None
        return SimpleNamespace(
            owner_alert_id="o1",
            alert_type="no_show_spike",
            severity="high",
            status="open",
            alert_date=date(2026, 4, 17),
            summary_text="No-show spike",
            details_json={"no_show": 4},
        )


def _access(role: RoleCode) -> AccessResolver:
    repo = InMemoryAccessRepository()
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    repo.upsert_actor_identity(ActorIdentity(actor_id="a1", actor_type=ActorType.STAFF, display_name="Owner", status=ActorStatus.ACTIVE, locale="en"))
    repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id="t1", actor_id="a1", telegram_user_id=501))
    repo.upsert_staff_member(StaffMember(staff_id="s1", actor_id="a1", clinic_id="c1", full_name="Owner", display_name="Owner", staff_status=StaffStatus.ACTIVE))
    repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id="r1", staff_id="s1", clinic_id="c1", role_code=role, granted_at=now))
    return AccessResolver(repo)


def test_owner_router_commands_owner_only_and_localized() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    router = make_router(i18n, _access(RoleCode.OWNER), analytics=_OwnerAnalyticsStub(), default_locale="en")
    handlers = [h.callback for h in router.message.handlers]

    today = _Message("/owner_today")
    asyncio.run(handlers[1](today))
    assert "Owner Today" in today.answers[-1]

    digest = _Message("/owner_digest")
    asyncio.run(handlers[2](digest))
    assert "Owner Digest" in digest.answers[-1]

    denied_router = make_router(i18n, _access(RoleCode.ADMIN), analytics=_OwnerAnalyticsStub(), default_locale="en")
    denied_handlers = [h.callback for h in denied_router.message.handlers]
    denied = _Message("/owner_today")
    asyncio.run(denied_handlers[1](denied))
    assert any("Access denied" in x for x in denied.answers)


class _FakeConn:
    def __init__(self):
        self.inserts = 0
        self.updates = 0
        self.exists = False

    async def execute(self, statement, params):
        sql = str(statement)
        if "SELECT owner_alert_id" in sql:
            return _Result(first=("o1",) if self.exists else None)
        if "INSERT INTO owner_views.owner_alerts" in sql:
            self.inserts += 1
            self.exists = True
            return _Result()
        if "UPDATE owner_views.owner_alerts" in sql:
            self.updates += 1
            return _Result()
        return _Result()


class _Result:
    def __init__(self, first=None):
        self._first = first

    def first(self):
        return self._first


def test_owner_alert_upsert_dedupes_open_alerts() -> None:
    conn = _FakeConn()
    asyncio.run(
        _upsert_open_alert(
            conn,
            clinic_id="c1",
            metrics_date=date(2026, 4, 17),
            alert_type="no_show_spike",
            severity="high",
            summary_text="No-show",
            details_json='{"no_show": 4}',
        )
    )
    asyncio.run(
        _upsert_open_alert(
            conn,
            clinic_id="c1",
            metrics_date=date(2026, 4, 17),
            alert_type="no_show_spike",
            severity="high",
            summary_text="No-show updated",
            details_json='{"no_show": 5}',
        )
    )
    assert conn.inserts == 1
    assert conn.updates == 1


def test_owner_projector_maps_booking_event_to_daily_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    projector = OwnerDailyMetricsProjector(db_config=object())
    calls: list[tuple[str, str]] = []

    async def _resolve(*args, **kwargs):
        return date(2026, 4, 17)

    async def _dims(*args, **kwargs):
        return {"doctor_id": "d1", "service_id": "s1"}

    async def _inc_clinic(conn, *, clinic_id, metrics_date, column):
        calls.append(("clinic", column))

    async def _inc_doctor(conn, *, clinic_id, metrics_date, doctor_id, column):
        calls.append(("doctor", column))

    async def _inc_service(conn, *, clinic_id, metrics_date, service_id, column):
        calls.append(("service", column))

    async def _refresh(conn, *, clinic_id, metrics_date):
        calls.append(("alerts", "refresh"))

    class _Conn:
        pass

    class _Engine:
        def begin(self):
            class _Ctx:
                async def __aenter__(self_non):
                    return _Conn()

                async def __aexit__(self_non, exc_type, exc, tb):
                    return False

            return _Ctx()

        async def dispose(self):
            return None

    monkeypatch.setattr("app.projections.owner.daily_metrics_projector.create_engine", lambda _: _Engine())
    monkeypatch.setattr("app.projections.owner.daily_metrics_projector._resolve_local_date", _resolve)
    monkeypatch.setattr("app.projections.owner.daily_metrics_projector._fetch_booking_dims", _dims)
    monkeypatch.setattr("app.projections.owner.daily_metrics_projector._inc_clinic", _inc_clinic)
    monkeypatch.setattr("app.projections.owner.daily_metrics_projector._inc_doctor", _inc_doctor)
    monkeypatch.setattr("app.projections.owner.daily_metrics_projector._inc_service", _inc_service)
    monkeypatch.setattr("app.projections.owner.daily_metrics_projector._refresh_alerts", _refresh)

    event = build_event(
        event_name="booking.confirmed",
        producer_context="tests",
        clinic_id="c1",
        entity_type="booking",
        entity_id="b1",
        payload={},
    )
    asyncio.run(projector.handle(event, outbox_event_id=1))
    assert ("clinic", "bookings_confirmed_count") in calls
    assert ("doctor", "bookings_confirmed_count") in calls
    assert ("service", "bookings_confirmed_count") in calls
    assert ("alerts", "refresh") in calls


def test_owner_snapshot_uses_local_day_window(monkeypatch: pytest.MonkeyPatch) -> None:
    service = OwnerAnalyticsService(db_config=object())

    async def _window(self, *, clinic_id: str, point: datetime):
        return (
            datetime(2026, 4, 17, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc),
            date(2026, 4, 17),
        )

    class _ScalarResult:
        def __init__(self, value):
            self.value = value

        def scalar_one(self):
            return self.value

    class _Conn:
        async def execute(self, statement, params):
            sql = str(statement)
            if "day_start" in params:
                assert params["day_start"] == datetime(2026, 4, 17, 0, 0, tzinfo=timezone.utc)
                assert params["day_end"] == datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
            if "status='pending_confirmation'" in sql:
                return _ScalarResult(2)
            if "status='completed'" in sql:
                return _ScalarResult(1)
            if "status='canceled'" in sql:
                return _ScalarResult(0)
            if "status='no_show'" in sql:
                return _ScalarResult(1)
            if "event_name='chart.opened'" in sql:
                return _ScalarResult(3)
            if "status='failed'" in sql:
                return _ScalarResult(1)
            if "owner_views.owner_alerts" in sql:
                return _ScalarResult(4)
            return _ScalarResult(10)

    class _Engine:
        def connect(self):
            class _Ctx:
                async def __aenter__(self_non):
                    return _Conn()

                async def __aexit__(self_non, exc_type, exc, tb):
                    return False

            return _Ctx()

        async def dispose(self):
            return None

    monkeypatch.setattr(OwnerAnalyticsService, "_local_day_window", _window)
    monkeypatch.setattr("app.application.owner.service.create_engine", lambda _: _Engine())

    snap = asyncio.run(service.get_today_snapshot(clinic_id="c1", now=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)))
    assert snap.local_date == date(2026, 4, 17)
    assert snap.pending_confirmations_today == 2


def test_open_confirmation_backlog_uses_local_timezone_semantics() -> None:
    captured_sql: list[str] = []

    class _Res:
        def __init__(self, first=None, scalar=0):
            self._first = first
            self._scalar = scalar

        def mappings(self):
            return self

        def first(self):
            return self._first

        def scalar_one(self):
            return self._scalar

    class _Conn:
        async def execute(self, statement, params):
            sql = str(statement)
            captured_sql.append(sql)
            if "FROM owner_views.daily_clinic_metrics" in sql:
                return _Res(first={"bookings_created_count": 0, "bookings_confirmed_count": 0, "bookings_no_show_count": 0, "reminders_failed_count": 0})
            if "FROM booking.bookings" in sql:
                return _Res(scalar=0)
            return _Res()

    asyncio.run(_refresh_alerts(_Conn(), clinic_id="c1", metrics_date=date(2026, 4, 17)))
    backlog_sql = next(s for s in captured_sql if "FROM booking.bookings" in s)
    assert "AT TIME ZONE COALESCE" in backlog_sql
    assert "AT TIME ZONE 'UTC'" not in backlog_sql
