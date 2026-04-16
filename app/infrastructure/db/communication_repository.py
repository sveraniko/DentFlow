from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from sqlalchemy import text

from app.domain.communication import ReminderJob
from app.infrastructure.db.engine import create_engine


class DbReminderJobRepository:
    def __init__(self, db_config) -> None:
        self._db_config = db_config

    async def create_reminder_job(self, item: ReminderJob) -> None:
        payload = asdict(item)
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            await _insert_reminder_on_conn(conn, payload)
        await engine.dispose()

    async def list_reminder_jobs_for_booking(self, *, booking_id: str) -> list[ReminderJob]:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            rows = list(
                (
                    await conn.execute(
                        text(
                            """
                            SELECT reminder_id, clinic_id, patient_id, booking_id, care_order_id, recommendation_id,
                                   reminder_type, channel, status, scheduled_for, payload_key, locale_at_send_time,
                                   planning_group, supersedes_reminder_id, created_at, updated_at, sent_at,
                                   acknowledged_at, canceled_at, cancel_reason_code
                            FROM communication.reminder_jobs
                            WHERE booking_id=:booking_id
                            ORDER BY scheduled_for ASC, created_at ASC
                            """
                        ),
                        {"booking_id": booking_id},
                    )
                ).mappings()
            )
        await engine.dispose()
        return [ReminderJob(**dict(row)) for row in rows]

    async def cancel_scheduled_reminders_for_booking(self, *, booking_id: str, canceled_at: datetime, reason_code: str) -> int:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    """
                    UPDATE communication.reminder_jobs
                    SET status='canceled', canceled_at=:canceled_at, cancel_reason_code=:reason_code, updated_at=:canceled_at
                    WHERE booking_id=:booking_id
                      AND status='scheduled'
                    """
                ),
                {"booking_id": booking_id, "canceled_at": canceled_at, "reason_code": reason_code},
            )
        await engine.dispose()
        return int(result.rowcount or 0)


async def _insert_reminder_on_conn(conn: Any, payload: dict[str, object]) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO communication.reminder_jobs (
              reminder_id, clinic_id, patient_id, booking_id, care_order_id, recommendation_id,
              reminder_type, channel, status, scheduled_for, payload_key, locale_at_send_time,
              planning_group, supersedes_reminder_id, created_at, updated_at, sent_at, acknowledged_at,
              canceled_at, cancel_reason_code
            ) VALUES (
              :reminder_id, :clinic_id, :patient_id, :booking_id, :care_order_id, :recommendation_id,
              :reminder_type, :channel, :status, :scheduled_for, :payload_key, :locale_at_send_time,
              :planning_group, :supersedes_reminder_id, :created_at, :updated_at, :sent_at, :acknowledged_at,
              :canceled_at, :cancel_reason_code
            )
            ON CONFLICT (reminder_id) DO UPDATE SET
              status=EXCLUDED.status,
              channel=EXCLUDED.channel,
              scheduled_for=EXCLUDED.scheduled_for,
              payload_key=EXCLUDED.payload_key,
              locale_at_send_time=EXCLUDED.locale_at_send_time,
              planning_group=EXCLUDED.planning_group,
              supersedes_reminder_id=EXCLUDED.supersedes_reminder_id,
              updated_at=EXCLUDED.updated_at,
              sent_at=EXCLUDED.sent_at,
              acknowledged_at=EXCLUDED.acknowledged_at,
              canceled_at=EXCLUDED.canceled_at,
              cancel_reason_code=EXCLUDED.cancel_reason_code
            """
        ),
        payload,
    )
