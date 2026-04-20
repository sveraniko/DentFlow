from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from app.domain.events import EventEnvelope
from app.infrastructure.outbox.repository import OutboxRepository, ProjectorCheckpointRepository


class Projector(Protocol):
    name: str

    async def handle(self, event: EventEnvelope, outbox_event_id: int) -> bool: ...


@dataclass(slots=True)
class ProjectorRunResult:
    scanned_events: int
    handled_by_projector: dict[str, int]
    failed_outbox_event_id: int | None = None


@dataclass(slots=True)
class ProjectorRunner:
    outbox_repository: OutboxRepository
    checkpoint_repository: ProjectorCheckpointRepository
    projectors: tuple[Projector, ...]

    async def run_once(self, *, limit: int = 200) -> ProjectorRunResult:
        logger = logging.getLogger("dentflow.projector")
        stats = {projector.name: 0 for projector in self.projectors}
        scanned_events = 0
        checkpoints = {
            projector.name: await self.checkpoint_repository.get_checkpoint(projector_name=projector.name)
            for projector in self.projectors
        }
        base_last = min(checkpoints.values()) if checkpoints else 0
        rows = await self.outbox_repository.list_after(last_outbox_event_id=base_last, limit=limit)
        for row in rows:
            scanned_events += 1
            event = EventEnvelope.from_record(row)
            outbox_event_id = int(row["outbox_event_id"])
            try:
                for projector in self.projectors:
                    if outbox_event_id <= checkpoints[projector.name]:
                        continue
                    handled = await projector.handle(event, outbox_event_id)
                    if handled:
                        stats[projector.name] += 1
                    checkpoints[projector.name] = outbox_event_id
                    await self.checkpoint_repository.save_checkpoint(
                        projector_name=projector.name,
                        last_outbox_event_id=outbox_event_id,
                    )
                await self.outbox_repository.mark_event_processed(outbox_event_id=outbox_event_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("projector processing failed", extra={"extra": {"event_id": event.event_id, "error": str(exc)}})
                await self.outbox_repository.mark_event_failed(outbox_event_id=outbox_event_id, error_text=str(exc))
                return ProjectorRunResult(
                    scanned_events=scanned_events,
                    handled_by_projector=stats,
                    failed_outbox_event_id=outbox_event_id,
                )
        return ProjectorRunResult(scanned_events=scanned_events, handled_by_projector=stats)
