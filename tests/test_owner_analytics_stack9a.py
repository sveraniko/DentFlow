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
    def __init__(self) -> None:
        self.last_doctor_days: int | None = None
        self.last_service_days: int | None = None
        self.last_branch_days: int | None = None
        self.last_care_days: int | None = None

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

    async def get_doctor_metrics(self, *, clinic_id: str, days: int = 7):
        self.last_doctor_days = days
        return SimpleNamespace(
            rows=[
                SimpleNamespace(
                    doctor_id="d1",
                    doctor_label="Dr. Alice",
                    bookings_created_count=10,
                    bookings_confirmed_count=8,
                    bookings_completed_count=7,
                    bookings_no_show_count=1,
                    bookings_reschedule_requested_count=1,
                    reminders_sent_count=6,
                    reminders_failed_count=1,
                    encounters_created_count=5,
                )
            ]
        )

    async def get_service_metrics(self, *, clinic_id: str, days: int = 7):
        self.last_service_days = days
        return SimpleNamespace(
            rows=[
                SimpleNamespace(
                    service_id="srv1",
                    service_label="Consultation",
                    bookings_created_count=12,
                    bookings_confirmed_count=9,
                    bookings_completed_count=8,
                    bookings_no_show_count=1,
                    bookings_reschedule_requested_count=2,
                )
            ]
        )

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

    async def get_branch_metrics(self, *, clinic_id: str, days: int = 7):
        self.last_branch_days = days
        return SimpleNamespace(
            rows=[
                SimpleNamespace(
                    branch_id="b1",
                    branch_label="Main branch",
                    bookings_created_count=12,
                    bookings_confirmed_count=10,
                    bookings_completed_count=9,
                    bookings_canceled_count=1,
                    bookings_no_show_count=1,
                    bookings_reschedule_requested_count=2,
                )
            ]
        )

    async def get_care_metrics(self, *, clinic_id: str, days: int = 7):
        self.last_care_days = days
        return SimpleNamespace(
            orders_created_count=9,
            orders_confirmed_count=7,
            orders_ready_for_pickup_count=5,
            orders_issued_count=4,
            orders_fulfilled_count=4,
            orders_canceled_count=1,
            orders_expired_count=1,
            active_orders_count=3,
            active_reservations_count=2,
        )


def _access(role: RoleCode) -> AccessResolver:
    repo = InMemoryAccessRepository()
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    repo.upsert_actor_identity(ActorIdentity(actor_id="a1", actor_type=ActorType.STAFF, display_name="Owner", status=ActorStatus.ACTIVE, locale="en"))
    repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id="t1", actor_id="a1", telegram_user_id=501))
    repo.upsert_staff_member(StaffMember(staff_id="s1", actor_id="a1", clinic_id="c1", full_name="Owner", display_name="Owner", staff_status=StaffStatus.ACTIVE))
    repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id="r1", staff_id="s1", clinic_id="c1", role_code=role, granted_at=now))
    return AccessResolver(repo)


def _handler_by_name(router, name: str):
    for handler in router.message.handlers:
        if handler.callback.__name__ == name:
            return handler.callback
    raise AssertionError(f"handler not found: {name}")


