from __future__ import annotations

from dataclasses import dataclass

from app.application.integration.google_calendar_projection import GoogleCalendarProjectionService
from app.domain.events import EventEnvelope
from app.infrastructure.db.google_calendar_projection_repository import DbGoogleCalendarProjectionRepository
from app.integrations.google_calendar import DisabledGoogleCalendarGateway


@dataclass(slots=True)
class GoogleCalendarScheduleProjector:
    db_config: object
    app_default_timezone: str = "UTC"
    google_calendar_enabled: bool = False
    dentflow_base_url: str = "https://dentflow.local"
    name: str = "integrations.google_calendar_schedule"

    async def handle(self, event: EventEnvelope, outbox_event_id: int) -> bool:
        if not self.google_calendar_enabled:
            return False
        if not event.event_name.startswith("booking."):
            return False

        repository = DbGoogleCalendarProjectionRepository(self.db_config, app_default_timezone=self.app_default_timezone)
        gateway = DisabledGoogleCalendarGateway(enabled=self.google_calendar_enabled)
        service = GoogleCalendarProjectionService(repository=repository, gateway=gateway, dentflow_base_url=self.dentflow_base_url)
        await service.handle_event(event)
        return True
