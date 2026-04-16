import pytest


@pytest.fixture
def required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_PATIENT_BOT_TOKEN", "test")
    monkeypatch.setenv("TELEGRAM_CLINIC_ADMIN_BOT_TOKEN", "test")
    monkeypatch.setenv("TELEGRAM_DOCTOR_BOT_TOKEN", "test")
    monkeypatch.setenv("TELEGRAM_OWNER_BOT_TOKEN", "test")
    monkeypatch.setenv("DB_DSN", "postgresql+asyncpg://user:pass@localhost:5432/db")
