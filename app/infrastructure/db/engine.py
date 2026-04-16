from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config.settings import DatabaseConfig


def create_engine(config: DatabaseConfig) -> AsyncEngine:
    return create_async_engine(config.dsn, echo=config.echo, future=True)
