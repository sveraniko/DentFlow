from __future__ import annotations

import asyncio

from app.domain.events import build_event
from app.integrations.google_calendar import (
    DisabledGoogleCalendarGateway,
    MisconfiguredGoogleCalendarGateway,
    RealGoogleCalendarGateway,
    create_google_calendar_gateway,
)
from app.projections.integrations.google_calendar_schedule_projector import GoogleCalendarScheduleProjector


def test_gateway_factory_uses_real_gateway_when_enabled_and_credentials_provided() -> None:
    gateway = create_google_calendar_gateway(
        enabled=True,
        credentials_path="/tmp/service-account.json",
        subject_email=None,
        application_name="DentFlow",
        timeout_sec=10.0,
    )
    assert isinstance(gateway, RealGoogleCalendarGateway)


def test_gateway_factory_returns_disabled_when_integration_disabled() -> None:
    gateway = create_google_calendar_gateway(
        enabled=False,
        credentials_path=None,
        subject_email=None,
        application_name="DentFlow",
        timeout_sec=10.0,
    )
    assert isinstance(gateway, DisabledGoogleCalendarGateway)


def test_gateway_factory_reports_misconfiguration_when_enabled_without_credentials() -> None:
    gateway = create_google_calendar_gateway(
        enabled=True,
        credentials_path=None,
        subject_email=None,
        application_name="DentFlow",
        timeout_sec=10.0,
    )
    assert isinstance(gateway, MisconfiguredGoogleCalendarGateway)


def test_projector_is_inert_when_disabled() -> None:
    projector = GoogleCalendarScheduleProjector(db_config=object(), google_calendar_enabled=False)
    event = build_event(
        event_name="booking.created",
        producer_context="booking",
        entity_type="booking",
        entity_id="b1",
        clinic_id="c1",
        payload={},
    )
    handled = asyncio.run(projector.handle(event, outbox_event_id=1))
    assert handled is False
