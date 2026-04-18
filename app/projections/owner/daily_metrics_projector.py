from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text

from app.domain.events import EventEnvelope
from app.infrastructure.db.engine import create_engine


@dataclass(slots=True)
class OwnerDailyMetricsProjector:
    db_config: object
    name: str = "owner.daily_metrics"

    async def handle(self, event: EventEnvelope, outbox_event_id: int) -> bool:
        if not event.clinic_id:
            return False
        event_name = event.event_name
        if not (
            event_name.startswith("patient.")
            or event_name.startswith("booking.")
            or event_name.startswith("reminder.")
            or event_name in {"chart.opened", "encounter.created"}
        ):
            return False

        engine = create_engine(self.db_config)
        try:
            async with engine.begin() as conn:
                metrics_date = await _resolve_local_date(conn, clinic_id=event.clinic_id, occurred_at=event.occurred_at)

                if event_name == "patient.created":
                    await _inc_clinic(conn, clinic_id=event.clinic_id, metrics_date=metrics_date, column="new_patients_count")
                elif event_name.startswith("booking."):
                    await self._handle_booking(conn, event=event, metrics_date=metrics_date)
                elif event_name.startswith("reminder."):
                    await self._handle_reminder(conn, event=event, metrics_date=metrics_date)
                elif event_name == "chart.opened":
                    await _inc_clinic(conn, clinic_id=event.clinic_id, metrics_date=metrics_date, column="charts_opened_count")
                elif event_name == "encounter.created":
                    await _inc_clinic(conn, clinic_id=event.clinic_id, metrics_date=metrics_date, column="encounters_created_count")
                    doctor_id = str(event.payload.get("doctor_id") or "").strip() if event.payload else ""
                    if doctor_id:
                        await _inc_doctor(
                            conn,
                            clinic_id=event.clinic_id,
                            metrics_date=metrics_date,
                            doctor_id=doctor_id,
                            column="encounters_created_count",
                        )

                await _refresh_alerts(conn, clinic_id=event.clinic_id, metrics_date=metrics_date)
                return True
        finally:
            await engine.dispose()

    async def _handle_booking(self, conn, *, event: EventEnvelope, metrics_date: date) -> None:
        mapping = {
            "booking.created": "bookings_created_count",
            "booking.confirmed": "bookings_confirmed_count",
            "booking.canceled": "bookings_canceled_count",
            "booking.completed": "bookings_completed_count",
            "booking.no_show_marked": "bookings_no_show_count",
            "booking.reschedule_requested": "bookings_reschedule_requested_count",
        }
        column = mapping.get(event.event_name)
        if not column:
            return
        await _inc_clinic(conn, clinic_id=event.clinic_id or "", metrics_date=metrics_date, column=column)

        booking = await _fetch_booking_dims(conn, booking_id=event.entity_id)
        if booking:
            if booking.get("doctor_id"):
                await _inc_doctor(
                    conn,
                    clinic_id=event.clinic_id or "",
                    metrics_date=metrics_date,
                    doctor_id=str(booking["doctor_id"]),
                    column=column,
                )
            if booking.get("service_id"):
                await _inc_service(
                    conn,
                    clinic_id=event.clinic_id or "",
                    metrics_date=metrics_date,
                    service_id=str(booking["service_id"]),
                    column=column,
                )

    async def _handle_reminder(self, conn, *, event: EventEnvelope, metrics_date: date) -> None:
        mapping = {
            "reminder.scheduled": "reminders_scheduled_count",
            "reminder.sent": "reminders_sent_count",
            "reminder.acknowledged": "reminders_acknowledged_count",
            "reminder.failed": "reminders_failed_count",
        }
        column = mapping.get(event.event_name)
        if not column:
            return
        await _inc_clinic(conn, clinic_id=event.clinic_id or "", metrics_date=metrics_date, column=column)

        booking_id = str(event.payload.get("booking_id") or "").strip() if event.payload else ""
        if not booking_id:
            return
        booking = await _fetch_booking_dims(conn, booking_id=booking_id)
        if booking and booking.get("doctor_id") and column in {"reminders_sent_count", "reminders_failed_count"}:
            await _inc_doctor(
                conn,
                clinic_id=event.clinic_id or "",
                metrics_date=metrics_date,
                doctor_id=str(booking["doctor_id"]),
                column=column,
            )


