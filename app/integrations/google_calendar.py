from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from app.application.integration.google_calendar_projection import CalendarEventPayload


@dataclass(slots=True)
class DisabledGoogleCalendarGateway:
    enabled: bool = False

    async def upsert_event(self, *, calendar_id: str, event: CalendarEventPayload, external_event_id: str | None) -> str:
        if not self.enabled:
            raise RuntimeError("google_calendar_integration_disabled")
        return external_event_id or f"gcal_{uuid4().hex}"

    async def cancel_event(self, *, calendar_id: str, external_event_id: str) -> None:
        if not self.enabled:
            raise RuntimeError("google_calendar_integration_disabled")


@dataclass(slots=True)
class InMemoryGoogleCalendarGateway:
    events: dict[tuple[str, str], CalendarEventPayload] = field(default_factory=dict)

    async def upsert_event(self, *, calendar_id: str, event: CalendarEventPayload, external_event_id: str | None) -> str:
        event_id = external_event_id or f"gcal_{uuid4().hex}"
        self.events[(calendar_id, event_id)] = event
        return event_id

    async def cancel_event(self, *, calendar_id: str, external_event_id: str) -> None:
        self.events.pop((calendar_id, external_event_id), None)
