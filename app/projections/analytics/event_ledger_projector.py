from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from app.domain.events import EventEnvelope
from app.infrastructure.db.engine import create_engine


@dataclass(slots=True)
class AnalyticsEventLedgerProjector:
    db_config: Any
    name: str = "analytics.event_ledger"

    async def handle(self, event: EventEnvelope, outbox_event_id: int) -> bool:
        engine = create_engine(self.db_config)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        INSERT INTO analytics_raw.event_ledger (
                          event_id, event_name, clinic_id, entity_type, entity_id,
                          actor_type, actor_id, occurred_at, payload_summary_json
                        ) VALUES (
                          :event_id, :event_name, :clinic_id, :entity_type, :entity_id,
                          :actor_type, :actor_id, :occurred_at, CAST(:payload_summary_json AS JSONB)
                        )
                        ON CONFLICT (event_id) DO NOTHING
                        """
                    ),
                    {
                        "event_id": event.event_id,
                        "event_name": event.event_name,
                        "clinic_id": event.clinic_id,
                        "entity_type": event.entity_type,
                        "entity_id": event.entity_id,
                        "actor_type": event.actor_type,
                        "actor_id": event.actor_id,
                        "occurred_at": event.occurred_at,
                        "payload_summary_json": json.dumps(_payload_summary(event.payload)),
                    },
                )
        finally:
            await engine.dispose()
        return True


def _payload_summary(payload: dict[str, object]) -> dict[str, object]:
    summary: dict[str, object] = {}
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            summary[key] = value
        elif isinstance(value, list):
            summary[key] = {"type": "list", "size": len(value)}
        elif isinstance(value, dict):
            summary[key] = {"type": "dict", "keys": sorted(list(value.keys()))[:10]}
        else:
            summary[key] = str(value)
    return summary
