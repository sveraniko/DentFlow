from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.events import EventEnvelope, build_event
from app.projections.runtime.projectors import ProjectorRunner


class _OutboxRepo:
    def __init__(self, rows):
        self.rows = rows
        self.processed = []
        self.failed = []

    async def list_after(self, *, last_outbox_event_id: int, limit: int = 200):
        return [r for r in self.rows if r["outbox_event_id"] > last_outbox_event_id][:limit]

    async def mark_event_processed(self, *, outbox_event_id: int):
        self.processed.append(outbox_event_id)

    async def mark_event_failed(self, *, outbox_event_id: int, error_text: str):
        self.failed.append((outbox_event_id, error_text))


class _CheckpointRepo:
    def __init__(self):
        self.values = {}

    async def get_checkpoint(self, *, projector_name: str):
        return self.values.get(projector_name, 0)

    async def save_checkpoint(self, *, projector_name: str, last_outbox_event_id: int):
        self.values[projector_name] = last_outbox_event_id


@dataclass
class _Projector:
    name: str
    seen: list[str]
    raise_on: str | None = None

    async def handle(self, event: EventEnvelope, outbox_event_id: int) -> bool:
        if self.raise_on == event.event_name:
            raise RuntimeError("boom")
        self.seen.append(event.event_name)
        return event.event_name.startswith("patient.")


def test_event_envelope_roundtrip() -> None:
    event = build_event(
        event_name="patient.created",
        producer_context="tests",
        clinic_id="c1",
        entity_type="patient",
        entity_id="p1",
        payload={"display_name": "Ann"},
        occurred_at=datetime(2026, 4, 17, tzinfo=timezone.utc),
    )
    rebuilt = EventEnvelope.from_record(event.to_record())
    assert rebuilt.event_id == event.event_id
    assert rebuilt.payload["display_name"] == "Ann"


def test_projector_runner_updates_checkpoints_and_handles_failure() -> None:
    event = build_event(
        event_name="patient.updated",
        producer_context="tests",
        clinic_id="c1",
        entity_type="patient",
        entity_id="p1",
        payload={"display_name": "Ann"},
    ).to_record()
    event["outbox_event_id"] = 1
    ok = _Projector(name="p.ok", seen=[])
    bad = _Projector(name="p.bad", seen=[], raise_on="patient.updated")
    outbox = _OutboxRepo([event])
    cp = _CheckpointRepo()

    runner = ProjectorRunner(outbox_repository=outbox, checkpoint_repository=cp, projectors=(ok, bad))
    asyncio.run(runner.run_once(limit=10))

    assert cp.values["p.ok"] == 1
    assert "p.bad" not in cp.values
    assert outbox.failed and outbox.failed[0][0] == 1