def test_owner_router_commands_owner_only_and_localized() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    analytics = _OwnerAnalyticsStub()
    router = make_router(i18n, _access(RoleCode.OWNER), analytics=analytics, default_locale="en")

    today = _Message("/owner_today")
    asyncio.run(_handler_by_name(router, "owner_today")(today))
    assert "Owner Today" in today.answers[-1]

    digest = _Message("/owner_digest")
    asyncio.run(_handler_by_name(router, "owner_digest")(digest))
    assert "Owner Digest" in digest.answers[-1]

    doctors = _Message("/owner_doctors")
    asyncio.run(_handler_by_name(router, "owner_doctors")(doctors))
    assert "Owner Doctor Metrics" in doctors.answers[-1]
    assert "Dr. Alice" in doctors.answers[-1]
    assert analytics.last_doctor_days == 7

    services = _Message("/owner_services 30")
    asyncio.run(_handler_by_name(router, "owner_services")(services))
    assert "Owner Service Metrics" in services.answers[-1]
    assert "Consultation" in services.answers[-1]
    assert analytics.last_service_days == 30

    branches = _Message("/owner_branches")
    asyncio.run(_handler_by_name(router, "owner_branches")(branches))
    assert "Owner Branch Metrics" in branches.answers[-1]
    assert "Main branch" in branches.answers[-1]
    assert "Window note:" in branches.answers[-1]
    assert analytics.last_branch_days == 7

    care = _Message("/owner_care")
    asyncio.run(_handler_by_name(router, "owner_care")(care))
    assert "Owner Care Metrics" in care.answers[-1]
    assert "Active reservations: 2" in care.answers[-1]
    assert analytics.last_care_days == 7
    assert "Revenue" not in care.answers[-1]
    assert "Payment" not in care.answers[-1]

    denied_router = make_router(i18n, _access(RoleCode.ADMIN), analytics=_OwnerAnalyticsStub(), default_locale="en")
    denied = _Message("/owner_services")
    asyncio.run(_handler_by_name(denied_router, "owner_services")(denied))
    assert any("Access denied" in x for x in denied.answers)
    denied_branches = _Message("/owner_branches")
    asyncio.run(_handler_by_name(denied_router, "owner_branches")(denied_branches))
    assert any("Access denied" in x for x in denied_branches.answers)
    denied_care = _Message("/owner_care")
    asyncio.run(_handler_by_name(denied_router, "owner_care")(denied_care))
    assert any("Access denied" in x for x in denied_care.answers)


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


def test_owner_metrics_invalid_window_and_empty_states() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")

    class _EmptyAnalytics(_OwnerAnalyticsStub):
        async def get_doctor_metrics(self, *, clinic_id: str, days: int = 7):
            self.last_doctor_days = days
            return SimpleNamespace(rows=[])

        async def get_service_metrics(self, *, clinic_id: str, days: int = 7):
            self.last_service_days = days
            return SimpleNamespace(rows=[])

        async def get_branch_metrics(self, *, clinic_id: str, days: int = 7):
            self.last_branch_days = days
            return SimpleNamespace(rows=[])

        async def get_care_metrics(self, *, clinic_id: str, days: int = 7):
            self.last_care_days = days
            return SimpleNamespace(
                orders_created_count=0,
                orders_confirmed_count=0,
                orders_ready_for_pickup_count=0,
                orders_issued_count=0,
                orders_fulfilled_count=0,
                orders_canceled_count=0,
                orders_expired_count=0,
                active_orders_count=0,
                active_reservations_count=0,
            )

    analytics = _EmptyAnalytics()
    router = make_router(i18n, _access(RoleCode.OWNER), analytics=analytics, default_locale="en")

    invalid = _Message("/owner_doctors 0")
    asyncio.run(_handler_by_name(router, "owner_doctors")(invalid))
    assert "Invalid window" in invalid.answers[0]
    assert "Usage: /owner_doctors" in invalid.answers[1]

    empty_doc = _Message("/owner_doctors 14")
    asyncio.run(_handler_by_name(router, "owner_doctors")(empty_doc))
    assert "No doctor metrics" in empty_doc.answers[-1]

    invalid_service = _Message("/owner_services q")
    asyncio.run(_handler_by_name(router, "owner_services")(invalid_service))
    assert "Invalid window" in invalid_service.answers[0]

    empty_service = _Message("/owner_services")
    asyncio.run(_handler_by_name(router, "owner_services")(empty_service))
    assert "No service metrics" in empty_service.answers[-1]

    invalid_branch = _Message("/owner_branches 120")
    asyncio.run(_handler_by_name(router, "owner_branches")(invalid_branch))
    assert "Invalid window" in invalid_branch.answers[0]
    assert "Usage: /owner_branches" in invalid_branch.answers[1]

    empty_branch = _Message("/owner_branches 30")
    asyncio.run(_handler_by_name(router, "owner_branches")(empty_branch))
    assert "No branch metrics" in empty_branch.answers[-1]

    invalid_care = _Message("/owner_care 100")
    asyncio.run(_handler_by_name(router, "owner_care")(invalid_care))
    assert "Invalid window" in invalid_care.answers[0]
    assert "Usage: /owner_care" in invalid_care.answers[1]

    empty_care = _Message("/owner_care")
    asyncio.run(_handler_by_name(router, "owner_care")(empty_care))
    assert "No care-commerce activity" in empty_care.answers[-1]


