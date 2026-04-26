from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("aiogram")
pytest.importorskip("pydantic")
pytest.importorskip("pydantic_settings")

from app.config.settings import Settings


def _valid_settings() -> Settings:
    return Settings.model_validate(
        {
            "app": {
                "default_locale": "ru",
                "default_timezone": "UTC",
                "run_mode": "bootstrap",
            },
            "telegram": {
                "patient_bot_token": "patient-token",
                "clinic_admin_bot_token": "admin-token",
                "doctor_bot_token": "doctor-token",
                "owner_bot_token": "owner-token",
            },
            "db": {"dsn": "postgresql+asyncpg://user:pass@localhost:5432/db", "echo": False},
            "redis": {"url": "redis://localhost:6379/0"},
        }
    )


def test_importing_app_main_does_not_start_polling(monkeypatch: pytest.MonkeyPatch, required_env: None) -> None:
    calls: list[str] = []

    async def _should_not_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        calls.append("start_polling")

    monkeypatch.setattr("aiogram.Dispatcher.start_polling", _should_not_run)
    sys.modules.pop("app.main", None)
    importlib.import_module("app.main")
    assert calls == []


def test_bootstrap_mode_builds_dispatcher_without_polling(monkeypatch: pytest.MonkeyPatch, required_env: None) -> None:
    import app.main as main_module

    calls: list[str] = []

    class _FakeRuntime:
        def __init__(self, _settings):
            calls.append("runtime_init")

        def build_dispatcher(self):
            calls.append("build_dispatcher")
            return SimpleNamespace()

    monkeypatch.setattr(main_module, "get_settings", lambda: _valid_settings())
    monkeypatch.setattr(main_module, "configure_logging", lambda _cfg: calls.append("configure_logging"))
    monkeypatch.setattr(main_module, "RuntimeRegistry", _FakeRuntime)
    monkeypatch.setattr(main_module.asyncio, "run", lambda _coro: calls.append("asyncio_run"))

    main_module.main()

    assert calls == ["configure_logging", "runtime_init", "build_dispatcher"]


def test_polling_mode_rejects_placeholder_tokens(required_env: None) -> None:
    import app.main as main_module

    settings = _valid_settings()
    settings.app.run_mode = "polling"
    settings.telegram.owner_bot_token = "replace_me"

    with pytest.raises(RuntimeError, match="TELEGRAM_OWNER_BOT_TOKEN"):
        main_module.validate_launch_settings(settings, settings.app.run_mode)


def test_launch_validation_does_not_print_token_values(required_env: None) -> None:
    import app.main as main_module

    secret_token = "ultra-secret-owner-token"
    settings = _valid_settings()
    settings.app.run_mode = "polling"
    settings.telegram.owner_bot_token = secret_token
    settings.telegram.patient_bot_token = "replace_me"

    with pytest.raises(RuntimeError) as exc:
        main_module.validate_launch_settings(settings, settings.app.run_mode)

    message = str(exc.value)
    assert "TELEGRAM_PATIENT_BOT_TOKEN" in message
    assert secret_token not in message


def test_unsupported_run_mode_fails_clearly(required_env: None) -> None:
    import app.main as main_module

    settings = _valid_settings()
    with pytest.raises(RuntimeError, match="unsupported APP_RUN_MODE"):
        main_module.validate_launch_settings(settings, "invalid_mode")


def test_env_example_contains_launch_worker_and_integration_keys() -> None:
    env_text = Path(".env.example").read_text(encoding="utf-8")
    expected_keys = [
        "APP_DEFAULT_TIMEZONE",
        "APP_RUN_MODE",
        "INTEGRATIONS_GOOGLE_CALENDAR_ENABLED",
        "INTEGRATIONS_GOOGLE_CALENDAR_CREDENTIALS_PATH",
        "INTEGRATIONS_GOOGLE_CALENDAR_SUBJECT_EMAIL",
        "INTEGRATIONS_GOOGLE_CALENDAR_APPLICATION_NAME",
        "INTEGRATIONS_GOOGLE_CALENDAR_TIMEOUT_SEC",
        "INTEGRATIONS_DENTFLOW_BASE_URL",
        "PROJECTOR_WORKER_ENABLED",
        "PROJECTOR_WORKER_BATCH_LIMIT",
        "PROJECTOR_WORKER_POLL_INTERVAL_SEC",
        "REMINDER_WORKER_DELIVERY_BATCH_LIMIT",
        "REMINDER_WORKER_RECOVERY_BATCH_LIMIT",
        "REMINDER_WORKER_POLL_INTERVAL_SEC",
        "REMINDER_WORKER_LEASE_TTL_SEC",
        "WORKER_MODE",
    ]
    for key in expected_keys:
        assert f"{key}=" in env_text


def test_makefile_contains_launch_targets() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    expected_targets = [
        "run-bootstrap:",
        "run-bots:",
        "run-worker-projector:",
        "run-worker-reminder:",
        "run-worker-all:",
    ]
    for target in expected_targets:
        assert target in makefile_text


def test_no_migrations_introduced() -> None:
    assert not Path("migrations").exists()
    assert not Path("alembic.ini").exists()
