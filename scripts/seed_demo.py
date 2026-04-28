from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Any

from app.application.care_catalog_sync.parser import parse_catalog_workbook
from app.application.care_catalog_sync.service import CareCatalogSyncService
from app.config.settings import get_settings
from app.infrastructure.db.booking_repository import _shift_stack3_seed_dates, seed_stack3_booking
from app.infrastructure.db.care_commerce_repository import DbCareCommerceRepository
from app.infrastructure.db.patient_repository import seed_stack2_patients
from app.infrastructure.db.repositories import seed_stack_data
from scripts.seed_demo_recommendations_care_orders import (
    load_seed_payload,
    seed_demo_recommendations_care_orders,
    shift_demo_recommendations_care_orders_dates,
    validate_demo_recommendations_care_orders_payload,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed full DentFlow demo fixture pack")
    parser.add_argument("--clinic-id", default="clinic_main")
    parser.add_argument("--relative-dates", action="store_true")
    parser.add_argument("--start-offset-days", type=int, default=1)
    parser.add_argument("--source-anchor-date", type=date.fromisoformat, default=None)
    parser.add_argument("--stack1-path", type=Path, default=Path("seeds/stack1_seed.json"))
    parser.add_argument("--stack2-path", type=Path, default=Path("seeds/stack2_patients.json"))
    parser.add_argument("--stack3-path", type=Path, default=Path("seeds/stack3_booking.json"))
    parser.add_argument("--care-catalog-path", type=Path, default=Path("seeds/care_catalog_demo.json"))
    parser.add_argument(
        "--recommendations-care-orders-path",
        type=Path,
        default=Path("seeds/demo_recommendations_care_orders.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-care", action="store_true")
    parser.add_argument("--skip-recommendations", action="store_true")
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_file_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {label} file: {path}")


def _validate_stack3_refs(stack1: dict[str, Any], stack2: dict[str, Any], stack3: dict[str, Any]) -> None:
    patient_ids = {row["patient_id"] for row in stack2.get("patients", [])}
    doctor_ids = {row["doctor_id"] for row in stack1.get("doctors", [])}
    service_ids = {row["service_id"] for row in stack1.get("services", [])}
    branch_ids = {row["branch_id"] for row in stack1.get("branches", [])}

    for booking in stack3.get("bookings", []):
        if booking.get("patient_id") not in patient_ids:
            raise ValueError(f"stack3 booking references unknown patient: {booking.get('patient_id')}")
        if booking.get("doctor_id") not in doctor_ids:
            raise ValueError(f"stack3 booking references unknown doctor: {booking.get('doctor_id')}")
        if booking.get("service_id") not in service_ids:
            raise ValueError(f"stack3 booking references unknown service: {booking.get('service_id')}")
        if booking.get("branch_id") not in branch_ids:
            raise ValueError(f"stack3 booking references unknown branch: {booking.get('branch_id')}")


def _print_header(args: argparse.Namespace) -> None:
    print("DentFlow demo seed bootstrap")
    print(f"  stack1 path: {args.stack1_path}")
    print(f"  stack2 path: {args.stack2_path}")
    print(f"  stack3 path: {args.stack3_path}")
    print(f"  care catalog path: {args.care_catalog_path}")
    print(f"  recommendations/care orders path: {args.recommendations_care_orders_path}")
    print(f"  relative_dates: {args.relative_dates}")
    print(f"  start_offset_days: {args.start_offset_days}")
    print(f"  clinic_id: {args.clinic_id}")


def _format_counts(counts: dict[str, Any]) -> str:
    return " ".join(f"{k}={v}" for k, v in sorted(counts.items()))


def _dry_run(args: argparse.Namespace) -> int:
    _print_header(args)
    files = [
        (args.stack1_path, "stack1"),
        (args.stack2_path, "stack2"),
        (args.stack3_path, "stack3"),
    ]
    if not args.skip_care:
        files.append((args.care_catalog_path, "care catalog"))
    if not args.skip_recommendations:
        files.append((args.recommendations_care_orders_path, "recommendations/care orders"))
    for path, label in files:
        _validate_file_exists(path, label)

    stack1_payload = _load_json(args.stack1_path)
    stack2_payload = _load_json(args.stack2_path)
    stack3_payload = _load_json(args.stack3_path)
    _validate_stack3_refs(stack1_payload, stack2_payload, stack3_payload)
    if args.relative_dates:
        _ = _shift_stack3_seed_dates(
            stack3_payload,
            start_offset_days=args.start_offset_days,
            source_anchor_date=args.source_anchor_date,
        )

    rec_validation: dict[str, list[str]] = {"errors": [], "warnings": []}
    if not args.skip_care:
        care_catalog_payload = _load_json(args.care_catalog_path)
        known_branch_ids = {str(row["branch_id"]) for row in stack1_payload.get("branches", [])}
        parsed_catalog, catalog_result = parse_catalog_workbook(
            workbook=care_catalog_payload,
            known_branch_ids=known_branch_ids,
            source="json",
        )
        if parsed_catalog is None:
            raise ValueError("Care catalog parser returned no parsed payload")
        if catalog_result.validation_errors or catalog_result.fatal_errors:
            problems = [*catalog_result.validation_errors, *catalog_result.fatal_errors]
            details = "; ".join(f"{item.code}: {item.message}" for item in problems)
            raise ValueError(f"Care catalog validation failed: {details}")
    else:
        care_catalog_payload = {}

    if not args.skip_recommendations:
        if args.skip_care:
            raise ValueError("--skip-recommendations must be used when --skip-care is enabled in dry-run mode")
        rec_payload = load_seed_payload(args.recommendations_care_orders_path)
        payload_for_validation = (
            shift_demo_recommendations_care_orders_dates(
                rec_payload,
                start_offset_days=args.start_offset_days,
                source_anchor_date=args.source_anchor_date,
            )
            if args.relative_dates
            else rec_payload
        )
        rec_validation = validate_demo_recommendations_care_orders_payload(
            payload_for_validation,
            stack1_payload=stack1_payload,
            stack2_payload=stack2_payload,
            stack3_payload=stack3_payload,
            catalog_payload=care_catalog_payload,
        )
        if rec_validation["errors"]:
            raise ValueError("Recommendations/care orders validation failed: " + "; ".join(rec_validation["errors"]))

    print("[1/5] stack1 reference... planned")
    print("[2/5] stack2 patients... planned")
    print("[3/5] stack3 booking... planned")
    print("[4/5] care catalog... planned" if not args.skip_care else "[4/5] care catalog... skipped")
    if args.skip_recommendations:
        print("[5/5] recommendations + care orders... skipped")
    else:
        print("[5/5] recommendations + care orders... planned")
    for warning in rec_validation["warnings"]:
        print(f"warning: {warning}")
    print("Dry-run validation complete.")
    return 0


async def _run(args: argparse.Namespace) -> int:
    if args.dry_run:
        return _dry_run(args)

    _print_header(args)
    settings = get_settings()
    await run_seed_demo_bootstrap(
        settings.db,
        clinic_id=args.clinic_id,
        relative_dates=args.relative_dates,
        start_offset_days=args.start_offset_days,
        source_anchor_date=args.source_anchor_date,
        stack1_path=args.stack1_path,
        stack2_path=args.stack2_path,
        stack3_path=args.stack3_path,
        care_catalog_path=args.care_catalog_path,
        recommendations_care_orders_path=args.recommendations_care_orders_path,
        skip_care=args.skip_care,
        skip_recommendations=args.skip_recommendations,
    )
    print("Demo seed bootstrap complete.")
    return 0


async def run_seed_demo_bootstrap(
    db_config,
    *,
    clinic_id: str,
    relative_dates: bool,
    start_offset_days: int,
    source_anchor_date: date | None,
    stack1_path: Path,
    stack2_path: Path,
    stack3_path: Path,
    care_catalog_path: Path,
    recommendations_care_orders_path: Path,
    skip_care: bool = False,
    skip_recommendations: bool = False,
) -> dict[str, Any]:
    stage_counts: dict[str, Any] = {}

    print("[1/5] stack1 reference...")
    stack1_counts = await seed_stack_data(db_config, stack1_path)
    stage_counts["stack1"] = stack1_counts
    print(f"ok {_format_counts(stack1_counts)}")

    print("[2/5] stack2 patients...")
    stack2_payload = _load_json(stack2_path)
    stack2_counts = await seed_stack2_patients(db_config, stack2_payload)
    stage_counts["stack2"] = stack2_counts
    print(f"ok {_format_counts(stack2_counts)}")

    print("[3/5] stack3 booking...")
    stack3_counts = await seed_stack3_booking(
        db_config,
        stack3_path,
        relative_dates=relative_dates,
        start_offset_days=start_offset_days,
        source_anchor_date=source_anchor_date,
    )
    stage_counts["stack3"] = stack3_counts
    print(f"ok {_format_counts(stack3_counts)}")

    if skip_care:
        stage_counts["care_catalog"] = {"skipped": True}
        print("[4/5] care catalog... skipped")
    else:
        print("[4/5] care catalog...")
        service = CareCatalogSyncService(DbCareCommerceRepository(db_config))
        catalog_result = await service.import_json(clinic_id=clinic_id, path=care_catalog_path)
        if not catalog_result.ok:
            print("care catalog import failed")
            for issue in catalog_result.validation_errors:
                print(f"error [{issue.tab}:{issue.row_number}] {issue.code}: {issue.message}")
            for issue in catalog_result.fatal_errors:
                print(f"fatal [{issue.tab}] {issue.code}: {issue.message}")
            raise ValueError("Care catalog import failed")
        totals = {
            "tabs": len(catalog_result.tabs_processed),
            "warnings": len(catalog_result.warnings),
        }
        stage_counts["care_catalog"] = totals
        print(f"ok {_format_counts(totals)}")

    if skip_recommendations:
        stage_counts["recommendations_care_orders"] = {"skipped": True}
        print("[5/5] recommendations + care orders... skipped")
    else:
        print("[5/5] recommendations + care orders...")
        rec_counts = await seed_demo_recommendations_care_orders(
            db_config,
            recommendations_care_orders_path,
            relative_dates=relative_dates,
            start_offset_days=start_offset_days,
            source_anchor_date=source_anchor_date,
        )
        stage_counts["recommendations_care_orders"] = rec_counts
        print(f"ok {_format_counts(rec_counts)}")

    return stage_counts


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
