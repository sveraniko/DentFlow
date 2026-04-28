from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from app.application.care_catalog_sync.parser import parse_catalog_workbook
from app.application.care_catalog_sync.service import CareCatalogSyncService
from scripts import sync_care_catalog


SEED_PATH = Path("seeds/care_catalog_demo.json")
REQUIRED_TABS = {
    "products",
    "product_i18n",
    "branch_availability",
    "recommendation_sets",
    "recommendation_set_items",
    "recommendation_links",
    "settings",
}


class InMemoryCatalogRepo:
    def __init__(self) -> None:
        self.branch_ids = {"branch_central"}
        self.products: dict[str, dict] = {}
        self.product_i18n: dict[tuple[str, str], dict] = {}
        self.availability: dict[tuple[str, str], dict] = {}
        self.sets: dict[str, dict] = {}
        self.set_items: dict[tuple[str, str], dict] = {}
        self.links: dict[tuple[str, str, str], dict] = {}
        self.settings: dict[str, str] = {}

    async def list_branch_ids(self, *, clinic_id: str) -> set[str]:
        return self.branch_ids

    async def upsert_catalog_product(self, *, clinic_id: str, row, now: datetime) -> str:
        prev = self.products.get(row.sku)
        payload = {"product_code": row.product_code, "status": row.status}
        self.products[row.sku] = payload
        return "added" if prev is None else ("updated" if prev != payload else "unchanged")

    async def upsert_catalog_product_i18n(self, *, clinic_id: str, row, now: datetime) -> str:
        key = (row.sku, row.locale)
        prev = self.product_i18n.get(key)
        payload = {"title": row.title, "description": row.description}
        self.product_i18n[key] = payload
        return "added" if prev is None else ("updated" if prev != payload else "unchanged")

    async def upsert_branch_availability_baseline(self, *, clinic_id: str, row, now: datetime) -> str:
        key = (row.branch_id, row.sku)
        prev = self.availability.get(key)
        payload = {"on_hand_qty": row.on_hand_qty, "enabled": row.availability_enabled, "preferred": row.preferred_pickup}
        self.availability[key] = payload
        return "added" if prev is None else ("updated" if prev != payload else "unchanged")

    async def upsert_recommendation_set(self, *, clinic_id: str, row, now: datetime) -> str:
        prev = self.sets.get(row.set_code)
        payload = {"status": row.status}
        self.sets[row.set_code] = payload
        return "added" if prev is None else ("updated" if prev != payload else "unchanged")

    async def upsert_recommendation_set_item(self, *, clinic_id: str, row, now: datetime) -> str:
        key = (row.set_code, row.sku)
        prev = self.set_items.get(key)
        payload = {"position": row.position, "quantity": row.quantity}
        self.set_items[key] = payload
        return "added" if prev is None else ("updated" if prev != payload else "unchanged")

    async def upsert_recommendation_link(self, *, clinic_id: str, row, now: datetime) -> str:
        key = (row.recommendation_type, row.target_kind, row.target_code)
        prev = self.links.get(key)
        payload = {"rank": row.relevance_rank, "active": row.active}
        self.links[key] = payload
        return "added" if prev is None else ("updated" if prev != payload else "unchanged")

    async def upsert_catalog_setting(self, *, clinic_id: str, key: str, value: str, now: datetime) -> str:
        prev = self.settings.get(key)
        self.settings[key] = value
        return "added" if prev is None else ("updated" if prev != value else "unchanged")


class _DummyRepo:
    def __init__(self, cfg) -> None:
        self.cfg = cfg


class _DummyService:
    def __init__(self, repo) -> None:
        self.repo = repo
        self.called: tuple[str, str, str] | None = None

    async def import_json(self, *, clinic_id: str, path: str):
        self.called = ("json", clinic_id, path)

        class _Result:
            source = "json"
            ok = True
            tabs_processed = ["products"]
            stats = {}
            warnings = []
            validation_errors = []
            fatal_errors = []

        return _Result()


def _dummy_database_config():
    return object()


def _load_seed() -> dict[str, list[dict[str, object]]]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def test_json_structure_and_parse() -> None:
    payload = _load_seed()
    assert REQUIRED_TABS.issubset(payload.keys())

    parsed, result = parse_catalog_workbook(
        workbook=payload,
        known_branch_ids={"branch_central"},
        source="json",
    )

    assert parsed is not None
    assert result.fatal_errors == []
    assert result.validation_errors == []


