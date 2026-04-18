from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.application.care_catalog_sync.models import CatalogImportResult, CatalogIssue, ParsedCatalogWorkbook
from app.application.care_catalog_sync.parser import parse_catalog_workbook
from app.application.care_catalog_sync.sheets import download_google_sheet_xlsx
from app.application.care_catalog_sync.xlsx_reader import read_xlsx_workbook


class CareCatalogSyncRepository(Protocol):
    async def list_branch_ids(self, *, clinic_id: str) -> set[str]: ...
    async def upsert_catalog_product(self, *, clinic_id: str, row, now: datetime) -> str: ...
    async def upsert_catalog_product_i18n(self, *, clinic_id: str, row, now: datetime) -> str: ...
    async def upsert_branch_availability_baseline(self, *, clinic_id: str, row, now: datetime) -> str: ...
    async def upsert_recommendation_set(self, *, clinic_id: str, row, now: datetime) -> str: ...
    async def upsert_recommendation_set_item(self, *, clinic_id: str, row, now: datetime) -> str: ...
    async def upsert_recommendation_link(self, *, clinic_id: str, row, now: datetime) -> str: ...
    async def upsert_catalog_setting(self, *, clinic_id: str, key: str, value: str, now: datetime) -> str: ...
    async def apply_catalog_sync_transaction(self, *, clinic_id: str, parsed: ParsedCatalogWorkbook, now: datetime) -> dict[str, dict[str, int]]: ...


@dataclass(slots=True)
class CareCatalogSyncService:
    repository: CareCatalogSyncRepository

    async def import_xlsx(self, *, clinic_id: str, path: str | Path, source: str = "xlsx") -> CatalogImportResult:
        workbook = read_xlsx_workbook(path)
        return await self._validate_and_apply(clinic_id=clinic_id, workbook=workbook, source=source)

    async def sync_google_sheet(
        self,
        *,
        clinic_id: str,
        sheet_url_or_id: str,
        tmp_path: str | Path,
    ) -> CatalogImportResult:
        try:
            xlsx_path = download_google_sheet_xlsx(sheet_url_or_id=sheet_url_or_id, output_path=tmp_path)
        except Exception as exc:
            result = CatalogImportResult(source="google_sheets")
            result.fatal_errors.append(
                CatalogIssue(
                    level="fatal",
                    tab="workbook",
                    row_number=None,
                    code="sheets_download_failed",
                    message=str(exc),
                )
            )
            return result
        return await self.import_xlsx(clinic_id=clinic_id, path=xlsx_path, source="google_sheets")

    async def _validate_and_apply(self, *, clinic_id: str, workbook: dict[str, list[dict[str, str]]], source: str) -> CatalogImportResult:
        known_branch_ids = await self.repository.list_branch_ids(clinic_id=clinic_id)
        parsed, result = parse_catalog_workbook(workbook=workbook, known_branch_ids=known_branch_ids, source=source)
        if parsed is None or result.validation_errors or result.fatal_errors:
            return result
        await self._apply(clinic_id=clinic_id, parsed=parsed, result=result)
        return result

    async def _apply(self, *, clinic_id: str, parsed: ParsedCatalogWorkbook, result: CatalogImportResult) -> None:
        now = datetime.now(timezone.utc)
        transactional_apply = getattr(self.repository, "apply_catalog_sync_transaction", None)
        if callable(transactional_apply):
            tab_states = await transactional_apply(clinic_id=clinic_id, parsed=parsed, now=now)
            for tab, counts in tab_states.items():
                stats = result.ensure_tab(tab)
                stats.added += counts.get("added", 0)
                stats.updated += counts.get("updated", 0)
                stats.unchanged += counts.get("unchanged", 0)
                stats.skipped += counts.get("skipped", 0)
            return

        for row in parsed.products:
            state = await self.repository.upsert_catalog_product(clinic_id=clinic_id, row=row, now=now)
            _bump_stats(result, "products", state)

        for row in parsed.product_i18n:
            state = await self.repository.upsert_catalog_product_i18n(clinic_id=clinic_id, row=row, now=now)
            _bump_stats(result, "product_i18n", state)

        for row in parsed.branch_availability:
            state = await self.repository.upsert_branch_availability_baseline(clinic_id=clinic_id, row=row, now=now)
            _bump_stats(result, "branch_availability", state)

        for row in parsed.recommendation_sets:
            state = await self.repository.upsert_recommendation_set(clinic_id=clinic_id, row=row, now=now)
            _bump_stats(result, "recommendation_sets", state)

        for row in parsed.recommendation_set_items:
            state = await self.repository.upsert_recommendation_set_item(clinic_id=clinic_id, row=row, now=now)
            _bump_stats(result, "recommendation_set_items", state)

        for row in parsed.recommendation_links:
            state = await self.repository.upsert_recommendation_link(clinic_id=clinic_id, row=row, now=now)
            _bump_stats(result, "recommendation_links", state)

        for row in parsed.settings:
            state = await self.repository.upsert_catalog_setting(clinic_id=clinic_id, key=row.key, value=row.value, now=now)
            _bump_stats(result, "settings", state)


def _bump_stats(result: CatalogImportResult, tab: str, state: str) -> None:
    stats = result.ensure_tab(tab)
    if state == "added":
        stats.added += 1
    elif state == "updated":
        stats.updated += 1
    elif state == "unchanged":
        stats.unchanged += 1
    else:
        stats.skipped += 1
