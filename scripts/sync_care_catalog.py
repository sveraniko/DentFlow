from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.application.care_catalog_sync import CareCatalogSyncService
from app.config.settings import DatabaseConfig
from app.infrastructure.db.care_commerce_repository import DbCareCommerceRepository


def _print_result(result) -> None:
    print(f"source={result.source} ok={result.ok}")
    if result.tabs_processed:
        print(f"tabs={','.join(result.tabs_processed)}")
    for tab, stats in sorted(result.stats.items()):
        print(
            f"tab={tab} added={stats.added} updated={stats.updated} unchanged={stats.unchanged} skipped={stats.skipped}"
        )
    for issue in result.warnings:
        print(f"warning [{issue.tab}:{issue.row_number}] {issue.code}: {issue.message}")
    for issue in result.validation_errors:
        print(f"error [{issue.tab}:{issue.row_number}] {issue.code}: {issue.message}")
    for issue in result.fatal_errors:
        print(f"fatal [{issue.tab}] {issue.code}: {issue.message}")


async def _run(args) -> int:
    repo = DbCareCommerceRepository(DatabaseConfig())
    service = CareCatalogSyncService(repo)
    if args.mode == "xlsx":
        result = await service.import_xlsx(clinic_id=args.clinic_id, path=args.path, source="xlsx")
    else:
        tmp = Path(args.tmp_file)
        result = await service.sync_google_sheet(
            clinic_id=args.clinic_id,
            sheet_url_or_id=args.sheet,
            tmp_path=tmp,
        )
    _print_result(result)
    return 0 if result.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="DentFlow care catalog import/sync")
    parser.add_argument("--clinic-id", required=True)
    sub = parser.add_subparsers(dest="mode", required=True)

    xlsx = sub.add_parser("xlsx", help="import from xlsx workbook")
    xlsx.add_argument("--path", required=True)

    sheets = sub.add_parser("sheets", help="sync from Google Sheets export")
    sheets.add_argument("--sheet", required=True, help="Google Sheets URL or sheet id")
    sheets.add_argument("--tmp-file", default="/tmp/dentflow-care-catalog.xlsx")

    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
