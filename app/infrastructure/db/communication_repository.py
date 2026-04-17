from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from sqlalchemy import text

from app.domain.communication import MessageDelivery, ReminderJob
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
                                   planning_group, supersedes_reminder_id, created_at, updated_at, queued_at,
                                   delivery_attempts_count, last_error_code, last_error_text, last_failed_at, sent_at,
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

    async def get_reminder(self, *, reminder_id: str) -> ReminderJob | None:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT reminder_id, clinic_id, patient_id, booking_id, care_order_id, recommendation_id,
                               reminder_type, channel, status, scheduled_for, payload_key, locale_at_send_time,
                               planning_group, supersedes_reminder_id, created_at, updated_at, queued_at,
                               delivery_attempts_count, last_error_code, last_error_text, last_failed_at, sent_at,
                               acknowledged_at, canceled_at, cancel_reason_code
                        FROM communication.reminder_jobs
                        WHERE reminder_id=:reminder_id
                        """
                    ),
                    {"reminder_id": reminder_id},
                )
            ).mappings().first()
        await engine.dispose()
        return ReminderJob(**dict(row)) if row is not None else None

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

    async def claim_due_reminders(self, *, now: datetime, limit: int) -> list[ReminderJob]:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            rows = list(
                (
                    await conn.execute(
                        text(
                            """
                            WITH due AS (
                              SELECT reminder_id
                              FROM communication.reminder_jobs
                              WHERE status='scheduled'
                                AND scheduled_for <= :now
                              ORDER BY scheduled_for ASC, created_at ASC
                              LIMIT :limit
                              FOR UPDATE SKIP LOCKED
                            )
                            UPDATE communication.reminder_jobs r
                            SET status='queued', updated_at=:now, queued_at=:now
                            FROM due
                            WHERE r.reminder_id = due.reminder_id
                            RETURNING r.reminder_id, r.clinic_id, r.patient_id, r.booking_id, r.care_order_id, r.recommendation_id,
                                      r.reminder_type, r.channel, r.status, r.scheduled_for, r.payload_key, r.locale_at_send_time,
                                      r.planning_group, r.supersedes_reminder_id, r.created_at, r.updated_at, r.queued_at,
                                      r.delivery_attempts_count, r.last_error_code, r.last_error_text, r.last_failed_at, r.sent_at,
                                      r.acknowledged_at, r.canceled_at, r.cancel_reason_code
                            """
                        ),
                        {"now": now, "limit": max(limit, 0)},
                    )
                ).mappings()
            )
        await engine.dispose()
        return [ReminderJob(**dict(row)) for row in rows]

    async def create_message_delivery(self, item: MessageDelivery) -> None:
        payload = asdict(item)
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO communication.message_deliveries (
                      message_delivery_id, reminder_id, patient_id, channel, delivery_status,
                      provider_message_id, attempt_no, error_text, created_at
                    )
                    VALUES (
                      :message_delivery_id, :reminder_id, :patient_id, :channel, :delivery_status,
                      :provider_message_id, :attempt_no, :error_text, :created_at
                    )
                    """
                ),
                payload,
            )
        await engine.dispose()

    async def mark_reminder_sent(self, *, reminder_id: str, sent_at: datetime) -> bool:
        return await self._update_status(
            reminder_id=reminder_id,
            now=sent_at,
            status="sent",
            extra_set=", sent_at=:now, queued_at=NULL, last_error_code=NULL, last_error_text=NULL",
            extra_params={},
        )

    async def mark_reminder_failed(self, *, reminder_id: str, failed_at: datetime, error_text: str) -> bool:
        return await self._update_status(
            reminder_id=reminder_id,
            now=failed_at,
            status="failed",
            extra_set=", queued_at=NULL, delivery_attempts_count=delivery_attempts_count + 1, last_error_code=:error_code, last_error_text=:error_text, last_failed_at=:now",
            extra_params={"error_text": error_text, "error_code": error_text[:64]},
        )

    async def schedule_queued_reminder_retry(
        self,
        *,
        reminder_id: str,
        retry_at: datetime,
        failed_at: datetime,
        error_code: str,
        error_text: str,
    ) -> bool:
        return await self._update_status(
            reminder_id=reminder_id,
            now=failed_at,
            status="scheduled",
            extra_set=", queued_at=NULL, scheduled_for=:retry_at, delivery_attempts_count=delivery_attempts_count + 1, last_error_code=:error_code, last_error_text=:error_text, last_failed_at=:now",
            extra_params={"retry_at": retry_at, "error_code": error_code, "error_text": error_text},
        )

    async def reclaim_stale_queued_reminder(self, *, reminder_id: str, retry_at: datetime) -> bool:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    """
                    UPDATE communication.reminder_jobs
                    SET status='scheduled', scheduled_for=:retry_at, updated_at=:retry_at, queued_at=NULL
                    WHERE reminder_id=:reminder_id
                      AND status='queued'
                    """
                ),
                {"reminder_id": reminder_id, "retry_at": retry_at},
            )
        await engine.dispose()
        return bool(result.rowcount)

    async def list_stale_queued_reminders(self, *, queued_before: datetime, limit: int) -> list[ReminderJob]:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            rows = list(
                (
                    await conn.execute(
                        text(
                            """
                            SELECT reminder_id, clinic_id, patient_id, booking_id, care_order_id, recommendation_id,
                                   reminder_type, channel, status, scheduled_for, payload_key, locale_at_send_time,
                                   planning_group, supersedes_reminder_id, created_at, updated_at, queued_at,
                                   delivery_attempts_count, last_error_code, last_error_text, last_failed_at, sent_at,
                                   acknowledged_at, canceled_at, cancel_reason_code
                            FROM communication.reminder_jobs
                            WHERE status='queued'
                              AND queued_at IS NOT NULL
                              AND queued_at <= :queued_before
                            ORDER BY queued_at ASC, updated_at ASC
                            LIMIT :limit
                            """
                        ),
                        {"queued_before": queued_before, "limit": limit},
                    )
                ).mappings()
            )
        await engine.dispose()
        return [ReminderJob(**dict(row)) for row in rows]

    async def list_failed_booking_reminders(self, *, limit: int) -> list[ReminderJob]:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            rows = list(
                (
                    await conn.execute(
                        text(
                            """
                            SELECT reminder_id, clinic_id, patient_id, booking_id, care_order_id, recommendation_id,
                                   reminder_type, channel, status, scheduled_for, payload_key, locale_at_send_time,
                                   planning_group, supersedes_reminder_id, created_at, updated_at, queued_at,
                                   delivery_attempts_count, last_error_code, last_error_text, last_failed_at, sent_at,
                                   acknowledged_at, canceled_at, cancel_reason_code
                            FROM communication.reminder_jobs
                            WHERE status='failed'
                              AND booking_id IS NOT NULL
                            ORDER BY updated_at DESC
                            LIMIT :limit
                            """
                        ),
                        {"limit": limit},
                    )
                ).mappings()
            )
        await engine.dispose()
        return [ReminderJob(**dict(row)) for row in rows]

    async def list_confirmation_no_response_candidates(self, *, sent_before: datetime, limit: int) -> list[ReminderJob]:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            rows = list(
                (
                    await conn.execute(
                        text(
                            """
                            SELECT reminder_id, clinic_id, patient_id, booking_id, care_order_id, recommendation_id,
                                   reminder_type, channel, status, scheduled_for, payload_key, locale_at_send_time,
                                   planning_group, supersedes_reminder_id, created_at, updated_at, queued_at,
                                   delivery_attempts_count, last_error_code, last_error_text, last_failed_at, sent_at,
                                   acknowledged_at, canceled_at, cancel_reason_code
                            FROM communication.reminder_jobs
                            WHERE reminder_type='booking_confirmation'
                              AND status='sent'
                              AND sent_at IS NOT NULL
                              AND sent_at <= :sent_before
                              AND acknowledged_at IS NULL
                              AND booking_id IS NOT NULL
                            ORDER BY sent_at ASC
                            LIMIT :limit
                            """
                        ),
                        {"sent_before": sent_before, "limit": limit},
                    )
                ).mappings()
            )
        await engine.dispose()
        return [ReminderJob(**dict(row)) for row in rows]

    async def mark_reminder_canceled(self, *, reminder_id: str, canceled_at: datetime, reason_code: str) -> bool:
        return await self._update_status(
            reminder_id=reminder_id,
            now=canceled_at,
            status="canceled",
            extra_set=", canceled_at=:now, cancel_reason_code=:reason_code",
            extra_params={"reason_code": reason_code},
        )

    async def mark_reminder_acknowledged(self, *, reminder_id: str, acknowledged_at: datetime) -> bool:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    """
                    UPDATE communication.reminder_jobs
                    SET status='acknowledged', acknowledged_at=:acknowledged_at, updated_at=:acknowledged_at
                    WHERE reminder_id=:reminder_id
                      AND status='sent'
                    """
                ),
                {"reminder_id": reminder_id, "acknowledged_at": acknowledged_at},
            )
        await engine.dispose()
        return bool(result.rowcount)

    async def has_sent_delivery_for_provider_message(self, *, reminder_id: str, provider_message_id: str) -> bool:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            count = (
                await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) AS c
                        FROM communication.message_deliveries
                        WHERE reminder_id=:reminder_id
                          AND provider_message_id=:provider_message_id
                          AND delivery_status='sent'
                        """
                    ),
                    {"reminder_id": reminder_id, "provider_message_id": provider_message_id},
                )
            ).scalar_one()
        await engine.dispose()
        return int(count) > 0

    async def next_delivery_attempt_no(self, *, reminder_id: str) -> int:
        engine = create_engine(self._db_config)
        async with engine.connect() as conn:
            count = (
                await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) AS c
                        FROM communication.message_deliveries
                        WHERE reminder_id=:reminder_id
                        """
                    ),
                    {"reminder_id": reminder_id},
                )
            ).scalar_one()
        await engine.dispose()
        return int(count) + 1

    async def _update_status(
        self,
        *,
        reminder_id: str,
        now: datetime,
        status: str,
        extra_set: str,
        extra_params: dict[str, object],
    ) -> bool:
        engine = create_engine(self._db_config)
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    f"""
                    UPDATE communication.reminder_jobs
                    SET status=:status, updated_at=:now{extra_set}
                    WHERE reminder_id=:reminder_id
                      AND status='queued'
                    """
                ),
                {"reminder_id": reminder_id, "now": now, "status": status, **extra_params},
            )
        await engine.dispose()
        return bool(result.rowcount)


