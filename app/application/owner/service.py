from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text

from app.infrastructure.db.engine import create_engine


@dataclass(slots=True)
class OwnerTodaySnapshot:
    clinic_id: str
    local_date: date
    bookings_today: int
    pending_confirmations_today: int
    completed_today: int
    canceled_today: int
    no_show_today: int
    charts_opened_today: int
    reminder_failures_today: int
    open_alerts_count: int


@dataclass(slots=True)
class OwnerDailyDigest:
    clinic_id: str
    metrics_date: date
    bookings_created_count: int
    bookings_confirmed_count: int
    bookings_completed_count: int
    bookings_canceled_count: int
    bookings_no_show_count: int
    reminders_failed_count: int
    open_alerts_count: int


@dataclass(slots=True)
class OwnerAlertRow:
    owner_alert_id: str
    clinic_id: str
    alert_type: str
    severity: str
    status: str
    entity_type: str | None
    entity_id: str | None
    alert_date: date
    summary_text: str
    details_json: dict | None
    created_at: datetime
    updated_at: datetime




@dataclass(slots=True)
class OwnerDoctorMetricRow:
    doctor_id: str
    bookings_created_count: int
    bookings_confirmed_count: int
    bookings_completed_count: int
    bookings_no_show_count: int
    bookings_reschedule_requested_count: int
    reminders_sent_count: int
    reminders_failed_count: int
    encounters_created_count: int


@dataclass(slots=True)
class OwnerDoctorMetricsSummary:
    clinic_id: str
    days: int
    limit: int
    rows: list[OwnerDoctorMetricRow]


@dataclass(slots=True)
class OwnerServiceMetricRow:
    service_id: str
    bookings_created_count: int
    bookings_confirmed_count: int
    bookings_completed_count: int
    bookings_no_show_count: int
    bookings_reschedule_requested_count: int


@dataclass(slots=True)
class OwnerServiceMetricsSummary:
    clinic_id: str
    days: int
    limit: int
    rows: list[OwnerServiceMetricRow]


@dataclass(slots=True)
class OwnerBranchMetricRow:
    branch_id: str
    branch_label: str | None
    bookings_created_count: int
    bookings_confirmed_count: int
    bookings_completed_count: int
    bookings_canceled_count: int
    bookings_no_show_count: int
    bookings_reschedule_requested_count: int


@dataclass(slots=True)
class OwnerBranchMetricsSummary:
    clinic_id: str
    days: int
    limit: int
    rows: list[OwnerBranchMetricRow]


@dataclass(slots=True)
class OwnerCareMetricsSummary:
    clinic_id: str
    days: int
    orders_created_count: int
    orders_confirmed_count: int
    orders_ready_for_pickup_count: int
    orders_issued_count: int
    orders_fulfilled_count: int
    orders_canceled_count: int
    orders_expired_count: int
    active_orders_count: int
    active_reservations_count: int


