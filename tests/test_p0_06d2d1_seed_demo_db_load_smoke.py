from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timezone
from urllib.parse import urlparse

import pytest
from sqlalchemy import text

from app.config.settings import DatabaseConfig
from app.infrastructure.db.bootstrap import SCHEMAS, bootstrap_database
from app.infrastructure.db.engine import create_engine
from scripts import seed_demo

TEST_DB_DSN_ENV = "DENTFLOW_TEST_DB_DSN"


def _safe_test_db_config() -> DatabaseConfig:
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


async def _reset_test_db(db_config: DatabaseConfig) -> None:
    engine = create_engine(db_config)
    try:
        async with engine.begin() as conn:
            for schema in SCHEMAS:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await bootstrap_database(db_config)
    finally:
        await engine.dispose()


async def _count(conn, sql: str) -> int:
    return int((await conn.execute(text(sql))).scalar_one())


async def _seed_and_collect_counts(db_config: DatabaseConfig) -> tuple[dict[str, object], dict[str, int]]:
    stage_counts = await seed_demo.run_seed_demo_bootstrap(
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

    engine = create_engine(db_config)
    try:
        async with engine.begin() as conn:
            counts = {
                "clinics": await _count(conn, "SELECT COUNT(*) FROM core_reference.clinics"),
                "branches": await _count(conn, "SELECT COUNT(*) FROM core_reference.branches"),
                "doctors": await _count(conn, "SELECT COUNT(*) FROM core_reference.doctors"),
                "services": await _count(conn, "SELECT COUNT(*) FROM core_reference.services"),
                "doctor_access_codes": await _count(conn, "SELECT COUNT(*) FROM core_reference.doctor_access_codes"),
                "patients": await _count(conn, "SELECT COUNT(*) FROM core_patient.patients"),
                "phone_contacts": await _count(conn, "SELECT COUNT(*) FROM core_patient.patient_contacts WHERE contact_type='phone'"),
                "telegram_contacts": await _count(conn, "SELECT COUNT(*) FROM core_patient.patient_contacts WHERE contact_type='telegram'"),
                "availability_slots": await _count(conn, "SELECT COUNT(*) FROM booking.availability_slots"),
                "future_slots": await _count(conn, "SELECT COUNT(*) FROM booking.availability_slots WHERE start_at > TIMESTAMPTZ '2026-04-28T00:00:00+00:00'"),
                "bookings": await _count(conn, "SELECT COUNT(*) FROM booking.bookings"),
                "waitlist_entries": await _count(conn, "SELECT COUNT(*) FROM booking.waitlist_entries"),
                "products": await _count(conn, "SELECT COUNT(*) FROM care_commerce.products"),
                "active_products": await _count(conn, "SELECT COUNT(*) FROM care_commerce.products WHERE status='active'"),
                "product_i18n": await _count(conn, "SELECT COUNT(*) FROM care_commerce.product_i18n"),
                "branch_availability": await _count(conn, "SELECT COUNT(*) FROM care_commerce.branch_product_availability"),
                "recommendation_sets": await _count(conn, "SELECT COUNT(*) FROM care_commerce.recommendation_sets"),
                "recommendation_links": await _count(conn, "SELECT COUNT(*) FROM care_commerce.recommendation_links"),
                "recommendations": await _count(conn, "SELECT COUNT(*) FROM recommendation.recommendations"),
                "care_orders": await _count(conn, "SELECT COUNT(*) FROM care_commerce.care_orders"),
                "care_order_items": await _count(conn, "SELECT COUNT(*) FROM care_commerce.care_order_items"),
                "care_reservations": await _count(conn, "SELECT COUNT(*) FROM care_commerce.care_reservations"),
            }

            booking_statuses = set((await conn.execute(text("SELECT DISTINCT status FROM booking.bookings"))).scalars())
            recommendation_statuses = set((await conn.execute(text("SELECT DISTINCT status FROM recommendation.recommendations"))).scalars())
            care_order_statuses = set((await conn.execute(text("SELECT DISTINCT status FROM care_commerce.care_orders"))).scalars())

            assert int(
                (await conn.execute(text("SELECT COUNT(*) FROM core_patient.patient_contacts WHERE contact_type='telegram' AND normalized_value='3001'"))).scalar_one()
            ) == 1
            assert int((await conn.execute(text("SELECT COUNT(*) FROM care_commerce.branch_product_availability WHERE available_qty > 0"))).scalar_one()) >= 1
            assert int((await conn.execute(text("SELECT COUNT(*) FROM care_commerce.branch_product_availability WHERE available_qty = 0"))).scalar_one()) >= 1
            assert int(
                (await conn.execute(text("SELECT COUNT(*) FROM care_commerce.catalog_settings WHERE key='care.default_pickup_branch_id' AND value='branch_central'"))).scalar_one()
            ) == 1
            assert int((await conn.execute(text("SELECT COUNT(*) FROM recommendation.recommendations WHERE patient_id='patient_sergey_ivanov'"))).scalar_one()) >= 1
            assert int((await conn.execute(text("SELECT COUNT(*) FROM recommendation.recommendation_manual_targets WHERE recommendation_id='rec_sergey_manual_invalid' AND target_code='SKU-NOT-EXISTS'"))).scalar_one()) == 1
            assert int((await conn.execute(text("SELECT COUNT(*) FROM care_commerce.care_orders WHERE patient_id='patient_sergey_ivanov' AND status IN ('confirmed','ready_for_pickup')"))).scalar_one()) >= 1

            assert int(
                (await conn.execute(text("SELECT COUNT(*) FROM booking.bookings b LEFT JOIN core_patient.patients p ON p.patient_id=b.patient_id WHERE p.patient_id IS NULL"))).scalar_one()
            ) == 0
            assert int(
                (await conn.execute(text("SELECT COUNT(*) FROM booking.bookings b LEFT JOIN core_reference.doctors d ON d.doctor_id=b.doctor_id WHERE d.doctor_id IS NULL"))).scalar_one()
            ) == 0
            assert int(
                (await conn.execute(text("SELECT COUNT(*) FROM booking.bookings b LEFT JOIN core_reference.services s ON s.service_id=b.service_id WHERE s.service_id IS NULL"))).scalar_one()
            ) == 0
            assert int(
                (await conn.execute(text("SELECT COUNT(*) FROM care_commerce.care_orders o LEFT JOIN core_patient.patients p ON p.patient_id=o.patient_id WHERE p.patient_id IS NULL"))).scalar_one()
            ) == 0
            assert int(
                (await conn.execute(text("SELECT COUNT(*) FROM care_commerce.care_order_items i LEFT JOIN care_commerce.products p ON p.care_product_id=i.care_product_id WHERE p.care_product_id IS NULL"))).scalar_one()
            ) == 0
            assert int(
                (await conn.execute(text("SELECT COUNT(*) FROM care_commerce.recommendation_product_links l LEFT JOIN care_commerce.products p ON p.care_product_id=l.care_product_id WHERE p.care_product_id IS NULL"))).scalar_one()
            ) == 0

            assert int((await conn.execute(text("SELECT COUNT(*) FROM booking.waitlist_entries WHERE requested_date >= DATE '2026-04-28'"))).scalar_one()) >= 1
            assert int((await conn.execute(text("SELECT COUNT(*) FROM booking.bookings WHERE status IN ('pending_confirmation','confirmed','reschedule_requested') AND scheduled_start_at >= TIMESTAMPTZ '2026-04-28T00:00:00+00:00'"))).scalar_one()) >= 3
            assert int((await conn.execute(text("SELECT COUNT(*) FROM care_commerce.care_reservations WHERE status='active' AND expires_at > TIMESTAMPTZ '2026-04-28T00:00:00+00:00'"))).scalar_one()) >= 1
            assert int((await conn.execute(text("SELECT COUNT(*) FROM recommendation.recommendations WHERE issued_at IS NOT NULL AND (viewed_at IS NULL OR viewed_at >= issued_at)"))).scalar_one()) >= 1

            assert booking_statuses >= {"pending_confirmation", "confirmed", "reschedule_requested", "canceled"}
            assert recommendation_statuses >= {"issued", "viewed", "acknowledged", "accepted", "declined", "expired"}
            assert care_order_statuses & {"canceled", "expired"}
            assert care_order_statuses >= {"confirmed", "ready_for_pickup", "fulfilled"}

    finally:
        await engine.dispose()

    return stage_counts, counts


def test_full_seed_load_and_idempotency_in_safe_db() -> None:
    db_config = _safe_test_db_config()

    async def _run() -> None:
        await _reset_test_db(db_config)
        stage_counts, first_counts = await _seed_and_collect_counts(db_config)

        assert set(stage_counts) == {"stack1", "stack2", "stack3", "care_catalog", "recommendations_care_orders"}
        assert first_counts["clinics"] >= 1
        assert first_counts["branches"] >= 1
        assert first_counts["doctors"] >= 3
        assert first_counts["services"] >= 4
        assert first_counts["doctor_access_codes"] >= 3
        assert first_counts["patients"] >= 4
        assert first_counts["phone_contacts"] >= 2
        assert first_counts["telegram_contacts"] >= 2
        assert first_counts["availability_slots"] >= 12
        assert first_counts["future_slots"] >= 12
        assert first_counts["bookings"] >= 4
        assert first_counts["waitlist_entries"] >= 1
        assert first_counts["products"] >= 6
        assert first_counts["active_products"] >= 5
        assert first_counts["product_i18n"] >= 10
        assert first_counts["branch_availability"] >= 5
        assert first_counts["recommendation_sets"] >= 2
        assert first_counts["recommendation_links"] >= 4
        assert first_counts["recommendations"] >= 7
        assert first_counts["care_orders"] >= 4
        assert first_counts["care_order_items"] >= 4
        assert first_counts["care_reservations"] >= 4

        _, second_counts = await _seed_and_collect_counts(db_config)
        assert second_counts == first_counts

        engine = create_engine(db_config)
        try:
            async with engine.begin() as conn:
                uniqueness = {
                    "doctor_id": "SELECT COUNT(*)=COUNT(DISTINCT doctor_id) FROM core_reference.doctors",
                    "service_id": "SELECT COUNT(*)=COUNT(DISTINCT service_id) FROM core_reference.services",
                    "patient_id": "SELECT COUNT(*)=COUNT(DISTINCT patient_id) FROM core_patient.patients",
                    "booking_id": "SELECT COUNT(*)=COUNT(DISTINCT booking_id) FROM booking.bookings",
                    "slot_id": "SELECT COUNT(*)=COUNT(DISTINCT slot_id) FROM booking.availability_slots",
                    "product_sku": "SELECT COUNT(*)=COUNT(DISTINCT sku) FROM care_commerce.products",
                    "recommendation_id": "SELECT COUNT(*)=COUNT(DISTINCT recommendation_id) FROM recommendation.recommendations",
                    "care_order_id": "SELECT COUNT(*)=COUNT(DISTINCT care_order_id) FROM care_commerce.care_orders",
                }
                for sql in uniqueness.values():
                    assert bool((await conn.execute(text(sql))).scalar_one())
        finally:
            await engine.dispose()

    asyncio.run(_run())


def test_dry_run_still_no_db_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"actual": False}

    async def _should_not_run(*_args, **_kwargs):
        called["actual"] = True
        return {}

    monkeypatch.setattr(seed_demo, "run_seed_demo_bootstrap", _should_not_run)
    exit_code = seed_demo.main(["--dry-run", "--relative-dates"])  # no DB needed
    assert exit_code == 0
    assert called["actual"] is False


