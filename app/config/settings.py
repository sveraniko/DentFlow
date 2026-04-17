from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore")

    name: str = "DentFlow"
    env: str = "dev"
    default_locale: str = "ru"


class TelegramConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TELEGRAM_", extra="ignore")

    patient_bot_token: str = Field(...)
    clinic_admin_bot_token: str = Field(...)
    doctor_bot_token: str = Field(...)
    owner_bot_token: str = Field(...)


class DatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_", extra="ignore")

    dsn: str = Field(..., description="Async SQLAlchemy DSN, e.g. postgresql+asyncpg://...")
    echo: bool = False


class RedisConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore")

    url: str = "redis://localhost:6379/0"


class SearchConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEARCH_", extra="ignore")

    enabled: bool = False
    meili_endpoint: str = "http://localhost:7700"
    meili_api_key: str | None = None
    meili_index_prefix: str = "dentflow"
    meili_timeout_sec: float = 2.0
    meili_batch_size: int = 500


class StorageConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STORAGE_", extra="ignore")

    bucket: str = "dentflow-local"
    endpoint: str = "http://localhost:9000"


class AIConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_", extra="ignore")

    provider: str = "disabled"
    enabled: bool = False


class IntegrationsConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INTEGRATIONS_", extra="ignore")

    google_sheets_enabled: bool = False


class LoggingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LOGGING_", extra="ignore")

    level: str = "INFO"
    json_logs: bool = False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app: AppConfig = Field(default_factory=AppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
