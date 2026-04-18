from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.application.care_catalog_sync.parser import parse_catalog_workbook
from app.application.care_catalog_sync.service import CareCatalogSyncService


class InMemoryCatalogRepo:
    def __init__(self) -> None:
        self.branch_ids = {"br1"}
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
        payload = {"product_code": row.product_code, "status": row.status, "price_amount": int(row.price_amount * 100)}
        self.products[row.sku] = payload
        if prev is None:
            return "added"
        return "updated" if prev != payload else "unchanged"

    async def upsert_catalog_product_i18n(self, *, clinic_id: str, row, now: datetime) -> str:
        key = (row.sku, row.locale)
        prev = self.product_i18n.get(key)
        payload = {"title": row.title}
        self.product_i18n[key] = payload
        if prev is None:
            return "added"
        return "updated" if prev != payload else "unchanged"

    async def upsert_branch_availability_baseline(self, *, clinic_id: str, row, now: datetime) -> str:
        key = (row.branch_id, row.sku)
        prev = self.availability.get(key)
        reserved_qty = prev["reserved_qty"] if prev else 3
        payload = {"on_hand_qty": row.on_hand_qty, "reserved_qty": reserved_qty, "status": ("active" if row.availability_enabled else "inactive")}
        self.availability[key] = payload
        if prev is None:
            return "added"
        return "updated" if prev != payload else "unchanged"

    async def upsert_recommendation_set(self, *, clinic_id: str, row, now: datetime) -> str:
        prev = self.sets.get(row.set_code)
        payload = {"status": row.status}
        self.sets[row.set_code] = payload
        if prev is None:
            return "added"
        return "updated" if prev != payload else "unchanged"

    async def upsert_recommendation_set_item(self, *, clinic_id: str, row, now: datetime) -> str:
        key = (row.set_code, row.sku)
        prev = self.set_items.get(key)
        payload = {"position": row.position, "quantity": row.quantity}
        self.set_items[key] = payload
        if prev is None:
            return "added"
        return "updated" if prev != payload else "unchanged"

    async def upsert_recommendation_link(self, *, clinic_id: str, row, now: datetime) -> str:
        key = (row.recommendation_type, row.target_kind, row.target_code)
        prev = self.links.get(key)
        payload = {"rank": row.relevance_rank, "active": row.active}
        self.links[key] = payload
        if prev is None:
            return "added"
        return "updated" if prev != payload else "unchanged"

    async def upsert_catalog_setting(self, *, clinic_id: str, key: str, value: str, now: datetime) -> str:
        prev = self.settings.get(key)
        self.settings[key] = value
        if prev is None:
            return "added"
        return "updated" if prev != value else "unchanged"


def _valid_workbook() -> dict[str, list[dict[str, object]]]:
    return {
        "products": [
            {
                "sku": "sku-1",
                "product_code": "p-1",
                "status": "active",
                "category": "toothbrush",
                "use_case_tag": "aftercare_hygiene",
                "price_amount": "12.50",
                "currency_code": "usd",
                "pickup_supported": "yes",
                "delivery_supported": "no",
                "sort_order": "1",
                "default_pickup_branch_id": "br1",
                "media_asset_id": "m1",
                "notes": " note ",
            }
        ],
        "product_i18n": [
            {
                "sku": "sku-1",
                "locale": "EN",
                "title": " Brush ",
                "description": " desc ",
                "short_label": "lbl",
                "justification_text": "j",
                "usage_hint": "u",
            }
        ],
        "branch_availability": [
            {
                "branch_id": "br1",
                "sku": "sku-1",
                "on_hand_qty": "10",
                "availability_enabled": "true",
                "low_stock_threshold": "2",
                "preferred_pickup": "1",
            }
        ],
        "recommendation_sets": [
            {
                "set_code": "set-1",
                "status": "active",
                "title_ru": "ru",
                "title_en": "en",
                "description_ru": "dru",
                "description_en": "den",
                "sort_order": "1",
            }
        ],
        "recommendation_set_items": [
            {
                "set_code": "set-1",
                "sku": "sku-1",
                "position": "1",
                "quantity": "2",
                "notes": "n",
            }
        ],
        "recommendation_links": [
            {
                "recommendation_type": "aftercare",
                "target_kind": "product",
                "target_code": "sku-1",
                "relevance_rank": "1",
                "active": "true",
                "justification_key": "jkey",
                "justification_text_ru": "jru",
                "justification_text_en": "jen",
            }
        ],
        "settings": [{"key": "care.default_pickup_branch_id", "value": "br1"}],
    }


