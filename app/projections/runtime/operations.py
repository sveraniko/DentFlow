from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.infrastructure.outbox.repository import OutboxRepository, ProjectorCheckpointRepository


@dataclass(frozen=True, slots=True)
class ProjectorLagStatus:
    projector_name: str
    last_outbox_event_id: int
    outbox_tail_event_id: int
    lag_events: int
    checkpoint_updated_at: datetime | None
    checkpoint_produced_at: datetime | None
    freshness_delay_sec: int | None


class ProjectorOperationsService:
    def __init__(
        self,
        *,
        outbox_repository: OutboxRepository,
        checkpoint_repository: ProjectorCheckpointRepository,
        projector_names: tuple[str, ...],
    ) -> None:
        self._outbox_repository = outbox_repository
        self._checkpoint_repository = checkpoint_repository
        self._projector_names = projector_names

    async def lag_status(self) -> dict[str, Any]:
        tail = await self._outbox_repository.get_tail()
        tail_id = int(tail["outbox_event_id"]) if tail else 0
        tail_produced_at = tail.get("produced_at") if tail else None
        rows = {row["projector_name"]: row for row in await self._checkpoint_repository.list_checkpoints()}
        statuses: list[ProjectorLagStatus] = []
        for projector_name in self._projector_names:
            cp_row = rows.get(projector_name, {})
            checkpoint_id = int(cp_row.get("last_outbox_event_id", 0) or 0)
            cp_meta = await self._outbox_repository.get_event_meta(outbox_event_id=checkpoint_id) if checkpoint_id > 0 else None
            cp_produced_at = cp_meta.get("produced_at") if cp_meta else None
            freshness_delay_sec: int | None = None
            if tail_produced_at and cp_produced_at:
                freshness_delay_sec = max(0, int((tail_produced_at - cp_produced_at).total_seconds()))
            elif tail_produced_at and checkpoint_id == 0:
                freshness_delay_sec = max(0, int((datetime.now(timezone.utc) - tail_produced_at).total_seconds()))
            statuses.append(
                ProjectorLagStatus(
                    projector_name=projector_name,
                    last_outbox_event_id=checkpoint_id,
                    outbox_tail_event_id=tail_id,
                    lag_events=max(0, tail_id - checkpoint_id),
                    checkpoint_updated_at=cp_row.get("updated_at"),
                    checkpoint_produced_at=cp_produced_at,
                    freshness_delay_sec=freshness_delay_sec,
                )
            )
        max_lag = max((s.lag_events for s in statuses), default=0)
        return {
            "outbox_tail_event_id": tail_id,
            "projector_count": len(statuses),
            "max_lag_events": max_lag,
            "projectors": [
                {
                    "projector_name": s.projector_name,
                    "last_outbox_event_id": s.last_outbox_event_id,
                    "outbox_tail_event_id": s.outbox_tail_event_id,
                    "lag_events": s.lag_events,
                    "checkpoint_updated_at": s.checkpoint_updated_at.isoformat() if s.checkpoint_updated_at else None,
                    "checkpoint_produced_at": s.checkpoint_produced_at.isoformat() if s.checkpoint_produced_at else None,
                    "freshness_delay_sec": s.freshness_delay_sec,
                }
                for s in statuses
            ],
        }

    async def recent_failures(self, *, limit: int = 20, projector_name: str | None = None) -> list[dict[str, Any]]:
        rows = await self._checkpoint_repository.list_recent_failures(limit=limit, projector_name=projector_name)
        for row in rows:
            if isinstance(row.get("failed_at"), datetime):
                row["failed_at"] = row["failed_at"].isoformat()
        return rows

    async def retry_failed_event(self, *, projector_name: str, outbox_event_id: int) -> dict[str, Any]:
        await self._checkpoint_repository.save_checkpoint(
            projector_name=projector_name,
            last_outbox_event_id=max(0, outbox_event_id - 1),
        )
        retried = await self._outbox_repository.retry_event(outbox_event_id=outbox_event_id)
        return {
            "projector_name": projector_name,
            "outbox_event_id": outbox_event_id,
            "checkpoint_set_to": max(0, outbox_event_id - 1),
            "outbox_retry_marked": retried,
        }
