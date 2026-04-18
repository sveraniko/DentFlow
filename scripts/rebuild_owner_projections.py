from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse
import asyncio

from sqlalchemy import text

from app.config.settings import get_settings
from app.domain.events import EventEnvelope
from app.infrastructure.db.engine import create_engine
from app.projections.owner.daily_metrics_projector import OwnerDailyMetricsProjector


async def _run(limit: int | None = None) -> None:
    settings = get_settings()
    projector = OwnerDailyMetricsProjector(settings.db)
    engine = create_engine(settings.db)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE owner_views.daily_clinic_metrics"))
            await conn.execute(text("TRUNCATE TABLE owner_views.daily_doctor_metrics"))
            await conn.execute(text("TRUNCATE TABLE owner_views.daily_service_metrics"))
            await conn.execute(text("TRUNCATE TABLE owner_views.owner_alerts"))

        async with engine.connect() as conn:
            q = """
                SELECT ledger_event_id, event_id, event_name, clinic_id, entity_type, entity_id,
                       actor_type, actor_id, occurred_at, payload_summary_json
                FROM analytics_raw.event_ledger
                ORDER BY ledger_event_id ASC
            """
            if limit:
                q += " LIMIT :limit"
                rows = (await conn.execute(text(q), {"limit": limit})).mappings().all()
            else:
                rows = (await conn.execute(text(q))).mappings().all()

        handled = 0
        for i, row in enumerate(rows, start=1):
            event = EventEnvelope(
                event_id=row["event_id"],
                event_name=row["event_name"],
                event_version=1,
                producer_context="analytics.event_ledger",
                clinic_id=row["clinic_id"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                actor_type=row["actor_type"],
                actor_id=row["actor_id"],
                correlation_id=None,
                causation_id=None,
                occurred_at=row["occurred_at"],
                produced_at=row["occurred_at"],
                payload=row["payload_summary_json"] or {},
            )
            ok = await projector.handle(event, outbox_event_id=i)
            handled += int(ok)
        print({"rows": len(rows), "handled": handled})
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild owner projections from analytics event ledger")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(_run(args.limit))


if __name__ == "__main__":
    main()