async def _fetch_booking_dims(conn, *, booking_id: str) -> dict[str, object] | None:
    row = (
        await conn.execute(
            text(
                """
                SELECT doctor_id, service_id
                FROM booking.bookings
                WHERE booking_id=:booking_id
                """
            ),
            {"booking_id": booking_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def _resolve_local_date(conn, *, clinic_id: str, occurred_at: datetime) -> date:
    row = (
        await conn.execute(
            text("SELECT timezone FROM core_reference.clinics WHERE clinic_id=:clinic_id"),
            {"clinic_id": clinic_id},
        )
    ).mappings().first()
    tz_name = str(row["timezone"]) if row and row.get("timezone") else "UTC"
    try:
        zone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("UTC")
    return occurred_at.astimezone(zone).date()


async def _inc_clinic(conn, *, clinic_id: str, metrics_date: date, column: str) -> None:
    await conn.execute(
        text(
            f"""
            INSERT INTO owner_views.daily_clinic_metrics (clinic_id, metrics_date, {column})
            VALUES (:clinic_id, :metrics_date, 1)
            ON CONFLICT (clinic_id, metrics_date) DO UPDATE SET
              {column}=owner_views.daily_clinic_metrics.{column}+1,
              updated_at=NOW()
            """
        ),
        {"clinic_id": clinic_id, "metrics_date": metrics_date},
    )


async def _inc_doctor(conn, *, clinic_id: str, metrics_date: date, doctor_id: str, column: str) -> None:
    await conn.execute(
        text(
            f"""
            INSERT INTO owner_views.daily_doctor_metrics (clinic_id, metrics_date, doctor_id, {column})
            VALUES (:clinic_id, :metrics_date, :doctor_id, 1)
            ON CONFLICT (clinic_id, metrics_date, doctor_id) DO UPDATE SET
              {column}=owner_views.daily_doctor_metrics.{column}+1,
              updated_at=NOW()
            """
        ),
        {"clinic_id": clinic_id, "metrics_date": metrics_date, "doctor_id": doctor_id},
    )


async def _inc_service(conn, *, clinic_id: str, metrics_date: date, service_id: str, column: str) -> None:
    await conn.execute(
        text(
            f"""
            INSERT INTO owner_views.daily_service_metrics (clinic_id, metrics_date, service_id, {column})
            VALUES (:clinic_id, :metrics_date, :service_id, 1)
            ON CONFLICT (clinic_id, metrics_date, service_id) DO UPDATE SET
              {column}=owner_views.daily_service_metrics.{column}+1,
              updated_at=NOW()
            """
        ),
        {"clinic_id": clinic_id, "metrics_date": metrics_date, "service_id": service_id},
    )


async def _refresh_alerts(conn, *, clinic_id: str, metrics_date: date) -> None:
    metrics = (
        await conn.execute(
            text(
                """
                SELECT bookings_created_count, bookings_confirmed_count, bookings_no_show_count,
                       reminders_failed_count
                FROM owner_views.daily_clinic_metrics
                WHERE clinic_id=:clinic_id AND metrics_date=:metrics_date
                """
            ),
            {"clinic_id": clinic_id, "metrics_date": metrics_date},
        )
    ).mappings().first()
    if metrics is None:
        return

    created = int(metrics["bookings_created_count"])
    confirmed = int(metrics["bookings_confirmed_count"])
    no_show = int(metrics["bookings_no_show_count"])
    reminder_failed = int(metrics["reminders_failed_count"])

    if created >= 5 and confirmed / max(created, 1) < 0.6:
        await _upsert_open_alert(
            conn,
            clinic_id=clinic_id,
            metrics_date=metrics_date,
            alert_type="low_confirmation_rate",
            severity="high",
            summary_text=f"Low confirmation rate: {confirmed}/{created}",
            details_json='{"confirmed": %d, "created": %d}' % (confirmed, created),
        )
    if no_show >= 3 and no_show / max(created, 1) >= 0.25:
        await _upsert_open_alert(
            conn,
            clinic_id=clinic_id,
            metrics_date=metrics_date,
            alert_type="no_show_spike",
            severity="high",
            summary_text=f"No-show spike detected: {no_show}",
            details_json='{"no_show": %d, "created": %d}' % (no_show, created),
        )
    if reminder_failed >= 3:
        await _upsert_open_alert(
            conn,
            clinic_id=clinic_id,
            metrics_date=metrics_date,
            alert_type="reminder_failure_spike",
            severity="medium",
            summary_text=f"Reminder failures spike: {reminder_failed}",
            details_json='{"reminders_failed": %d}' % reminder_failed,
        )

    pending = (
        await conn.execute(
            text(
                """
                SELECT COUNT(*) AS c
                FROM booking.bookings
                WHERE clinic_id=:clinic_id
                  AND status='pending_confirmation'
                  AND DATE(scheduled_start_at AT TIME ZONE 'UTC') = :metrics_date
                """
            ),
            {"clinic_id": clinic_id, "metrics_date": metrics_date},
        )
    ).scalar_one()
    if int(pending) >= 8:
        await _upsert_open_alert(
            conn,
            clinic_id=clinic_id,
            metrics_date=metrics_date,
            alert_type="open_confirmation_backlog",
            severity="medium",
            summary_text=f"Pending confirmations backlog: {int(pending)}",
            details_json='{"pending_confirmations": %d}' % int(pending),
        )


async def _upsert_open_alert(
    conn,
    *,
    clinic_id: str,
    metrics_date: date,
    alert_type: str,
    severity: str,
    summary_text: str,
    details_json: str,
) -> None:
    row = (
        await conn.execute(
            text(
                """
                SELECT owner_alert_id
                FROM owner_views.owner_alerts
                WHERE clinic_id=:clinic_id AND alert_type=:alert_type AND alert_date=:alert_date AND status='open'
                LIMIT 1
                """
            ),
            {"clinic_id": clinic_id, "alert_type": alert_type, "alert_date": metrics_date},
        )
    ).first()
    if row:
        await conn.execute(
            text(
                """
                UPDATE owner_views.owner_alerts
                SET summary_text=:summary_text,
                    details_json=CAST(:details_json AS JSONB),
                    severity=:severity,
                    updated_at=NOW()
                WHERE owner_alert_id=:owner_alert_id
                """
            ),
            {
                "owner_alert_id": row[0],
                "summary_text": summary_text,
                "details_json": details_json,
                "severity": severity,
            },
        )
        return

    await conn.execute(
        text(
            """
            INSERT INTO owner_views.owner_alerts (
              owner_alert_id, clinic_id, alert_type, severity, status,
              entity_type, entity_id, alert_date, summary_text, details_json, created_at, updated_at
            ) VALUES (
              :owner_alert_id, :clinic_id, :alert_type, :severity, 'open',
              NULL, NULL, :alert_date, :summary_text, CAST(:details_json AS JSONB), NOW(), NOW()
            )
            """
        ),
        {
            "owner_alert_id": f"oal_{uuid4().hex[:16]}",
            "clinic_id": clinic_id,
            "alert_type": alert_type,
            "severity": severity,
            "alert_date": metrics_date,
            "summary_text": summary_text,
            "details_json": details_json,
        },
    )