def test_owner_metric_labels_fallback_to_compact_ids() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")

    class _IdOnlyAnalytics(_OwnerAnalyticsStub):
        async def get_doctor_metrics(self, *, clinic_id: str, days: int = 7):
            return SimpleNamespace(
                rows=[
                    SimpleNamespace(
                        doctor_id="doctor-very-long-id-12345",
                        doctor_label=None,
                        bookings_created_count=1,
                        bookings_confirmed_count=1,
                        bookings_completed_count=1,
                        bookings_no_show_count=0,
                        bookings_reschedule_requested_count=0,
                        reminders_sent_count=1,
                        reminders_failed_count=0,
                        encounters_created_count=1,
                    )
                ]
            )

        async def get_service_metrics(self, *, clinic_id: str, days: int = 7):
            return SimpleNamespace(
                rows=[
                    SimpleNamespace(
                        service_id="service-very-long-id-99999",
                        service_label=None,
                        bookings_created_count=1,
                        bookings_confirmed_count=1,
                        bookings_completed_count=1,
                        bookings_no_show_count=0,
                        bookings_reschedule_requested_count=0,
                    )
                ]
            )

    router = make_router(i18n, _access(RoleCode.OWNER), analytics=_IdOnlyAnalytics(), default_locale="en")
    doctors = _Message("/owner_doctors")
    asyncio.run(_handler_by_name(router, "owner_doctors")(doctors))
    assert "doctor…2345" in doctors.answers[-1]

    services = _Message("/owner_services")
    asyncio.run(_handler_by_name(router, "owner_services")(services))
    assert "servic…9999" in services.answers[-1]


def test_owner_service_doctor_metrics_aggregate_and_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    service = OwnerAnalyticsService(db_config=object())

    async def _window(self, *, clinic_id: str, point: datetime):
        return (
            datetime(2026, 4, 17, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc),
            date(2026, 4, 17),
        )

    class _Res:
        def __init__(self, rows):
            self._rows = rows

        def mappings(self):
            return self

        def all(self):
            return self._rows

    captured_params = []

    class _Conn:
        async def execute(self, statement, params):
            sql = str(statement)
            captured_params.append((sql, params))
            if "daily_doctor_metrics" in sql:
                return _Res([
                {
                    "doctor_id": "d1",
                    "doctor_label": "Dr. Label",
                    "bookings_created_count": 11,
                        "bookings_confirmed_count": 9,
                        "bookings_completed_count": 8,
                        "bookings_no_show_count": 1,
                        "bookings_reschedule_requested_count": 1,
                        "reminders_sent_count": 7,
                        "reminders_failed_count": 1,
                        "encounters_created_count": 6,
                    }
                ])
            return _Res([
                {
                    "service_id": "srv1",
                    "service_label": "Service Label",
                    "bookings_created_count": 10,
                    "bookings_confirmed_count": 8,
                    "bookings_completed_count": 7,
                    "bookings_no_show_count": 1,
                    "bookings_reschedule_requested_count": 1,
                }
            ])

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

    doctors = asyncio.run(service.get_doctor_metrics(clinic_id="c1", days=7, limit=25))
    services = asyncio.run(service.get_service_metrics(clinic_id="c1", days=7, limit=25))

    assert doctors.limit == 10
    assert doctors.rows[0].doctor_id == "d1"
    assert doctors.rows[0].doctor_label == "Dr. Label"
    assert services.limit == 10
    assert services.rows[0].service_id == "srv1"
    assert services.rows[0].service_label == "Service Label"
    assert any("GROUP BY m.doctor_id" in sql for sql, _ in captured_params)
    assert any("GROUP BY m.service_id" in sql for sql, _ in captured_params)
    assert any("LEFT JOIN core_reference.doctors" in sql for sql, _ in captured_params)
    assert any("LEFT JOIN core_reference.services" in sql for sql, _ in captured_params)


