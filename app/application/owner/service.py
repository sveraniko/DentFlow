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
    doctor_label: str | None
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
    service_label: str | None
    service_title_key: str | None
    service_code: str | None
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
class OwnerStaffAccessRow:
    actor_id: str
    display_name: str | None
    role_code: str | None
    role_label: str | None
    staff_kind: str
    doctor_id: str | None
    telegram_binding_state: str
    active_state: str
    branch_id: str | None
    branch_label: str | None
    created_at: datetime | None
    last_seen_at: datetime | None


@dataclass(slots=True)
class OwnerStaffAccessOverview:
    clinic_id: str
    limit: int
    rows: list[OwnerStaffAccessRow]


@dataclass(slots=True)
class OwnerPatientBaseRecentRow:
    patient_id: str
    display_name: str | None
    created_at: datetime | None


@dataclass(slots=True)
class OwnerPatientBaseSnapshot:
    clinic_id: str
    days: int
    limit: int
    total_patients_count: int | None
    new_patients_in_window_count: int | None
    upcoming_live_booking_patients_count: int | None
    completed_booking_patients_in_window_count: int | None
    active_care_patients_count: int | None
    telegram_bound_patients_count: int | None
    recent_new_patients: list[OwnerPatientBaseRecentRow]


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
                            SELECT m.doctor_id,
                                   MAX(COALESCE(NULLIF(dp.display_name, ''), NULLIF(dp.full_name, ''))) AS doctor_label,
                                   SUM(bookings_created_count) AS bookings_created_count,
                                   SUM(bookings_confirmed_count) AS bookings_confirmed_count,
                                   SUM(bookings_completed_count) AS bookings_completed_count,
                                   SUM(bookings_no_show_count) AS bookings_no_show_count,
                                   SUM(bookings_reschedule_requested_count) AS bookings_reschedule_requested_count,
                                   SUM(reminders_sent_count) AS reminders_sent_count,
                                   SUM(reminders_failed_count) AS reminders_failed_count,
                                   SUM(encounters_created_count) AS encounters_created_count
                            FROM owner_views.daily_doctor_metrics m
                            LEFT JOIN core_reference.doctors dp
                              ON dp.doctor_id=m.doctor_id
                             AND dp.clinic_id=m.clinic_id
                            WHERE m.clinic_id=:clinic_id
                              AND m.metrics_date>=:window_start
                              AND m.metrics_date<=:window_end
                            GROUP BY m.doctor_id
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
                    doctor_label=str(row["doctor_label"]) if row["doctor_label"] else None,
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
                            SELECT m.service_id,
                                   MAX(NULLIF(cs.title_key, '')) AS service_title_key,
                                   MAX(NULLIF(cs.code, '')) AS service_code,
                                   SUM(bookings_created_count) AS bookings_created_count,
                                   SUM(bookings_confirmed_count) AS bookings_confirmed_count,
                                   SUM(bookings_completed_count) AS bookings_completed_count,
                                   SUM(bookings_no_show_count) AS bookings_no_show_count,
                                   SUM(bookings_reschedule_requested_count) AS bookings_reschedule_requested_count
                            FROM owner_views.daily_service_metrics m
                            LEFT JOIN core_reference.services cs
                              ON cs.service_id=m.service_id
                             AND cs.clinic_id=m.clinic_id
                            WHERE m.clinic_id=:clinic_id
                              AND m.metrics_date>=:window_start
                              AND m.metrics_date<=:window_end
                            GROUP BY m.service_id
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
                    service_title_key=str(row["service_title_key"]) if row["service_title_key"] else None,
                    service_code=str(row["service_code"]) if row["service_code"] else None,
                    service_label=(
                        str(row["service_code"])
                        if row.get("service_code")
                        else (str(row["service_title_key"]) if row.get("service_title_key") else None)
                    ),
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

    async def get_staff_access_overview(self, *, clinic_id: str, limit: int = 50) -> OwnerStaffAccessOverview:
        bounded_limit = max(1, min(limit, 100))
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            WITH staff_base AS (
                              SELECT sm.staff_id,
                                     sm.actor_id,
                                     sm.display_name AS staff_display_name,
                                     sm.full_name,
                                     sm.staff_status,
                                     sm.primary_branch_id,
                                     sm.created_at AS staff_created_at,
                                     ai.display_name AS actor_display_name,
                                     ai.status AS actor_status,
                                     ai.created_at AS actor_created_at
                              FROM access_identity.staff_members sm
                              LEFT JOIN access_identity.actor_identities ai ON ai.actor_id=sm.actor_id
                              WHERE sm.clinic_id=:clinic_id
                            )
                            SELECT
                              sb.actor_id,
                              COALESCE(NULLIF(sb.staff_display_name, ''), NULLIF(sb.full_name, ''), NULLIF(sb.actor_display_name, '')) AS display_name,
                              cra.role_code,
                              CASE cra.role_code
                                WHEN 'owner' THEN 'Owner'
                                WHEN 'admin' THEN 'Admin'
                                WHEN 'doctor' THEN 'Doctor'
                                ELSE cra.role_code
                              END AS role_label,
                              CASE
                                WHEN cra.role_code='doctor' OR dp.doctor_id IS NOT NULL THEN 'doctor'
                                WHEN cra.role_code='admin' THEN 'admin'
                                WHEN cra.role_code='owner' THEN 'owner'
                                ELSE 'unknown'
                              END AS staff_kind,
                              dp.doctor_id,
                              CASE
                                WHEN tb.actor_id IS NULL THEN 'no'
                                WHEN tb.is_active THEN 'yes'
                                ELSE 'unknown'
                              END AS telegram_binding_state,
                              CASE
                                WHEN sb.staff_status='active' AND sb.actor_status='active' AND COALESCE(cra.is_active, TRUE) THEN 'active'
                                WHEN sb.staff_status IS NULL AND sb.actor_status IS NULL AND cra.role_code IS NULL THEN 'unknown'
                                ELSE 'inactive'
                              END AS active_state,
                              COALESCE(cra.branch_id, sb.primary_branch_id) AS branch_id,
                              cb.display_name AS branch_label,
                              GREATEST(sb.staff_created_at, sb.actor_created_at) AS created_at,
                              tb.last_seen_at
                            FROM staff_base sb
                            LEFT JOIN access_identity.clinic_role_assignments cra
                              ON cra.staff_id=sb.staff_id
                             AND cra.clinic_id=:clinic_id
                             AND cra.is_active
                             AND cra.revoked_at IS NULL
                            LEFT JOIN access_identity.doctor_profiles dp
                              ON dp.staff_id=sb.staff_id
                             AND dp.clinic_id=:clinic_id
                             AND (dp.active_for_clinical_work OR dp.active_for_booking)
                            LEFT JOIN LATERAL (
                              SELECT actor_id, is_active, last_seen_at
                              FROM access_identity.telegram_bindings tbx
                              WHERE tbx.actor_id=sb.actor_id
                                AND tbx.is_primary
                              ORDER BY tbx.created_at DESC
                              LIMIT 1
                            ) tb ON TRUE
                            LEFT JOIN core_reference.branches cb
                              ON cb.branch_id=COALESCE(cra.branch_id, sb.primary_branch_id)
                            ORDER BY
                              CASE WHEN cra.role_code='owner' THEN 0 WHEN cra.role_code='admin' THEN 1 WHEN cra.role_code='doctor' THEN 2 ELSE 3 END,
                              COALESCE(NULLIF(sb.staff_display_name, ''), NULLIF(sb.full_name, ''), sb.actor_id) ASC,
                              sb.actor_id ASC
                            LIMIT :limit
                            """
                        ),
                        {"clinic_id": clinic_id, "limit": bounded_limit},
                    )
                ).mappings().all()
        finally:
            await engine.dispose()

        return OwnerStaffAccessOverview(
            clinic_id=clinic_id,
            limit=bounded_limit,
            rows=[
                OwnerStaffAccessRow(
                    actor_id=str(row["actor_id"]),
                    display_name=str(row["display_name"]) if row["display_name"] else None,
                    role_code=str(row["role_code"]) if row["role_code"] else None,
                    role_label=str(row["role_label"]) if row["role_label"] else None,
                    staff_kind=str(row["staff_kind"] or "unknown"),
                    doctor_id=str(row["doctor_id"]) if row["doctor_id"] else None,
                    telegram_binding_state=str(row["telegram_binding_state"] or "unknown"),
                    active_state=str(row["active_state"] or "unknown"),
                    branch_id=str(row["branch_id"]) if row["branch_id"] else None,
                    branch_label=str(row["branch_label"]) if row["branch_label"] else None,
                    created_at=row["created_at"],
                    last_seen_at=row["last_seen_at"],
                )
                for row in rows
            ],
        )

    async def get_patient_base_snapshot(self, *, clinic_id: str, days: int = 30, limit: int = 10) -> OwnerPatientBaseSnapshot:
        point = datetime.now(timezone.utc)
        day_start_utc, _, local_date = await self._local_day_window(clinic_id=clinic_id, point=point)
        window_days = max(days, 1)
        window_start = local_date - timedelta(days=window_days - 1)
        bounded_limit = max(1, min(limit, 10))

        async def _safe_scalar(conn, sql: str, params: dict[str, object]) -> int | None:
            try:
                value = (await conn.execute(text(sql), params)).scalar_one()
            except Exception:
                return None
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                return None

        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                total_patients_count = await _safe_scalar(
                    conn,
                    """
                    SELECT COUNT(*)
                    FROM core_patient.patients
                    WHERE clinic_id=:clinic_id
                    """,
                    {"clinic_id": clinic_id},
                )
                new_patients_in_window_count = await _safe_scalar(
                    conn,
                    """
                    WITH tz AS (
                      SELECT COALESCE(NULLIF(timezone, ''), 'UTC') AS tz_name
                      FROM core_reference.clinics
                      WHERE clinic_id=:clinic_id
                    )
                    SELECT COUNT(*)
                    FROM core_patient.patients p
                    WHERE p.clinic_id=:clinic_id
                      AND DATE(p.created_at AT TIME ZONE (SELECT tz_name FROM tz))
                          BETWEEN :window_start AND :window_end
                    """,
                    {"clinic_id": clinic_id, "window_start": window_start, "window_end": local_date},
                )
                upcoming_live_booking_patients_count = await _safe_scalar(
                    conn,
                    """
                    SELECT COUNT(DISTINCT b.resolved_patient_id)
                    FROM booking.bookings b
                    WHERE b.clinic_id=:clinic_id
                      AND b.resolved_patient_id IS NOT NULL
                      AND (
                        b.status='in_service'
                        OR (
                          b.scheduled_start_at>=:day_start
                          AND b.status IN ('pending_confirmation', 'confirmed', 'reschedule_requested')
                        )
                      )
                    """,
                    {"clinic_id": clinic_id, "day_start": day_start_utc},
                )
                completed_booking_patients_in_window_count = await _safe_scalar(
                    conn,
                    """
                    WITH tz AS (
                      SELECT COALESCE(NULLIF(timezone, ''), 'UTC') AS tz_name
                      FROM core_reference.clinics
                      WHERE clinic_id=:clinic_id
                    )
                    SELECT COUNT(DISTINCT b.resolved_patient_id)
                    FROM booking.bookings b
                    WHERE b.clinic_id=:clinic_id
                      AND b.resolved_patient_id IS NOT NULL
                      AND b.completed_at IS NOT NULL
                      AND DATE(b.completed_at AT TIME ZONE (SELECT tz_name FROM tz))
                          BETWEEN :window_start AND :window_end
                    """,
                    {"clinic_id": clinic_id, "window_start": window_start, "window_end": local_date},
                )
                active_care_patients_count = await _safe_scalar(
                    conn,
                    """
                    WITH active_patients AS (
                      SELECT co.patient_id
                      FROM care_commerce.care_orders co
                      WHERE co.clinic_id=:clinic_id
                        AND co.patient_id IS NOT NULL
                        AND co.status IN ('created', 'awaiting_confirmation', 'confirmed', 'awaiting_payment', 'paid', 'ready_for_pickup', 'issued')
                      UNION
                      SELECT co.patient_id
                      FROM care_commerce.care_reservations cr
                      JOIN care_commerce.care_orders co ON co.care_order_id=cr.care_order_id
                      WHERE co.clinic_id=:clinic_id
                        AND co.patient_id IS NOT NULL
                        AND cr.status IN ('created', 'active')
                    )
                    SELECT COUNT(DISTINCT patient_id) FROM active_patients
                    """,
                    {"clinic_id": clinic_id},
                )
                telegram_bound_patients_count = await _safe_scalar(
                    conn,
                    """
                    SELECT COUNT(DISTINCT pei.patient_id)
                    FROM core_patient.patient_external_ids pei
                    JOIN core_patient.patients p ON p.patient_id=pei.patient_id
                    WHERE p.clinic_id=:clinic_id
                      AND pei.external_system='telegram'
                    """,
                    {"clinic_id": clinic_id},
                )
                try:
                    recent_rows = (
                        await conn.execute(
                            text(
                                """
                                WITH tz AS (
                                  SELECT COALESCE(NULLIF(timezone, ''), 'UTC') AS tz_name
                                  FROM core_reference.clinics
                                  WHERE clinic_id=:clinic_id
                                )
                                SELECT patient_id, display_name, created_at
                                FROM core_patient.patients p
                                WHERE p.clinic_id=:clinic_id
                                  AND DATE(p.created_at AT TIME ZONE (SELECT tz_name FROM tz))
                                      BETWEEN :window_start AND :window_end
                                ORDER BY p.created_at DESC, p.patient_id ASC
                                LIMIT :limit
                                """
                            ),
                            {"clinic_id": clinic_id, "window_start": window_start, "window_end": local_date, "limit": bounded_limit},
                        )
                    ).mappings().all()
                except Exception:
                    recent_rows = []
        finally:
            await engine.dispose()

        return OwnerPatientBaseSnapshot(
            clinic_id=clinic_id,
            days=window_days,
            limit=bounded_limit,
            total_patients_count=total_patients_count,
            new_patients_in_window_count=new_patients_in_window_count,
            upcoming_live_booking_patients_count=upcoming_live_booking_patients_count,
            completed_booking_patients_in_window_count=completed_booking_patients_in_window_count,
            active_care_patients_count=active_care_patients_count,
            telegram_bound_patients_count=telegram_bound_patients_count,
            recent_new_patients=[
                OwnerPatientBaseRecentRow(
                    patient_id=str(row["patient_id"]),
                    display_name=str(row["display_name"]) if row["display_name"] else None,
                    created_at=row["created_at"],
                )
                for row in recent_rows
            ],
        )

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
