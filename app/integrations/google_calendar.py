from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timezone
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


@dataclass(slots=True)
class MisconfiguredGoogleCalendarGateway:
    reason: str

    async def upsert_event(self, *, calendar_id: str, event: CalendarEventPayload, external_event_id: str | None) -> str:
        raise RuntimeError(self.reason)

    async def cancel_event(self, *, calendar_id: str, external_event_id: str) -> None:
        raise RuntimeError(self.reason)


@dataclass(slots=True)
class RealGoogleCalendarGateway:
    credentials_path: str
    subject_email: str | None = None
    application_name: str = "DentFlow"
    timeout_sec: float = 10.0
    _service: object | None = None

    async def upsert_event(self, *, calendar_id: str, event: CalendarEventPayload, external_event_id: str | None) -> str:
        return await asyncio.to_thread(
            self._upsert_event_blocking,
            calendar_id,
            event,
            external_event_id,
        )

    async def cancel_event(self, *, calendar_id: str, external_event_id: str) -> None:
        await asyncio.to_thread(self._cancel_event_blocking, calendar_id, external_event_id)

    def _upsert_event_blocking(self, calendar_id: str, event: CalendarEventPayload, external_event_id: str | None) -> str:
        service = self._get_service()
        payload = {
            "summary": event.title,
            "description": event.description,
            "start": {
                "dateTime": event.starts_at_local.astimezone(timezone.utc).isoformat(),
                "timeZone": event.timezone,
            },
            "end": {
                "dateTime": event.ends_at_local.astimezone(timezone.utc).isoformat(),
                "timeZone": event.timezone,
            },
        }
        if external_event_id:
            response = (
                service.events()
                .patch(calendarId=calendar_id, eventId=external_event_id, body=payload)
                .execute(num_retries=2)
            )
        else:
            response = service.events().insert(calendarId=calendar_id, body=payload).execute(num_retries=2)
        event_id = response.get("id")
        if not event_id:
            raise RuntimeError("google_calendar_missing_event_id")
        return str(event_id)

    def _cancel_event_blocking(self, calendar_id: str, external_event_id: str) -> None:
        service = self._get_service()
        service.events().delete(calendarId=calendar_id, eventId=external_event_id).execute(num_retries=2)

    def _get_service(self):
        if self._service is not None:
            return self._service

        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover - import path validation
            raise RuntimeError("google_calendar_dependencies_missing") from exc

        scopes = ("https://www.googleapis.com/auth/calendar",)
        credentials = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
        if self.subject_email:
            credentials = credentials.with_subject(self.subject_email)
        self._service = build(
            "calendar",
            "v3",
            credentials=credentials,
            cache_discovery=False,
            num_retries=2,
        )
        return self._service


def create_google_calendar_gateway(
    *,
    enabled: bool,
    credentials_path: str | None,
    subject_email: str | None,
    application_name: str,
    timeout_sec: float,
):
    if not enabled:
        return DisabledGoogleCalendarGateway(enabled=False)
    if not credentials_path:
        return MisconfiguredGoogleCalendarGateway(reason="google_calendar_credentials_path_required")
    return RealGoogleCalendarGateway(
        credentials_path=credentials_path,
        subject_email=subject_email,
        application_name=application_name,
        timeout_sec=timeout_sec,
    )