def test_skip_flags_in_actual_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def _fake_stack1(_db, _path):
        calls.append("stack1")
        return {"clinics": 1}

    async def _fake_stack2(_db, _payload):
        calls.append("stack2")
        return {"patients": 1}

    async def _fake_stack3(_db, _path, **_kwargs):
        calls.append("stack3")
        return {"bookings": 1}

    async def _fake_rec(_db, _path, **_kwargs):
        calls.append("recommendations")
        return {"recommendations": 1}

    class _FakeService:
        def __init__(self, _repo):
            pass

        async def import_json(self, *, clinic_id, path):
            calls.append("care")
            return type("R", (), {"ok": True, "tabs_processed": ["products"], "warnings": [], "validation_errors": [], "fatal_errors": []})()

    monkeypatch.setattr(seed_demo, "seed_stack_data", _fake_stack1)
    monkeypatch.setattr(seed_demo, "seed_stack2_patients", _fake_stack2)
    monkeypatch.setattr(seed_demo, "seed_stack3_booking", _fake_stack3)
    monkeypatch.setattr(seed_demo, "seed_demo_recommendations_care_orders", _fake_rec)
    monkeypatch.setattr(seed_demo, "DbCareCommerceRepository", lambda _db: object())
    monkeypatch.setattr(seed_demo, "CareCatalogSyncService", _FakeService)

    async def _run() -> None:
        counts = await seed_demo.run_seed_demo_bootstrap(
            object(),
            clinic_id="clinic_main",
            relative_dates=False,
            start_offset_days=1,
            source_anchor_date=None,
            stack1_path=seed_demo.Path("seeds/stack1_seed.json"),
            stack2_path=seed_demo.Path("seeds/stack2_patients.json"),
            stack3_path=seed_demo.Path("seeds/stack3_booking.json"),
            care_catalog_path=seed_demo.Path("seeds/care_catalog_demo.json"),
            recommendations_care_orders_path=seed_demo.Path("seeds/demo_recommendations_care_orders.json"),
            skip_care=True,
            skip_recommendations=True,
        )
        assert counts["care_catalog"] == {"skipped": True}
        assert counts["recommendations_care_orders"] == {"skipped": True}

    asyncio.run(_run())
    assert calls == ["stack1", "stack2", "stack3"]