def test_owner_branch_metrics_aggregate_and_bound_with_label_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    service = OwnerAnalyticsService(db_config=object())

    async def _window(self, *, clinic_id: str, point: datetime):
        return (
            datetime(2026, 4, 17, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc),
            date(2026, 4, 17),
        )

    class _Res:
        def __init__(self, rows):
            self._rows = rows

        def mappings(self):
            return self

        def all(self):
            return self._rows

    captured_sql: list[str] = []
    captured_params: list[dict[str, object]] = []

    class _Conn:
        async def execute(self, statement, params):
            captured_sql.append(str(statement))
            captured_params.append(params)
            return _Res([
                {
                    "branch_id": "b1",
                    "branch_label": "Branch A",
                    "bookings_created_count": 11,
                    "bookings_confirmed_count": 8,
                    "bookings_completed_count": 7,
                    "bookings_canceled_count": 2,
                    "bookings_no_show_count": 1,
                    "bookings_reschedule_requested_count": 1,
                },
                {
                    "branch_id": "b2",
                    "branch_label": None,
                    "bookings_created_count": 4,
                    "bookings_confirmed_count": 3,
                    "bookings_completed_count": 2,
                    "bookings_canceled_count": 1,
                    "bookings_no_show_count": 0,
                    "bookings_reschedule_requested_count": 1,
                },
            ])

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

    summary = asyncio.run(service.get_branch_metrics(clinic_id="c1", days=7, limit=25))

    assert summary.limit == 10
    assert len(summary.rows) == 2
    assert summary.rows[0].branch_label == "Branch A"
    assert summary.rows[1].branch_id == "b2"
    assert summary.rows[1].branch_label is None
    assert any("LEFT JOIN core_reference.branches" in sql for sql in captured_sql)
    assert any("GROUP BY b.branch_id, cb.display_name" in sql for sql in captured_sql)
    assert captured_params[0]["limit"] == 10


def test_owner_care_metrics_status_counts_and_active_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    service = OwnerAnalyticsService(db_config=object())

    async def _window(self, *, clinic_id: str, point: datetime):
        return (
            datetime(2026, 4, 17, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc),
            date(2026, 4, 17),
        )

    class _Res:
        def __init__(self, row=None, scalar=None):
            self._row = row
            self._scalar = scalar

        def mappings(self):
            return self

        def first(self):
            return self._row

        def scalar_one(self):
            return self._scalar

    captured_sql: list[str] = []

    class _Conn:
        async def execute(self, statement, params):
            sql = str(statement)
            captured_sql.append(sql)
            if "FROM care_commerce.care_orders co" in sql:
                return _Res(
                    row={
                        "orders_created_count": 9,
                        "orders_confirmed_count": 7,
                        "orders_ready_for_pickup_count": 5,
                        "orders_issued_count": 4,
                        "orders_fulfilled_count": 4,
                        "orders_canceled_count": 1,
                        "orders_expired_count": 2,
                        "active_orders_count": 6,
                    }
                )
            return _Res(scalar=3)

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

    summary = asyncio.run(service.get_care_metrics(clinic_id="c1", days=30))
    assert summary.days == 30
    assert summary.orders_created_count == 9
    assert summary.orders_confirmed_count == 7
    assert summary.orders_ready_for_pickup_count == 5
    assert summary.orders_issued_count == 4
    assert summary.orders_fulfilled_count == 4
    assert summary.orders_canceled_count == 1
    assert summary.orders_expired_count == 2
    assert summary.active_orders_count == 6
    assert summary.active_reservations_count == 3
    assert any("AT TIME ZONE (SELECT tz_name FROM tz)" in sql for sql in captured_sql)
    assert any("cr.status IN ('created', 'active')" in sql for sql in captured_sql)