def test_parser_requires_tabs_and_headers() -> None:
    workbook = _valid_workbook()
    del workbook["products"]
    parsed, result = parse_catalog_workbook(workbook=workbook, known_branch_ids={"br1"}, source="xlsx")
    assert parsed is None
    assert any(issue.code == "missing_tab" for issue in result.fatal_errors)


def test_parser_row_validation_for_bad_refs_and_enums() -> None:
    workbook = _valid_workbook()
    workbook["products"][0]["status"] = "broken"
    workbook["product_i18n"][0]["sku"] = "no-such"
    workbook["branch_availability"][0]["branch_id"] = "no-branch"
    parsed, result = parse_catalog_workbook(workbook=workbook, known_branch_ids={"br1"}, source="xlsx")
    assert parsed is not None
    codes = {issue.code for issue in result.validation_errors}
    assert {"invalid_status", "unknown_sku", "unknown_branch"}.issubset(codes)


def test_service_import_updates_master_data_and_keeps_reserved_qty_runtime_truth() -> None:
    repo = InMemoryCatalogRepo()
    service = CareCatalogSyncService(repo)

    workbook = _valid_workbook()
    result = asyncio.run(service._validate_and_apply(clinic_id="c1", workbook=workbook, source="xlsx"))
    assert result.ok
    assert result.stats["products"].added == 1
    assert repo.availability[("br1", "sku-1")]["reserved_qty"] == 3

    workbook["branch_availability"][0]["on_hand_qty"] = "8"
    result2 = asyncio.run(service._validate_and_apply(clinic_id="c1", workbook=workbook, source="xlsx"))
    assert result2.ok
    assert repo.availability[("br1", "sku-1")]["on_hand_qty"] == 8
    assert repo.availability[("br1", "sku-1")]["reserved_qty"] == 3


def test_service_surfaces_sync_failure() -> None:
    repo = InMemoryCatalogRepo()
    service = CareCatalogSyncService(repo)
    result = asyncio.run(
        service.sync_google_sheet(
            clinic_id="c1",
            sheet_url_or_id="https://docs.google.com/spreadsheets/d/does-not-exist/edit#gid=0",
            tmp_path="/tmp/non-existent.xlsx",
        )
    )
    assert not result.ok
    assert any(issue.code == "sheets_download_failed" for issue in result.fatal_errors)


def _make_test_xlsx(path: Path) -> None:
    workbook_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">
  <sheets><sheet name=\"products\" sheetId=\"1\" r:id=\"rId1\"/></sheets>
</workbook>
"""
    rels_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/>
</Relationships>
"""
    sheet_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData>
  <row r=\"1\"><c r=\"A1\" t=\"inlineStr\"><is><t>sku</t></is></c><c r=\"B1\" t=\"inlineStr\"><is><t>product_code</t></is></c></row>
  <row r=\"2\"><c r=\"A2\" t=\"inlineStr\"><is><t>sku-1</t></is></c><c r=\"B2\" t=\"inlineStr\"><is><t>p1</t></is></c></row>
</sheetData></worksheet>
"""
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zipf:
        zipf.writestr("xl/workbook.xml", workbook_xml)
        zipf.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        zipf.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def test_xlsx_import_baseline_validates_missing_tabs(tmp_path: Path) -> None:
    file_path = tmp_path / "catalog.xlsx"
    _make_test_xlsx(file_path)
    repo = InMemoryCatalogRepo()
    service = CareCatalogSyncService(repo)
    result = asyncio.run(service.import_xlsx(clinic_id="c1", path=file_path))
    assert not result.ok
    assert any(issue.code == "missing_tab" for issue in result.fatal_errors)
