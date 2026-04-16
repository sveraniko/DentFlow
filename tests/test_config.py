import pytest

pytest.importorskip("pydantic")
pytest.importorskip("pydantic_settings")

from app.config.settings import Settings


def test_settings_loads(required_env) -> None:
    settings = Settings()
    assert settings.app.default_locale == "ru"
    assert settings.telegram.patient_bot_token == "test"
    assert settings.db.dsn.startswith("postgresql+asyncpg://")


def test_logging_config_uses_json_logs(required_env) -> None:
    settings = Settings()
    assert hasattr(settings.logging, "json_logs")
