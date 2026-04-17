from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_id: str
    event_name: str
    event_version: int
    producer_context: str
    clinic_id: str | None
    entity_type: str
    entity_id: str
    actor_type: str | None
    actor_id: str | None
    correlation_id: str | None
    causation_id: str | None
    occurred_at: datetime
    produced_at: datetime
    payload: dict[str, object]

    def to_record(self) -> dict[str, object]:
        payload = asdict(self)
        payload["payload_json"] = payload.pop("payload")
        return payload

    @classmethod
    def from_record(cls, row: dict[str, object]) -> "EventEnvelope":
        payload = {k: v for k, v in dict(row).items() if k in {
            "event_id", "event_name", "event_version", "producer_context", "clinic_id",
            "entity_type", "entity_id", "actor_type", "actor_id", "correlation_id",
            "causation_id", "payload_json", "occurred_at", "produced_at"
        }}
        payload["payload"] = payload.pop("payload_json")
        return cls(**payload)


def build_event(
    *,
    event_name: str,
    producer_context: str,
    entity_type: str,
    entity_id: str,
    clinic_id: str | None,
    payload: dict[str, object] | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    event_version: int = 1,
    occurred_at: datetime | None = None,
) -> EventEnvelope:
    now = datetime.now(timezone.utc)
    stamp = occurred_at or now
    return EventEnvelope(
        event_id=f"evt_{uuid4().hex}",
        event_name=event_name,
        event_version=event_version,
        producer_context=producer_context,
        clinic_id=clinic_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
        occurred_at=stamp,
        produced_at=now,
        payload=payload or {},
    )
