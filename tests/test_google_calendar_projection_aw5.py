from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone

from app.application.integration.google_calendar_projection import (
    CalendarEventMapping,
    CalendarProjectionBooking,
    GoogleCalendarProjectionService,
    render_calendar_event,
)
from app.integrations.google_calendar import InMemoryGoogleCalendarGateway


class _Repo:
    def __init__(self, booking: CalendarProjectionBooking):
        self.booking = booking
        self.mapping: CalendarEventMapping | None = None

    async def get_booking_projection(self, *, booking_id: str) -> CalendarProjectionBooking | None:
        return self.booking if self.booking.booking_id == booking_id else None

    async def get_event_mapping(self, *, booking_id: str) -> CalendarEventMapping | None:
        return self.mapping if self.mapping and self.mapping.booking_id == booking_id else None

    async def upsert_event_mapping(
        self,
        *,
        booking_id: str,
        clinic_id: str,
        target_calendar_id: str,
        external_event_id: str | None,
        sync_status: str,
        payload_hash: str | None,
        last_error_text: str | None,
    ) -> None:
        attempts = (self.mapping.sync_attempts if self.mapping else 0) + 1
        self.mapping = CalendarEventMapping(
            booking_id=booking_id,
            clinic_id=clinic_id,
            calendar_provider="google_calendar",
            target_calendar_id=target_calendar_id,
            external_event_id=external_event_id,
            sync_status=sync_status,
            sync_attempts=attempts,
            last_synced_at=datetime.now(timezone.utc),
            last_error_text=last_error_text,
            payload_hash=payload_hash,
        )


class _FailingGateway(InMemoryGoogleCalendarGateway):
    def __init__(self):
        super().__init__()
        self.fail = True

    async def upsert_event(self, *, calendar_id: str, event, external_event_id: str | None) -> str:  # type: ignore[override]
        if self.fail:
            raise RuntimeError("provider_timeout")
        return await super().upsert_event(calendar_id=calendar_id, event=event, external_event_id=external_event_id)


def _booking(status: str = "pending_confirmation") -> CalendarProjectionBooking:
    return CalendarProjectionBooking(
        booking_id="b1",
        clinic_id="c1",
        doctor_id="d1",
        service_id="s1",
        patient_id="p1",
        status=status,
        scheduled_start_at=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
        scheduled_end_at=datetime(2026, 4, 19, 13, 0, tzinfo=timezone.utc),
        timezone="Europe/Kyiv",
        doctor_calendar_id="doc_cal_d1",
        patient_display_name="Anna Petrova",
        doctor_display_name="Dr. Smith",
        service_label="Consultation",
        service_locale="en",
        branch_label="Main Branch",
    )


def test_projection_creates_mapping_and_event() -> None:
    repo = _Repo(_booking())
    gateway = InMemoryGoogleCalendarGateway()
    service = GoogleCalendarProjectionService(repository=repo, gateway=gateway, dentflow_base_url="https://dentflow.example")

    asyncio.run(service.sync_booking(booking_id="b1"))

    assert repo.mapping is not None
    assert repo.mapping.sync_status == "synced"
    assert repo.mapping.external_event_id is not None
    assert (repo.mapping.target_calendar_id, repo.mapping.external_event_id) in gateway.events


def test_projection_updates_existing_mapping_on_reschedule() -> None:
    repo = _Repo(_booking(status="confirmed"))
    gateway = InMemoryGoogleCalendarGateway()
    service = GoogleCalendarProjectionService(repository=repo, gateway=gateway)

    asyncio.run(service.sync_booking(booking_id="b1"))
    first_event_id = repo.mapping.external_event_id

    repo.booking = replace(
        repo.booking,
        scheduled_start_at=datetime(2026, 4, 19, 14, 0, tzinfo=timezone.utc),
        scheduled_end_at=datetime(2026, 4, 19, 15, 0, tzinfo=timezone.utc),
        status="confirmed",
    )
    asyncio.run(service.sync_booking(booking_id="b1"))

    assert repo.mapping.external_event_id == first_event_id
    event = gateway.events[(repo.mapping.target_calendar_id, first_event_id)]
    assert event.starts_at_local.hour == 17


def test_projection_cancels_calendar_event_when_booking_canceled() -> None:
    repo = _Repo(_booking(status="confirmed"))
    gateway = InMemoryGoogleCalendarGateway()
    service = GoogleCalendarProjectionService(repository=repo, gateway=gateway)
    asyncio.run(service.sync_booking(booking_id="b1"))

    event_id = repo.mapping.external_event_id
    repo.booking = replace(repo.booking, status="canceled")
    asyncio.run(service.sync_booking(booking_id="b1"))

    assert repo.mapping.sync_status == "canceled"
    assert repo.mapping.external_event_id is None
    assert ("doc_cal_d1", event_id) not in gateway.events


def test_projection_failure_is_detectable_and_retryable() -> None:
    repo = _Repo(_booking(status="confirmed"))
    gateway = _FailingGateway()
    service = GoogleCalendarProjectionService(repository=repo, gateway=gateway)

    asyncio.run(service.sync_booking(booking_id="b1"))
    assert repo.mapping.sync_status == "failed"
    assert repo.booking.status == "confirmed"

    gateway.fail = False
    asyncio.run(service.sync_booking(booking_id="b1"))
    assert repo.mapping.sync_status == "synced"


def test_event_rendering_is_local_time_and_privacy_bounded() -> None:
    payload = render_calendar_event(booking=_booking(), dentflow_base_url="https://dentflow.example")
    assert payload.starts_at_local.hour == 15
    assert "Anna P." in payload.title
    assert "Diagnosis" not in payload.description
    assert "DentFlow booking: b1" in payload.description
    assert "Open in DentFlow: https://dentflow.example/admin/booking/b1" in payload.description


def test_event_rendering_humanizes_raw_service_title_key_when_missing_localized_label() -> None:
    booking = replace(_booking(), service_label="service.deep_cleaning", service_locale="en")
    payload = render_calendar_event(booking=booking, dentflow_base_url="https://dentflow.example")
    assert "Deep cleaning" in payload.title
    assert "service.deep_cleaning" not in payload.title
