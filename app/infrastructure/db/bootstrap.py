import logging

from sqlalchemy import text

from app.infrastructure.db.engine import create_engine

SCHEMAS: tuple[str, ...] = (
    "core_reference",
    "access_identity",
    "policy_config",
    "core_patient",
    "booking",
    "communication",
    "clinical",
    "care_commerce",
    "media_docs",
    "integration",
    "analytics_raw",
    "owner_views",
    "platform",
)


async def bootstrap_database(db_config) -> None:
    logger = logging.getLogger("dentflow.db.bootstrap")
    engine = create_engine(db_config)
    async with engine.begin() as conn:
        for schema in SCHEMAS:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            logger.info("schema ensured", extra={"extra": {"schema": schema}})
    await engine.dispose()
