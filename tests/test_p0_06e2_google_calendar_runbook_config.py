from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from app.application.integration.google_calendar_projection import CalendarEventPayload
from app.config.settings import IntegrationsConfig
from app.integrations.google_calendar import (
    DisabledGoogleCalendarGateway,
    InMemoryGoogleCalendarGateway,
    MisconfiguredGoogleCalendarGateway,
    RealGoogleCalendarGateway,
    create_google_calendar_gateway,
)


RUNBOOK = Path("docs/runbooks/google_calendar_projection_runbook.md")


def test_runbook_exists_and_documents_truth_boundary_and_commands() -> None:
    assert RUNBOOK.exists()
    text = RUNBOOK.read_text(encoding="utf-8")

    required_snippets = [
        "DentFlow",
        "Google Calendar",
        "one-way",
        "mirror",
        "not booking truth",
        "No Calendar-to-DentFlow sync",
        "/admin_calendar",
        "/admin_integrations",
        "process_outbox_events.py",
        "retry_google_calendar_projection.py",
    ]
    for snippet in required_snippets:
        assert snippet in text


def test_env_example_includes_required_google_calendar_keys() -> None:
    env_text = Path(".env.example").read_text(encoding="utf-8")
    required_keys = [
        "INTEGRATIONS_GOOGLE_CALENDAR_ENABLED",
        "INTEGRATIONS_GOOGLE_CALENDAR_CREDENTIALS_PATH",
        "INTEGRATIONS_GOOGLE_CALENDAR_SUBJECT_EMAIL",
        "INTEGRATIONS_GOOGLE_CALENDAR_APPLICATION_NAME",
        "INTEGRATIONS_GOOGLE_CALENDAR_TIMEOUT_SEC",
        "INTEGRATIONS_DENTFLOW_BASE_URL",
    ]
    for key in required_keys:
        assert f"{key}=" in env_text


def test_integrations_config_parses_google_calendar_fields(monkeypatch) -> None:
    monkeypatch.setenv("INTEGRATIONS_GOOGLE_CALENDAR_ENABLED", "true")
    monkeypatch.setenv("INTEGRATIONS_GOOGLE_CALENDAR_CREDENTIALS_PATH", "/tmp/gcal.json")
    monkeypatch.setenv("INTEGRATIONS_GOOGLE_CALENDAR_SUBJECT_EMAIL", "ops@example.com")
    monkeypatch.setenv("INTEGRATIONS_GOOGLE_CALENDAR_APPLICATION_NAME", "DentFlow")
    monkeypatch.setenv("INTEGRATIONS_GOOGLE_CALENDAR_TIMEOUT_SEC", "12.5")

    cfg = IntegrationsConfig()

    assert cfg.google_calendar_enabled is True
    assert cfg.google_calendar_credentials_path == "/tmp/gcal.json"
    assert cfg.google_calendar_subject_email == "ops@example.com"
    assert cfg.google_calendar_application_name == "DentFlow"
    assert cfg.google_calendar_timeout_sec == 12.5


def test_integrations_config_default_application_name_is_dentflow(monkeypatch) -> None:
    monkeypatch.delenv("INTEGRATIONS_GOOGLE_CALENDAR_APPLICATION_NAME", raising=False)
    cfg = IntegrationsConfig()
    assert cfg.google_calendar_application_name == "DentFlow"


def test_gateway_factory_disabled_returns_disabled_gateway_and_raises_on_upsert() -> None:
    gateway = create_google_calendar_gateway(
        enabled=False,
        credentials_path=None,
        subject_email=None,
        application_name="DentFlow",
        timeout_sec=10.0,
    )
    assert isinstance(gateway, DisabledGoogleCalendarGateway)

    event = CalendarEventPayload(
        title="Title",
        description="Description",
        starts_at_local=datetime.now(timezone.utc),
        ends_at_local=datetime.now(timezone.utc),
        timezone="UTC",
        status="confirmed",
    )

    try:
        asyncio.run(gateway.upsert_event(calendar_id="cal", event=event, external_event_id=None))
    except RuntimeError as exc:
        assert str(exc) == "google_calendar_integration_disabled"
    else:  # pragma: no cover
        raise AssertionError("expected disabled gateway to raise")


def test_gateway_factory_enabled_without_credentials_returns_misconfigured_gateway() -> None:
    gateway = create_google_calendar_gateway(
        enabled=True,
        credentials_path=None,
        subject_email=None,
        application_name="DentFlow",
        timeout_sec=10.0,
    )
    assert isinstance(gateway, MisconfiguredGoogleCalendarGateway)

    event = CalendarEventPayload(
        title="Title",
        description="Description",
        starts_at_local=datetime.now(timezone.utc),
        ends_at_local=datetime.now(timezone.utc),
        timezone="UTC",
        status="confirmed",
    )

    try:
        asyncio.run(gateway.upsert_event(calendar_id="cal", event=event, external_event_id=None))
    except RuntimeError as exc:
        assert str(exc) == "google_calendar_credentials_path_required"
    else:  # pragma: no cover
        raise AssertionError("expected misconfigured gateway to raise")


def test_gateway_factory_enabled_with_credentials_path_returns_real_gateway_without_live_api_call() -> None:
    gateway = create_google_calendar_gateway(
        enabled=True,
        credentials_path="/tmp/fake-service-account.json",
        subject_email=None,
        application_name="DentFlow",
        timeout_sec=10.0,
    )
    assert isinstance(gateway, RealGoogleCalendarGateway)


def test_in_memory_gateway_upsert_and_cancel_contract() -> None:
    gateway = InMemoryGoogleCalendarGateway()
    event = CalendarEventPayload(
        title="Title",
        description="Description",
        starts_at_local=datetime.now(timezone.utc),
        ends_at_local=datetime.now(timezone.utc),
        timezone="UTC",
        status="confirmed",
    )
    event_id = asyncio.run(gateway.upsert_event(calendar_id="doc1", event=event, external_event_id=None))
    assert event_id
    assert ("doc1", event_id) in gateway.events

    asyncio.run(gateway.cancel_event(calendar_id="doc1", external_event_id=event_id))
    assert ("doc1", event_id) not in gateway.events


def test_runbook_mentions_process_and_retry_script_commands() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "python scripts/process_outbox_events.py --limit" in text
    assert "python scripts/retry_google_calendar_projection.py --limit" in text
    assert "python scripts/retry_google_calendar_projection.py --booking-id" in text


def test_docs_do_not_contain_positive_two_way_sync_claims() -> None:
    docs = [
        Path("docs/runbooks/google_calendar_projection_runbook.md"),
        Path("docs/80_integrations_and_infra.md"),
    ]
    joined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    assert "Calendar edits update DentFlow" not in joined

    for line in joined.splitlines():
        if "two-way sync" in line or "Calendar is source of truth" in line:
            assert any(token in line.lower() for token in ("forbidden", "non-goal", "no ", "not "))


def test_e1_matrix_correction_labels_non_acceptance_broad_run() -> None:
    matrix = Path("docs/p0-06e1-matrix.md").read_text(encoding="utf-8")
    assert "patient and booking (E1 acceptance command): **105 passed**" in matrix
    assert "343 passed, 5 failed" not in matrix or "broader non-E1 acceptance selection" in matrix