@dataclass(slots=True)
class OwnerAnalyticsService:
    db_config: object



    async def get_doctor_metrics(self, *, clinic_id: str, days: int = 7, limit: int = 10) -> OwnerDoctorMetricsSummary:
        _, _, local_date = await self._local_day_window(clinic_id=clinic_id, point=datetime.now(timezone.utc))
        window_start = local_date - timedelta(days=max(days, 1) - 1)
        bounded_limit = max(1, min(limit, 10))

        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT doctor_id,
                                   SUM(bookings_created_count) AS bookings_created_count,
                                   SUM(bookings_confirmed_count) AS bookings_confirmed_count,
                                   SUM(bookings_completed_count) AS bookings_completed_count,
                                   SUM(bookings_no_show_count) AS bookings_no_show_count,
                                   SUM(bookings_reschedule_requested_count) AS bookings_reschedule_requested_count,
                                   SUM(reminders_sent_count) AS reminders_sent_count,
                                   SUM(reminders_failed_count) AS reminders_failed_count,
                                   SUM(encounters_created_count) AS encounters_created_count
                            FROM owner_views.daily_doctor_metrics
                            WHERE clinic_id=:clinic_id
                              AND metrics_date>=:window_start
                              AND metrics_date<=:window_end
                            GROUP BY doctor_id
                            ORDER BY SUM(bookings_completed_count) DESC,
                                     SUM(bookings_created_count) DESC,
                                     SUM(bookings_confirmed_count) DESC,
                                     doctor_id ASC
                            LIMIT :limit
                            """
                        ),
                        {"clinic_id": clinic_id, "window_start": window_start, "window_end": local_date, "limit": bounded_limit},
                    )
                ).mappings().all()
        finally:
            await engine.dispose()

        return OwnerDoctorMetricsSummary(
            clinic_id=clinic_id,
            days=days,
            limit=bounded_limit,
            rows=[
                OwnerDoctorMetricRow(
                    doctor_id=str(row["doctor_id"]),
                    bookings_created_count=int(row["bookings_created_count"] or 0),
                    bookings_confirmed_count=int(row["bookings_confirmed_count"] or 0),
                    bookings_completed_count=int(row["bookings_completed_count"] or 0),
                    bookings_no_show_count=int(row["bookings_no_show_count"] or 0),
                    bookings_reschedule_requested_count=int(row["bookings_reschedule_requested_count"] or 0),
                    reminders_sent_count=int(row["reminders_sent_count"] or 0),
                    reminders_failed_count=int(row["reminders_failed_count"] or 0),
                    encounters_created_count=int(row["encounters_created_count"] or 0),
                )
                for row in rows
            ],
        )

    async def get_service_metrics(self, *, clinic_id: str, days: int = 7, limit: int = 10) -> OwnerServiceMetricsSummary:
        _, _, local_date = await self._local_day_window(clinic_id=clinic_id, point=datetime.now(timezone.utc))
        window_start = local_date - timedelta(days=max(days, 1) - 1)
        bounded_limit = max(1, min(limit, 10))

        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT service_id,
                                   SUM(bookings_created_count) AS bookings_created_count,
                                   SUM(bookings_confirmed_count) AS bookings_confirmed_count,
                                   SUM(bookings_completed_count) AS bookings_completed_count,
                                   SUM(bookings_no_show_count) AS bookings_no_show_count,
                                   SUM(bookings_reschedule_requested_count) AS bookings_reschedule_requested_count
                            FROM owner_views.daily_service_metrics
                            WHERE clinic_id=:clinic_id
                              AND metrics_date>=:window_start
                              AND metrics_date<=:window_end
                            GROUP BY service_id
                            ORDER BY SUM(bookings_completed_count) DESC,
                                     SUM(bookings_created_count) DESC,
                                     SUM(bookings_confirmed_count) DESC,
                                     service_id ASC
                            LIMIT :limit
                            """
                        ),
                        {"clinic_id": clinic_id, "window_start": window_start, "window_end": local_date, "limit": bounded_limit},
                    )
                ).mappings().all()
        finally:
            await engine.dispose()

        return OwnerServiceMetricsSummary(
            clinic_id=clinic_id,
            days=days,
            limit=bounded_limit,
            rows=[
                OwnerServiceMetricRow(
                    service_id=str(row["service_id"]),
                    bookings_created_count=int(row["bookings_created_count"] or 0),
                    bookings_confirmed_count=int(row["bookings_confirmed_count"] or 0),
                    bookings_completed_count=int(row["bookings_completed_count"] or 0),
                    bookings_no_show_count=int(row["bookings_no_show_count"] or 0),
                    bookings_reschedule_requested_count=int(row["bookings_reschedule_requested_count"] or 0),
                )
                for row in rows
            ],
        )

    async def get_branch_metrics(self, *, clinic_id: str, days: int = 7, limit: int = 10) -> OwnerBranchMetricsSummary:
        day_start_utc, day_end_utc, local_date = await self._local_day_window(clinic_id=clinic_id, point=datetime.now(timezone.utc))
        window_start = local_date - timedelta(days=max(days, 1) - 1)
        bounded_limit = max(1, min(limit, 10))

        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            WITH window AS (
                              SELECT
                                CAST(:window_start AS date) AS window_start,
                                CAST(:window_end AS date) AS window_end
                            )
                            SELECT
                              b.branch_id,
                              cb.display_name AS branch_label,
                              SUM(CASE WHEN DATE(
                                   b.created_at AT TIME ZONE COALESCE(
                                     NULLIF(cb.timezone, ''),
                                     NULLIF(cc.timezone, ''),
                                     'UTC'
                                   )
                                 ) BETWEEN (SELECT window_start FROM window) AND (SELECT window_end FROM window) THEN 1 ELSE 0 END) AS bookings_created_count,
                              SUM(CASE WHEN b.confirmed_at IS NOT NULL AND DATE(
                                   b.confirmed_at AT TIME ZONE COALESCE(
                                     NULLIF(cb.timezone, ''),
                                     NULLIF(cc.timezone, ''),
                                     'UTC'
                                   )
                                 ) BETWEEN (SELECT window_start FROM window) AND (SELECT window_end FROM window) THEN 1 ELSE 0 END) AS bookings_confirmed_count,
                              SUM(CASE WHEN b.completed_at IS NOT NULL AND DATE(
                                   b.completed_at AT TIME ZONE COALESCE(
                                     NULLIF(cb.timezone, ''),
                                     NULLIF(cc.timezone, ''),
                                     'UTC'
                                   )
                                 ) BETWEEN (SELECT window_start FROM window) AND (SELECT window_end FROM window) THEN 1 ELSE 0 END) AS bookings_completed_count,
                              SUM(CASE WHEN b.canceled_at IS NOT NULL AND DATE(
                                   b.canceled_at AT TIME ZONE COALESCE(
                                     NULLIF(cb.timezone, ''),
                                     NULLIF(cc.timezone, ''),
                                     'UTC'
                                   )
                                 ) BETWEEN (SELECT window_start FROM window) AND (SELECT window_end FROM window) THEN 1 ELSE 0 END) AS bookings_canceled_count,
                              SUM(CASE WHEN b.no_show_at IS NOT NULL AND DATE(
                                   b.no_show_at AT TIME ZONE COALESCE(
                                     NULLIF(cb.timezone, ''),
                                     NULLIF(cc.timezone, ''),
                                     'UTC'
                                   )
                                 ) BETWEEN (SELECT window_start FROM window) AND (SELECT window_end FROM window) THEN 1 ELSE 0 END) AS bookings_no_show_count,
                              SUM(CASE WHEN b.status='reschedule_requested' AND DATE(
                                   b.updated_at AT TIME ZONE COALESCE(
                                     NULLIF(cb.timezone, ''),
                                     NULLIF(cc.timezone, ''),
                                     'UTC'
                                   )
                                 ) BETWEEN (SELECT window_start FROM window) AND (SELECT window_end FROM window) THEN 1 ELSE 0 END) AS bookings_reschedule_requested_count
                            FROM booking.bookings b
                            JOIN core_reference.clinics cc ON cc.clinic_id=b.clinic_id
                            LEFT JOIN core_reference.branches cb ON cb.branch_id=b.branch_id
                            WHERE b.clinic_id=:clinic_id
                              AND b.scheduled_start_at >= :window_start_utc
                              AND b.scheduled_start_at < :window_end_utc
                            GROUP BY b.branch_id, cb.display_name
                            ORDER BY
                              SUM(CASE WHEN b.completed_at IS NOT NULL THEN 1 ELSE 0 END) DESC,
                              SUM(CASE WHEN b.created_at IS NOT NULL THEN 1 ELSE 0 END) DESC,
                              b.branch_id ASC
                            LIMIT :limit
                            """
                        ),
                        {
                            "clinic_id": clinic_id,
                            "window_start": window_start,
                            "window_end": local_date,
                            "window_start_utc": day_start_utc - timedelta(days=max(days, 1) - 1),
                            "window_end_utc": day_end_utc,
                            "limit": bounded_limit,
                        },
                    )
                ).mappings().all()
        finally:
            await engine.dispose()

        return OwnerBranchMetricsSummary(
            clinic_id=clinic_id,
            days=days,
            limit=bounded_limit,
            rows=[
                OwnerBranchMetricRow(
                    branch_id=str(row["branch_id"] or "-"),
                    branch_label=str(row["branch_label"]) if row["branch_label"] else None,
                    bookings_created_count=int(row["bookings_created_count"] or 0),
                    bookings_confirmed_count=int(row["bookings_confirmed_count"] or 0),
                    bookings_completed_count=int(row["bookings_completed_count"] or 0),
                    bookings_canceled_count=int(row["bookings_canceled_count"] or 0),
                    bookings_no_show_count=int(row["bookings_no_show_count"] or 0),
                    bookings_reschedule_requested_count=int(row["bookings_reschedule_requested_count"] or 0),
                )
                for row in rows
            ],
        )

    async def get_care_metrics(self, *, clinic_id: str, days: int = 7) -> OwnerCareMetricsSummary:
        _, _, local_date = await self._local_day_window(clinic_id=clinic_id, point=datetime.now(timezone.utc))
        window_start = local_date - timedelta(days=max(days, 1) - 1)

        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            """
                            WITH tz AS (
                              SELECT COALESCE(NULLIF(timezone, ''), 'UTC') AS tz_name
                              FROM core_reference.clinics
                              WHERE clinic_id=:clinic_id
                            ),
                            window AS (
                              SELECT CAST(:window_start AS date) AS window_start,
                                     CAST(:window_end AS date) AS window_end
                            )
                            SELECT
                              SUM(CASE WHEN DATE(co.created_at AT TIME ZONE (SELECT tz_name FROM tz))
                                        BETWEEN (SELECT window_start FROM window) AND (SELECT window_end FROM window)
                                       THEN 1 ELSE 0 END) AS orders_created_count,
                              SUM(CASE WHEN co.confirmed_at IS NOT NULL
                                            AND DATE(co.confirmed_at AT TIME ZONE (SELECT tz_name FROM tz))
                                        BETWEEN (SELECT window_start FROM window) AND (SELECT window_end FROM window)
                                       THEN 1 ELSE 0 END) AS orders_confirmed_count,
                              SUM(CASE WHEN co.ready_for_pickup_at IS NOT NULL
                                            AND DATE(co.ready_for_pickup_at AT TIME ZONE (SELECT tz_name FROM tz))
                                        BETWEEN (SELECT window_start FROM window) AND (SELECT window_end FROM window)
                                       THEN 1 ELSE 0 END) AS orders_ready_for_pickup_count,
                              SUM(CASE WHEN co.issued_at IS NOT NULL
                                            AND DATE(co.issued_at AT TIME ZONE (SELECT tz_name FROM tz))
                                        BETWEEN (SELECT window_start FROM window) AND (SELECT window_end FROM window)
                                       THEN 1 ELSE 0 END) AS orders_issued_count,
                              SUM(CASE WHEN co.fulfilled_at IS NOT NULL
                                            AND DATE(co.fulfilled_at AT TIME ZONE (SELECT tz_name FROM tz))
                                        BETWEEN (SELECT window_start FROM window) AND (SELECT window_end FROM window)
                                       THEN 1 ELSE 0 END) AS orders_fulfilled_count,
                              SUM(CASE WHEN co.canceled_at IS NOT NULL
                                            AND DATE(co.canceled_at AT TIME ZONE (SELECT tz_name FROM tz))
                                        BETWEEN (SELECT window_start FROM window) AND (SELECT window_end FROM window)
                                       THEN 1 ELSE 0 END) AS orders_canceled_count,
                              SUM(CASE WHEN co.expired_at IS NOT NULL
                                            AND DATE(co.expired_at AT TIME ZONE (SELECT tz_name FROM tz))
                                        BETWEEN (SELECT window_start FROM window) AND (SELECT window_end FROM window)
                                       THEN 1 ELSE 0 END) AS orders_expired_count,
                              SUM(CASE WHEN co.status IN ('created', 'awaiting_confirmation', 'confirmed', 'awaiting_payment', 'paid', 'ready_for_pickup', 'issued')
                                       THEN 1 ELSE 0 END) AS active_orders_count
                            FROM care_commerce.care_orders co
                            WHERE co.clinic_id=:clinic_id
                            """
                        ),
                        {"clinic_id": clinic_id, "window_start": window_start, "window_end": local_date},
                    )
                ).mappings().first()
                active_reservations_count = int(
                    (
                        await conn.execute(
                            text(
                                """
                                SELECT COUNT(*)
                                FROM care_commerce.care_reservations cr
                                JOIN care_commerce.care_orders co ON co.care_order_id=cr.care_order_id
                                WHERE co.clinic_id=:clinic_id
                                  AND cr.status IN ('created', 'active')
                                """
                            ),
                            {"clinic_id": clinic_id},
                        )
                    ).scalar_one()
                )
        finally:
            await engine.dispose()

        row = row or {}
        return OwnerCareMetricsSummary(
            clinic_id=clinic_id,
            days=days,
            orders_created_count=int(row.get("orders_created_count") or 0),
            orders_confirmed_count=int(row.get("orders_confirmed_count") or 0),
            orders_ready_for_pickup_count=int(row.get("orders_ready_for_pickup_count") or 0),
            orders_issued_count=int(row.get("orders_issued_count") or 0),
            orders_fulfilled_count=int(row.get("orders_fulfilled_count") or 0),
            orders_canceled_count=int(row.get("orders_canceled_count") or 0),
            orders_expired_count=int(row.get("orders_expired_count") or 0),
            active_orders_count=int(row.get("active_orders_count") or 0),
            active_reservations_count=active_reservations_count,
        )

    async def get_today_snapshot(self, *, clinic_id: str, now: datetime | None = None) -> OwnerTodaySnapshot:
        point = now or datetime.now(timezone.utc)
        day_start_utc, day_end_utc, local_date = await self._local_day_window(clinic_id=clinic_id, point=point)

        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                bookings = int(
                    (
                        await conn.execute(
                            text(
                                """
                                SELECT COUNT(*) AS c
                                FROM booking.bookings
                                WHERE clinic_id=:clinic_id
                                  AND scheduled_start_at >= :day_start
                                  AND scheduled_start_at < :day_end
                                """
                            ),
                            {"clinic_id": clinic_id, "day_start": day_start_utc, "day_end": day_end_utc},
                        )
                    ).scalar_one()
                )
                pending = int(
                    (
                        await conn.execute(
                            text(
                                """
                                SELECT COUNT(*) AS c
                                FROM booking.bookings
                                WHERE clinic_id=:clinic_id
                                  AND status='pending_confirmation'
                                  AND scheduled_start_at >= :day_start
                                  AND scheduled_start_at < :day_end
                                """
                            ),
                            {"clinic_id": clinic_id, "day_start": day_start_utc, "day_end": day_end_utc},
                        )
                    ).scalar_one()
                )
                completed = int((await conn.execute(text("SELECT COUNT(*) FROM booking.bookings WHERE clinic_id=:clinic_id AND status='completed' AND completed_at >= :day_start AND completed_at < :day_end"), {"clinic_id": clinic_id, "day_start": day_start_utc, "day_end": day_end_utc})).scalar_one())
                canceled = int((await conn.execute(text("SELECT COUNT(*) FROM booking.bookings WHERE clinic_id=:clinic_id AND status='canceled' AND canceled_at >= :day_start AND canceled_at < :day_end"), {"clinic_id": clinic_id, "day_start": day_start_utc, "day_end": day_end_utc})).scalar_one())
                no_show = int((await conn.execute(text("SELECT COUNT(*) FROM booking.bookings WHERE clinic_id=:clinic_id AND status='no_show' AND no_show_at >= :day_start AND no_show_at < :day_end"), {"clinic_id": clinic_id, "day_start": day_start_utc, "day_end": day_end_utc})).scalar_one())
                charts = int((await conn.execute(text("SELECT COUNT(*) FROM analytics_raw.event_ledger WHERE clinic_id=:clinic_id AND event_name='chart.opened' AND occurred_at >= :day_start AND occurred_at < :day_end"), {"clinic_id": clinic_id, "day_start": day_start_utc, "day_end": day_end_utc})).scalar_one())
                reminder_failures = int((await conn.execute(text("SELECT COUNT(*) FROM communication.reminder_jobs WHERE clinic_id=:clinic_id AND status='failed' AND last_failed_at >= :day_start AND last_failed_at < :day_end"), {"clinic_id": clinic_id, "day_start": day_start_utc, "day_end": day_end_utc})).scalar_one())
                open_alerts = int((await conn.execute(text("SELECT COUNT(*) FROM owner_views.owner_alerts WHERE clinic_id=:clinic_id AND status='open'"), {"clinic_id": clinic_id})).scalar_one())
        finally:
            await engine.dispose()

        return OwnerTodaySnapshot(
            clinic_id=clinic_id,
            local_date=local_date,
            bookings_today=bookings,
            pending_confirmations_today=pending,
            completed_today=completed,
            canceled_today=canceled,
            no_show_today=no_show,
            charts_opened_today=charts,
            reminder_failures_today=reminder_failures,
            open_alerts_count=open_alerts,
        )

    async def get_latest_digest(self, *, clinic_id: str, now: datetime | None = None) -> OwnerDailyDigest | None:
        point = now or datetime.now(timezone.utc)
        _, _, local_date = await self._local_day_window(clinic_id=clinic_id, point=point)
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            """
                            SELECT metrics_date, bookings_created_count, bookings_confirmed_count,
                                   bookings_completed_count, bookings_canceled_count, bookings_no_show_count,
                                   reminders_failed_count
                            FROM owner_views.daily_clinic_metrics
                            WHERE clinic_id=:clinic_id AND metrics_date<=:target
                            ORDER BY metrics_date DESC
                            LIMIT 1
                            """
                        ),
                        {"clinic_id": clinic_id, "target": local_date},
                    )
                ).mappings().first()
                if row is None:
                    return None
                open_alerts = int((await conn.execute(text("SELECT COUNT(*) FROM owner_views.owner_alerts WHERE clinic_id=:clinic_id AND status='open'"), {"clinic_id": clinic_id})).scalar_one())
        finally:
            await engine.dispose()

        return OwnerDailyDigest(
            clinic_id=clinic_id,
            metrics_date=row["metrics_date"],
            bookings_created_count=int(row["bookings_created_count"]),
            bookings_confirmed_count=int(row["bookings_confirmed_count"]),
            bookings_completed_count=int(row["bookings_completed_count"]),
            bookings_canceled_count=int(row["bookings_canceled_count"]),
            bookings_no_show_count=int(row["bookings_no_show_count"]),
            reminders_failed_count=int(row["reminders_failed_count"]),
            open_alerts_count=open_alerts,
        )

    async def list_open_alerts(self, *, clinic_id: str, limit: int = 10) -> list[OwnerAlertRow]:
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT owner_alert_id, clinic_id, alert_type, severity, status, entity_type, entity_id,
                                   alert_date, summary_text, details_json, created_at, updated_at
                            FROM owner_views.owner_alerts
                            WHERE clinic_id=:clinic_id AND status='open'
                            ORDER BY alert_date DESC, created_at DESC
                            LIMIT :limit
                            """
                        ),
                        {"clinic_id": clinic_id, "limit": limit},
                    )
                ).mappings().all()
        finally:
            await engine.dispose()
        return [OwnerAlertRow(**dict(row)) for row in rows]

    async def get_alert(self, *, clinic_id: str, owner_alert_id: str) -> OwnerAlertRow | None:
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            """
                            SELECT owner_alert_id, clinic_id, alert_type, severity, status, entity_type, entity_id,
                                   alert_date, summary_text, details_json, created_at, updated_at
                            FROM owner_views.owner_alerts
                            WHERE clinic_id=:clinic_id AND owner_alert_id=:owner_alert_id
                            """
                        ),
                        {"clinic_id": clinic_id, "owner_alert_id": owner_alert_id},
                    )
                ).mappings().first()
        finally:
            await engine.dispose()
        return OwnerAlertRow(**dict(row)) if row else None

    async def _local_day_window(self, *, clinic_id: str, point: datetime) -> tuple[datetime, datetime, date]:
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                row = (await conn.execute(text("SELECT timezone FROM core_reference.clinics WHERE clinic_id=:clinic_id"), {"clinic_id": clinic_id})).mappings().first()
        finally:
            await engine.dispose()

        tz_name = str(row["timezone"]) if row and row.get("timezone") else "UTC"
        try:
            zone = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("UTC")
        local_point = point.astimezone(zone)
        local_start = datetime(local_point.year, local_point.month, local_point.day, tzinfo=zone)
        local_end = local_start + timedelta(days=1)
        return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc), local_start.date()