def test_product_readiness() -> None:
    payload = _load_seed()
    products = payload["products"]

    assert len(products) >= 6
    active_products = [row for row in products if row["status"] == "active"]
    assert len(active_products) >= 6

    categories = {row["category"] for row in products}
    assert {"toothbrush", "toothpaste", "floss", "rinse", "irrigator"}.issubset(categories)
    assert "remineralization" in categories or "sensitivity" in categories

    active_skus = {row["sku"] for row in active_products}
    locales_by_sku: dict[str, set[str]] = {}
    for row in payload["product_i18n"]:
        locales_by_sku.setdefault(row["sku"], set()).add(str(row["locale"]).lower())

    for sku in active_skus:
        assert {"ru", "en"}.issubset(locales_by_sku.get(sku, set()))

    for row in active_products:
        assert row.get("price_amount")
        assert row.get("currency_code")

    skus = [row["sku"] for row in products]
    assert len(skus) == len(set(skus))
    codes = [row["product_code"] for row in products]
    assert len(codes) == len(set(codes))


def test_branch_availability_readiness() -> None:
    payload = _load_seed()
    products = {row["sku"] for row in payload["products"]}
    availability = payload["branch_availability"]

    assert availability
    for row in availability:
        assert row["sku"] in products
        assert row["branch_id"] == "branch_central"

    in_stock = sum(1 for row in availability if int(row["on_hand_qty"]) > 0)
    out_stock = sum(1 for row in availability if int(row["on_hand_qty"]) == 0)
    low_stock = sum(
        1
        for row in availability
        if int(row["on_hand_qty"]) > 0 and int(row["on_hand_qty"]) <= int(row["low_stock_threshold"])
    )

    assert in_stock >= 4
    assert out_stock >= 1
    assert low_stock >= 1
    assert any(bool(row["preferred_pickup"]) for row in availability)


def test_recommendation_mapping_readiness() -> None:
    payload = _load_seed()
    products = {row["sku"] for row in payload["products"]}
    set_codes = {row["set_code"] for row in payload["recommendation_sets"]}

    assert len(payload["recommendation_sets"]) >= 2
    assert len(payload["recommendation_set_items"]) >= 2
    assert len(payload["recommendation_links"]) >= 4

    for row in payload["recommendation_set_items"]:
        assert row["sku"] in products
        assert row["set_code"] in set_codes

    for row in payload["recommendation_links"]:
        if row["target_kind"] == "product":
            assert row["target_code"] in products
        if row["target_kind"] == "set":
            assert row["target_code"] in set_codes

    link_types = {row["recommendation_type"] for row in payload["recommendation_links"]}
    assert {"aftercare_hygiene", "sensitivity", "post_treatment", "gum_care"}.issubset(link_types)


def test_settings_include_default_pickup_branch() -> None:
    payload = _load_seed()
    settings = {row["key"]: row["value"] for row in payload["settings"]}
    assert settings["care.default_pickup_branch_id"] == "branch_central"


def test_sync_service_json_import() -> None:
    repo = InMemoryCatalogRepo()
    service = CareCatalogSyncService(repo)

    result = asyncio.run(service.import_json(clinic_id="clinic_main", path=SEED_PATH))

    assert result.ok
    assert len(repo.products) == 7
    assert len(repo.product_i18n) == 12
    assert len(repo.availability) == 6
    assert len(repo.sets) == 2
    assert len(repo.set_items) == 6
    assert len(repo.links) == 4
    assert len(repo.settings) == 3


def test_cli_run_json_mode(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _BoundService(_DummyService):
        async def import_json(self, *, clinic_id: str, path: str):
            captured["clinic_id"] = clinic_id
            captured["path"] = path
            return await super().import_json(clinic_id=clinic_id, path=path)

    monkeypatch.setattr(sync_care_catalog, "DbCareCommerceRepository", _DummyRepo)
    monkeypatch.setattr(sync_care_catalog, "CareCatalogSyncService", _BoundService)
    monkeypatch.setattr(sync_care_catalog, "DatabaseConfig", _dummy_database_config)

    args = argparse.Namespace(mode="json", clinic_id="clinic_main", path="seeds/care_catalog_demo.json")
    exit_code = asyncio.run(sync_care_catalog._run(args))

    assert exit_code == 0
    assert captured == {"clinic_id": "clinic_main", "path": "seeds/care_catalog_demo.json"}
