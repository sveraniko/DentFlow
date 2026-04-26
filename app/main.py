import asyncio
import logging
from collections.abc import Mapping

from aiogram import Bot

from app.bootstrap.logging import configure_logging
from app.bootstrap.runtime import RuntimeRegistry
from app.config.settings import Settings, get_settings

SUPPORTED_RUN_MODES = {"bootstrap", "polling"}
_PLACEHOLDER_TOKEN_VALUES = {"", "replace_me", "changeme", "placeholder"}


def _is_missing_value(value: str | None) -> bool:
    candidate = (value or "").strip()
    return candidate.lower() in _PLACEHOLDER_TOKEN_VALUES


def validate_launch_settings(settings: Settings, mode: str) -> None:
    errors: list[str] = []

    if mode not in SUPPORTED_RUN_MODES:
        errors.append(f"unsupported APP_RUN_MODE '{mode}' (expected bootstrap or polling)")

    if _is_missing_value(settings.db.dsn):
        errors.append("DB_DSN is required")
    if _is_missing_value(settings.redis.url):
        errors.append("REDIS_URL is required")
    if _is_missing_value(settings.app.default_locale):
        errors.append("APP_DEFAULT_LOCALE is required")
    if _is_missing_value(settings.app.default_timezone):
        errors.append("APP_DEFAULT_TIMEZONE is required")

    if mode == "polling":
        role_tokens: Mapping[str, str] = {
            "patient": settings.telegram.patient_bot_token,
            "clinic_admin": settings.telegram.clinic_admin_bot_token,
            "doctor": settings.telegram.doctor_bot_token,
            "owner": settings.telegram.owner_bot_token,
        }
        for role, token in role_tokens.items():
            if _is_missing_value(token):
                errors.append(f"TELEGRAM_{role.upper()}_BOT_TOKEN must be configured for polling mode")

    if errors:
        raise RuntimeError("launch settings validation failed: " + "; ".join(errors))


def _build_bots(settings: Settings) -> dict[str, Bot]:
    return {
        "patient": Bot(token=settings.telegram.patient_bot_token),
        "clinic_admin": Bot(token=settings.telegram.clinic_admin_bot_token),
        "doctor": Bot(token=settings.telegram.doctor_bot_token),
        "owner": Bot(token=settings.telegram.owner_bot_token),
    }


async def _run_polling(runtime: RuntimeRegistry, settings: Settings, logger: logging.Logger) -> None:
    bots_by_role = _build_bots(settings)
    logger.info("Polling mode starting", extra={"extra": {"configured_bot_roles": sorted(bots_by_role.keys())}})
    try:
        await runtime.build_dispatcher().start_polling(*bots_by_role.values())
    finally:
        await asyncio.gather(*(bot.session.close() for bot in bots_by_role.values()), return_exceptions=True)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.logging)
    logger = logging.getLogger("dentflow.main")

    mode = settings.app.run_mode.strip().lower()
    logger.info("DentFlow runtime startup selected", extra={"extra": {"run_mode": mode}})

    validate_launch_settings(settings, mode)

    runtime = RuntimeRegistry(settings)
    runtime.build_dispatcher()

    if mode == "bootstrap":
        logger.info("DentFlow runtime skeleton ready")
        return

    logger.info("DentFlow polling runtime ready")
    asyncio.run(_run_polling(runtime, settings, logger))


if __name__ == "__main__":
    main()
