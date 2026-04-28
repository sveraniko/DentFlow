from __future__ import annotations

import os
from datetime import date
from urllib.parse import urlparse

import pytest
from sqlalchemy import text

from app.config.settings import DatabaseConfig
from app.infrastructure.db.bootstrap import SCHEMAS, bootstrap_database
from app.infrastructure.db.engine import create_engine
from scripts import seed_demo

TEST_DB_DSN_ENV = "DENTFLOW_TEST_DB_DSN"


def safe_test_db_config() -> DatabaseConfig:
    dsn = os.getenv(TEST_DB_DSN_ENV)
    if not dsn:
        pytest.skip(f"Set {TEST_DB_DSN_ENV} to run DB smoke test")
    parsed = urlparse(dsn.replace("postgresql+asyncpg://", "postgresql://"))
    db_name = (parsed.path or "").lstrip("/").lower()
    host = (parsed.hostname or "").lower()
    if not db_name or not any(tag in db_name for tag in ("test", "sandbox", "tmp")):
        pytest.fail(f"Unsafe test database name: '{db_name}' from {TEST_DB_DSN_ENV}")
    if host not in {"localhost", "127.0.0.1"}:
        pytest.fail(f"Unsafe test database host: '{host}' from {TEST_DB_DSN_ENV}")
    return DatabaseConfig(dsn=dsn, echo=False)


async def reset_test_db(db_config: DatabaseConfig) -> None:
    engine = create_engine(db_config)
    try:
        async with engine.begin() as conn:
            for schema in SCHEMAS:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await bootstrap_database(db_config)
    finally:
        await engine.dispose()


async def run_seed_demo_bootstrap_for_tests(db_config: DatabaseConfig) -> dict[str, object]:
    return await seed_demo.run_seed_demo_bootstrap(
        db_config,
        clinic_id="clinic_main",
        relative_dates=True,
        start_offset_days=1,
        source_anchor_date=date(2026, 4, 20),
        stack1_path=seed_demo.Path("seeds/stack1_seed.json"),
        stack2_path=seed_demo.Path("seeds/stack2_patients.json"),
        stack3_path=seed_demo.Path("seeds/stack3_booking.json"),
        care_catalog_path=seed_demo.Path("seeds/care_catalog_demo.json"),
        recommendations_care_orders_path=seed_demo.Path("seeds/demo_recommendations_care_orders.json"),
    )
