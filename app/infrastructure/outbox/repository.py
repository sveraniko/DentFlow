from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.domain.events import EventEnvelope
from app.infrastructure.db.engine import create_engine


@dataclass(slots=True)
class OutboxRepository:
    db_config: Any

    async def append_on_connection(self, conn: Any, event: EventEnvelope) -> int:
        payload = event.to_record()
        payload["payload_json"] = json.dumps(payload["payload_json"])
        payload["status"] = "pending"
        row = (
            await conn.execute(
                text(
                    """
                    INSERT INTO system_runtime.event_outbox (
                      event_id, event_name, event_version, producer_context, clinic_id,
                      entity_type, entity_id, actor_type, actor_id, correlation_id, causation_id,
                      payload_json, occurred_at, produced_at, status
                    ) VALUES (
                      :event_id, :event_name, :event_version, :producer_context, :clinic_id,
                      :entity_type, :entity_id, :actor_type, :actor_id, :correlation_id, :causation_id,
                      CAST(:payload_json AS JSONB), :occurred_at, :produced_at, :status
                    )
                    ON CONFLICT (event_id) DO NOTHING
                    RETURNING outbox_event_id
                    """
                ),
                payload,
            )
        ).first()
        return int(row[0]) if row else 0

    async def list_after(self, *, last_outbox_event_id: int, limit: int = 200) -> list[dict[str, object]]:
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT outbox_event_id, event_id, event_name, event_version, producer_context,
                                   clinic_id, entity_type, entity_id, actor_type, actor_id,
                                   correlation_id, causation_id, payload_json, occurred_at, produced_at,
                                   status, last_error_text, dispatched_at, created_at
                            FROM system_runtime.event_outbox
                            WHERE outbox_event_id > :last_id
                            ORDER BY outbox_event_id ASC
                            LIMIT :limit
                            """
                        ),
                        {"last_id": last_outbox_event_id, "limit": limit},
                    )
                ).mappings().all()
                return [dict(r) for r in rows]
        finally:
            await engine.dispose()

    async def mark_event_processed(self, *, outbox_event_id: int) -> None:
        engine = create_engine(self.db_config)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        UPDATE system_runtime.event_outbox
                        SET status='processed', dispatched_at=:now
                        WHERE outbox_event_id=:outbox_event_id
                        """
                    ),
                    {"outbox_event_id": outbox_event_id, "now": datetime.now(timezone.utc)},
                )
        finally:
            await engine.dispose()

    async def mark_event_failed(self, *, outbox_event_id: int, error_text: str) -> None:
        engine = create_engine(self.db_config)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        UPDATE system_runtime.event_outbox
                        SET status='failed', last_error_text=:error_text
                        WHERE outbox_event_id=:outbox_event_id
                        """
                    ),
                    {"outbox_event_id": outbox_event_id, "error_text": error_text[:1000]},
                )
        finally:
            await engine.dispose()


@dataclass(slots=True)
class ProjectorCheckpointRepository:
    db_config: Any

    async def get_checkpoint(self, *, projector_name: str) -> int:
        engine = create_engine(self.db_config)
        try:
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            """
                            SELECT last_outbox_event_id
                            FROM system_runtime.projector_checkpoints
                            WHERE projector_name=:projector_name
                            """
                        ),
                        {"projector_name": projector_name},
                    )
                ).first()
                return int(row[0]) if row else 0
        finally:
            await engine.dispose()

    async def save_checkpoint(self, *, projector_name: str, last_outbox_event_id: int) -> None:
        engine = create_engine(self.db_config)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        INSERT INTO system_runtime.projector_checkpoints (projector_name, last_outbox_event_id)
                        VALUES (:projector_name, :last_outbox_event_id)
                        ON CONFLICT (projector_name) DO UPDATE SET
                          last_outbox_event_id=EXCLUDED.last_outbox_event_id,
                          updated_at=NOW()
                        """
                    ),
                    {"projector_name": projector_name, "last_outbox_event_id": last_outbox_event_id},
                )
        finally:
            await engine.dispose()

    async def reset_checkpoint(self, *, projector_name: str) -> None:
        await self.save_checkpoint(projector_name=projector_name, last_outbox_event_id=0)