async def _insert_reminder_on_conn(conn: Any, payload: dict[str, object]) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO communication.reminder_jobs (
              reminder_id, clinic_id, patient_id, booking_id, care_order_id, recommendation_id,
              reminder_type, channel, status, scheduled_for, payload_key, locale_at_send_time,
              planning_group, supersedes_reminder_id, created_at, updated_at, queued_at,
              delivery_attempts_count, last_error_code, last_error_text, last_failed_at, sent_at, acknowledged_at,
              canceled_at, cancel_reason_code
            ) VALUES (
              :reminder_id, :clinic_id, :patient_id, :booking_id, :care_order_id, :recommendation_id,
              :reminder_type, :channel, :status, :scheduled_for, :payload_key, :locale_at_send_time,
              :planning_group, :supersedes_reminder_id, :created_at, :updated_at, :queued_at,
              :delivery_attempts_count, :last_error_code, :last_error_text, :last_failed_at, :sent_at, :acknowledged_at,
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
              queued_at=EXCLUDED.queued_at,
              delivery_attempts_count=EXCLUDED.delivery_attempts_count,
              last_error_code=EXCLUDED.last_error_code,
              last_error_text=EXCLUDED.last_error_text,
              last_failed_at=EXCLUDED.last_failed_at,
              sent_at=EXCLUDED.sent_at,
              acknowledged_at=EXCLUDED.acknowledged_at,
              canceled_at=EXCLUDED.canceled_at,
              cancel_reason_code=EXCLUDED.cancel_reason_code
            """
        ),
        payload,
    )
