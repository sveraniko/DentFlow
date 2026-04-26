"""Bounded smoke check: load settings and print a safe launch summary."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
from urllib.parse import urlsplit

from app.config.settings import Settings, get_settings

_PLACEHOLDER_VALUES = {"", "replace_me", "changeme", "placeholder"}


def _is_placeholder(value: str | None) -> bool:
    return (value or "").strip().lower() in _PLACEHOLDER_VALUES


def _sanitize_url(value: str | None) -> str:
    if not value or _is_placeholder(value):
        return "missing"
    parsed = urlsplit(value)
    host = parsed.hostname or "unknown-host"
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or ""
    return f"{parsed.scheme}://***@{host}{port}{path}"


def _token_configured(value: str | None) -> str:
    return "yes" if not _is_placeholder(value) else "no"


def _validate_launch_critical(settings: Settings) -> list[str]:
    errors: list[str] = []
    if _is_placeholder(settings.db.dsn):
        errors.append("DB_DSN is required")
    if _is_placeholder(settings.redis.url):
        errors.append("REDIS_URL is required")
    mode = settings.app.run_mode.strip().lower()
    if mode == "polling":
        token_fields = {
            "TELEGRAM_PATIENT_BOT_TOKEN": settings.telegram.patient_bot_token,
            "TELEGRAM_CLINIC_ADMIN_BOT_TOKEN": settings.telegram.clinic_admin_bot_token,
            "TELEGRAM_DOCTOR_BOT_TOKEN": settings.telegram.doctor_bot_token,
            "TELEGRAM_OWNER_BOT_TOKEN": settings.telegram.owner_bot_token,
        }
        for key, value in token_fields.items():
            if _is_placeholder(value):
                errors.append(f"{key} must be configured for APP_RUN_MODE=polling")
    return errors


def main() -> int:
    try:
        settings = get_settings()
    except Exception as exc:
        print("SMOKE_SETTINGS FAIL")
        print(f"- {exc.__class__.__name__}: {exc}")
        return 1

    print("SMOKE_SETTINGS SUMMARY")
    print(f"- app_env={settings.app.env}")
    print(f"- locale={settings.app.default_locale} timezone={settings.app.default_timezone}")
    print(f"- db_dsn_present={'yes' if not _is_placeholder(settings.db.dsn) else 'no'} dsn={_sanitize_url(settings.db.dsn)}")
    print(f"- redis_present={'yes' if not _is_placeholder(settings.redis.url) else 'no'} redis={_sanitize_url(settings.redis.url)}")
    print(
        "- telegram_tokens_configured "
        f"patient={_token_configured(settings.telegram.patient_bot_token)} "
        f"clinic_admin={_token_configured(settings.telegram.clinic_admin_bot_token)} "
        f"doctor={_token_configured(settings.telegram.doctor_bot_token)} "
        f"owner={_token_configured(settings.telegram.owner_bot_token)}"
    )
    print(
        "- integrations "
        f"google_calendar_enabled={settings.integrations.google_calendar_enabled} "
        f"google_sheets_enabled={settings.integrations.google_sheets_enabled}"
    )
    print(f"- worker_mode={os.getenv('WORKER_MODE', 'projector').strip().lower()}")

    errors = _validate_launch_critical(settings)
    if errors:
        print("SMOKE_SETTINGS FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("SMOKE_SETTINGS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
