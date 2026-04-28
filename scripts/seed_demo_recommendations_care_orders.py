from __future__ import annotations

import argparse
import asyncio
import json
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text

from app.config.settings import get_settings
from app.domain.care_commerce import RecommendationProductLink
from app.domain.recommendations import Recommendation
from app.infrastructure.db.care_commerce_repository import DbCareCommerceRepository
from app.infrastructure.db.engine import create_engine
from app.infrastructure.db.recommendation_repository import DbRecommendationRepository

ALLOWED_MANUAL_TARGET_KINDS = {"product", "set", "category"}
STATUS_TIMESTAMP_FIELD = {
    "issued": "issued_at",
    "viewed": "viewed_at",
    "acknowledged": "acknowledged_at",
    "accepted": "accepted_at",
    "declined": "declined_at",
    "expired": "expired_at",
    "withdrawn": "withdrawn_at",
}
ORDER_STATUS_TIMESTAMP_FIELD = {
    "confirmed": "confirmed_at",
    "ready_for_pickup": "ready_for_pickup_at",
    "fulfilled": "fulfilled_at",
    "canceled": "canceled_at",
    "expired": "expired_at",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed demo patient recommendations + care orders fixtures")
    parser.add_argument("--path", type=Path, default=Path("seeds/demo_recommendations_care_orders.json"))
    parser.add_argument("--relative-dates", action="store_true")
    parser.add_argument("--start-offset-days", type=int, default=1)
    parser.add_argument("--source-anchor-date", type=date.fromisoformat, default=None)
    return parser.parse_args()


def load_seed_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _shift_iso_datetime_string(value: str, *, delta_days: int) -> str | None:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return None
    shifted = parsed + timedelta(days=delta_days)
    rendered = shifted.isoformat()
    if value.endswith("Z") and rendered.endswith("+00:00"):
        return f"{rendered[:-6]}Z"
    return rendered


def _detect_anchor_date(payload: dict[str, Any]) -> date | None:
    candidates: list[date] = []
    explicit = payload.get("source_anchor_date")
    if isinstance(explicit, str):
        try:
            return date.fromisoformat(explicit)
        except ValueError:
            pass

    for section in ("recommendations", "care_orders", "care_reservations"):
        for row in payload.get(section, []):
            for key in ("created_at", "issued_at"):
                value = row.get(key)
                if isinstance(value, str):
                    parsed = _parse_iso_datetime(value)
                    if parsed is not None:
                        candidates.append(parsed.date())
    return min(candidates) if candidates else None


def shift_demo_recommendations_care_orders_dates(
    payload: dict[str, Any],
    *,
    now: datetime | None = None,
    start_offset_days: int = 1,
    source_anchor_date: date | None = None,
) -> dict[str, Any]:
    shifted = deepcopy(payload)
    anchor = source_anchor_date or _detect_anchor_date(payload)
    if anchor is None:
        return shifted
    effective_now = now or datetime.now(timezone.utc)
    target_anchor = effective_now.date() + timedelta(days=start_offset_days)
    delta_days = (target_anchor - anchor).days
    if delta_days == 0:
        return shifted

    for key, value in shifted.items():
        if isinstance(value, list):
            for row in value:
                if not isinstance(row, dict):
                    continue
                for field, raw in list(row.items()):
                    if not isinstance(raw, str):
                        continue
                    if field.endswith("_at") or field == "expires_at":
                        new_value = _shift_iso_datetime_string(raw, delta_days=delta_days)
                        if new_value is not None:
                            row[field] = new_value
    return shifted


def _load_support_payloads() -> dict[str, Any]:
    return {
        "stack1": load_seed_payload(Path("seeds/stack1_seed.json")),
        "stack2": load_seed_payload(Path("seeds/stack2_patients.json")),
        "stack3": load_seed_payload(Path("seeds/stack3_booking.json")),
        "catalog": load_seed_payload(Path("seeds/care_catalog_demo.json")),
    }


def validate_demo_recommendations_care_orders_payload(
    payload: dict[str, Any],
    *,
    stack1_payload: dict[str, Any],
    stack2_payload: dict[str, Any],
    stack3_payload: dict[str, Any],
    catalog_payload: dict[str, Any],
) -> dict[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    required_arrays = {
        "recommendations",
        "manual_recommendation_targets",
        "recommendation_product_links",
        "care_orders",
        "care_order_items",
        "care_reservations",
    }
    for key in required_arrays:
        if not isinstance(payload.get(key), list):
            errors.append(f"Missing top-level array: {key}")

    patients = {row["patient_id"] for row in stack2_payload["patients"]}
    bookings = {row["booking_id"] for row in stack3_payload["bookings"]}
    branches = {row["branch_id"] for row in stack1_payload["branches"]}
    valid_types = {"aftercare", "follow_up", "next_step", "hygiene_support", "monitoring", "general_guidance"}
    valid_sources = {"doctor_manual", "booking_trigger", "system_template"}
    catalog_skus = {row["sku"] for row in catalog_payload["products"]}
    catalog_sets = {row["set_code"] for row in catalog_payload["recommendation_sets"]}
    catalog_categories = {row["category"] for row in catalog_payload["products"]}
    sku_price = {
        row["sku"]: int((Decimal(str(row["price_amount"])) * 100).quantize(Decimal("1")))
        for row in catalog_payload["products"]
        if row.get("status") == "active"
    }

    recommendation_by_id = {row["recommendation_id"]: row for row in payload.get("recommendations", [])}
    order_by_id = {row["care_order_id"]: row for row in payload.get("care_orders", [])}

    for row in payload.get("recommendations", []):
        rec_id = row["recommendation_id"]
        if row.get("patient_id") not in patients:
            errors.append(f"Recommendation {rec_id} references unknown patient")
        booking_id = row.get("booking_id")
        if booking_id and booking_id not in bookings:
            errors.append(f"Recommendation {rec_id} references unknown booking")
        if row.get("recommendation_type") not in valid_types:
            errors.append(f"Recommendation {rec_id} has unsupported recommendation_type")
        if row.get("source_kind") not in valid_sources:
            errors.append(f"Recommendation {rec_id} has unsupported source_kind")
        if not str(row.get("title") or "").strip() or not str(row.get("body_text") or "").strip():
            errors.append(f"Recommendation {rec_id} has empty title/body")
        required_ts = STATUS_TIMESTAMP_FIELD.get(row.get("status"))
        if required_ts and not row.get(required_ts):
            errors.append(f"Recommendation {rec_id} missing required {required_ts}")

    for row in payload.get("manual_recommendation_targets", []):
        rec_id = row["recommendation_id"]
        kind = row.get("target_kind")
        code = row.get("target_code")
        if rec_id not in recommendation_by_id:
            errors.append(f"Manual target references unknown recommendation {rec_id}")
        if kind not in ALLOWED_MANUAL_TARGET_KINDS:
            errors.append(f"Manual target {rec_id} has invalid target_kind")
        if kind == "product" and code not in catalog_skus:
            if code == "SKU-NOT-EXISTS" and rec_id == "rec_sergey_manual_invalid":
                warnings.append("Intentional invalid manual target SKU-NOT-EXISTS retained for smoke")
            else:
                errors.append(f"Manual target {rec_id} references unknown SKU {code}")
        if kind == "set" and code not in catalog_sets:
            errors.append(f"Manual target {rec_id} references unknown set {code}")
        if kind == "category" and code not in catalog_categories:
            errors.append(f"Manual target {rec_id} references unknown category {code}")

    for row in payload.get("recommendation_product_links", []):
        rec_id = row.get("recommendation_id")
        sku = row.get("sku")
        if rec_id not in recommendation_by_id:
            errors.append(f"Direct link references unknown recommendation {rec_id}")
        if sku not in catalog_skus:
            errors.append(f"Direct link {row.get('recommendation_product_link_id')} references unknown sku {sku}")
        if int(row.get("relevance_rank") or 0) <= 0:
            errors.append(f"Direct link {row.get('recommendation_product_link_id')} must have positive rank")

    items_by_order: dict[str, list[dict[str, Any]]] = {}
    for item in payload.get("care_order_items", []):
        items_by_order.setdefault(item["care_order_id"], []).append(item)
        sku = item.get("sku")
        qty = int(item.get("quantity") or 0)
        unit_price = int(item.get("unit_price") or 0)
        if sku not in catalog_skus:
            errors.append(f"Order item {item['care_order_item_id']} references unknown sku")
        if qty <= 0:
            errors.append(f"Order item {item['care_order_item_id']} has non-positive quantity")
        if sku in sku_price and unit_price != sku_price[sku]:
            errors.append(f"Order item {item['care_order_item_id']} unit_price mismatch for sku {sku}")
        if int(item.get("line_total") or 0) != qty * unit_price:
            errors.append(f"Order item {item['care_order_item_id']} has invalid line_total")

    for order in payload.get("care_orders", []):
        order_id = order["care_order_id"]
        if order.get("patient_id") not in patients:
            errors.append(f"Order {order_id} references unknown patient")
        booking_id = order.get("booking_id")
        if booking_id and booking_id not in bookings:
            errors.append(f"Order {order_id} references unknown booking")
        rec_id = order.get("recommendation_id")
        if rec_id and rec_id not in recommendation_by_id:
            errors.append(f"Order {order_id} references unknown recommendation")
        if order.get("pickup_branch_id") not in branches:
            errors.append(f"Order {order_id} references unknown branch")
        status_field = ORDER_STATUS_TIMESTAMP_FIELD.get(order.get("status"))
        if status_field and not order.get(status_field):
            errors.append(f"Order {order_id} missing required {status_field}")
        subtotal = sum(int(row["line_total"]) for row in items_by_order.get(order_id, []))
        if subtotal != int(order.get("total_amount") or 0):
            errors.append(f"Order {order_id} total_amount mismatch")

    reservation_status_expectations = {
        "confirmed": "active",
        "ready_for_pickup": "active",
        "fulfilled": "consumed",
        "canceled": "released",
        "expired": "expired",
    }
    for row in payload.get("care_reservations", []):
        order_id = row.get("care_order_id")
        sku = row.get("sku")
        order = order_by_id.get(order_id)
        if order is None:
            errors.append(f"Reservation {row['care_reservation_id']} references unknown order")
            continue
        if sku not in catalog_skus:
            errors.append(f"Reservation {row['care_reservation_id']} references unknown sku")
        if row.get("branch_id") not in branches:
            errors.append(f"Reservation {row['care_reservation_id']} references unknown branch")
        expected_status = reservation_status_expectations.get(order.get("status"))
        if expected_status and row.get("status") != expected_status:
            errors.append(f"Reservation {row['care_reservation_id']} has status {row.get('status')} but expected {expected_status}")

    return {"errors": errors, "warnings": warnings}


async def _lookup_product_ids(conn, skus: set[str]) -> dict[str, str]:
    if not skus:
        return {}
    rows = (
        await conn.execute(
            text(
                """
                SELECT sku, care_product_id
                FROM care_commerce.products
                WHERE sku IN :skus
                """
            ).bindparams(bindparam("skus", expanding=True)),
            {"skus": tuple(sorted(skus))},
        )
    ).mappings()
    return {str(row["sku"]): str(row["care_product_id"]) for row in rows}


async def _validate_db_refs(conn, payload: dict[str, Any]) -> None:
    def _collect(section: str, key: str) -> set[str]:
        return {str(row[key]) for row in payload.get(section, []) if row.get(key)}

    patient_ids = _collect("recommendations", "patient_id") | _collect("care_orders", "patient_id")
    booking_ids = _collect("recommendations", "booking_id") | _collect("care_orders", "booking_id")
    recommendation_ids = _collect("recommendations", "recommendation_id")

    existing_patients = set(
        (await conn.execute(text("SELECT patient_id FROM core_patient.patients WHERE patient_id IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": tuple(patient_ids) if patient_ids else ("",)})).scalars()
    )
    missing_patients = sorted(patient_ids - existing_patients)
    if missing_patients:
        raise ValueError(f"Missing patient references in DB: {missing_patients}")

    if booking_ids:
        existing_bookings = set(
            (await conn.execute(text("SELECT booking_id FROM booking.bookings WHERE booking_id IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": tuple(booking_ids)})).scalars()
        )
        missing_bookings = sorted(booking_ids - existing_bookings)
        if missing_bookings:
            raise ValueError(f"Missing booking references in DB: {missing_bookings}")

    existing_branches = set(
        (await conn.execute(text("SELECT branch_id FROM core.branches WHERE branch_id IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": tuple({row['pickup_branch_id'] for row in payload.get('care_orders', []) if row.get('pickup_branch_id')}) or ("",)})).scalars()
    )
    order_branches = {str(row["pickup_branch_id"]) for row in payload.get("care_orders", []) if row.get("pickup_branch_id")}
    missing_branches = sorted(order_branches - existing_branches)
    if missing_branches:
        raise ValueError(f"Missing branch references in DB: {missing_branches}")

    if recommendation_ids:
        rows = (await conn.execute(text("SELECT recommendation_id FROM recommendation.recommendations WHERE recommendation_id IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": tuple(recommendation_ids)})).scalars()
        # existing recommendation rows are optional because script creates/upserts them first.
        _ = rows


async def _seed_orders_items_reservations(conn, payload: dict[str, Any], sku_to_product_id: dict[str, str]) -> dict[str, int]:
    for order in payload.get("care_orders", []):
        await conn.execute(
            text(
                """
                INSERT INTO care_commerce.care_orders (
                  care_order_id, clinic_id, patient_id, booking_id, recommendation_id, status,
                  payment_mode, pickup_branch_id, total_amount, currency_code,
                  created_at, updated_at, confirmed_at, paid_at, ready_for_pickup_at,
                  issued_at, fulfilled_at, canceled_at, expired_at
                ) VALUES (
                  :care_order_id, :clinic_id, :patient_id, :booking_id, :recommendation_id, :status,
                  :payment_mode, :pickup_branch_id, :total_amount, :currency_code,
                  :created_at, :updated_at, :confirmed_at, :paid_at, :ready_for_pickup_at,
                  :issued_at, :fulfilled_at, :canceled_at, :expired_at
                )
                ON CONFLICT (care_order_id) DO UPDATE SET
                  clinic_id=EXCLUDED.clinic_id,
                  patient_id=EXCLUDED.patient_id,
                  booking_id=EXCLUDED.booking_id,
                  recommendation_id=EXCLUDED.recommendation_id,
                  status=EXCLUDED.status,
                  payment_mode=EXCLUDED.payment_mode,
                  pickup_branch_id=EXCLUDED.pickup_branch_id,
                  total_amount=EXCLUDED.total_amount,
                  currency_code=EXCLUDED.currency_code,
                  updated_at=EXCLUDED.updated_at,
                  confirmed_at=EXCLUDED.confirmed_at,
                  paid_at=EXCLUDED.paid_at,
                  ready_for_pickup_at=EXCLUDED.ready_for_pickup_at,
                  issued_at=EXCLUDED.issued_at,
                  fulfilled_at=EXCLUDED.fulfilled_at,
                  canceled_at=EXCLUDED.canceled_at,
                  expired_at=EXCLUDED.expired_at
                """
            ),
            order,
        )

    for item in payload.get("care_order_items", []):
        mapped = dict(item)
        mapped["care_product_id"] = sku_to_product_id[item["sku"]]
        await conn.execute(
            text(
                """
                INSERT INTO care_commerce.care_order_items (
                  care_order_item_id, care_order_id, care_product_id, quantity,
                  unit_price, line_total, created_at
                ) VALUES (
                  :care_order_item_id, :care_order_id, :care_product_id, :quantity,
                  :unit_price, :line_total, :created_at
                )
                ON CONFLICT (care_order_item_id) DO UPDATE SET
                  care_order_id=EXCLUDED.care_order_id,
                  care_product_id=EXCLUDED.care_product_id,
                  quantity=EXCLUDED.quantity,
                  unit_price=EXCLUDED.unit_price,
                  line_total=EXCLUDED.line_total
                """
            ),
            mapped,
        )

    for reservation in payload.get("care_reservations", []):
        mapped = dict(reservation)
        mapped["care_product_id"] = sku_to_product_id[reservation["sku"]]
        await conn.execute(
            text(
                """
                INSERT INTO care_commerce.care_reservations (
                  care_reservation_id, care_order_id, care_product_id, branch_id, status,
                  reserved_qty, expires_at, created_at, updated_at, released_at, consumed_at
                ) VALUES (
                  :care_reservation_id, :care_order_id, :care_product_id, :branch_id, :status,
                  :reserved_qty, :expires_at, :created_at, :updated_at, :released_at, :consumed_at
                )
                ON CONFLICT (care_reservation_id) DO UPDATE SET
                  care_order_id=EXCLUDED.care_order_id,
                  care_product_id=EXCLUDED.care_product_id,
                  branch_id=EXCLUDED.branch_id,
                  status=EXCLUDED.status,
                  reserved_qty=EXCLUDED.reserved_qty,
                  expires_at=EXCLUDED.expires_at,
                  updated_at=EXCLUDED.updated_at,
                  released_at=EXCLUDED.released_at,
                  consumed_at=EXCLUDED.consumed_at
                """
            ),
            mapped,
        )

    return {
        "care_orders": len(payload.get("care_orders", [])),
        "care_order_items": len(payload.get("care_order_items", [])),
        "care_reservations": len(payload.get("care_reservations", [])),
    }


async def seed_demo_recommendations_care_orders(
    db_config: Any,
    path: Path,
    *,
    relative_dates: bool = False,
    now: datetime | None = None,
    start_offset_days: int = 1,
    source_anchor_date: date | None = None,
) -> dict[str, int]:
    payload = load_seed_payload(path)
    payload_to_seed = (
        shift_demo_recommendations_care_orders_dates(
            payload,
            now=now,
            start_offset_days=start_offset_days,
            source_anchor_date=source_anchor_date,
        )
        if relative_dates
        else payload
    )

    validation = validate_demo_recommendations_care_orders_payload(payload_to_seed, **_load_support_payloads())
    if validation["errors"]:
        raise ValueError("\n".join(validation["errors"]))

    recommendation_repo = DbRecommendationRepository(db_config)
    care_repo = DbCareCommerceRepository(db_config)

    for row in payload_to_seed.get("recommendations", []):
        await recommendation_repo.save(Recommendation(**row))

    for row in payload_to_seed.get("manual_recommendation_targets", []):
        await care_repo.upsert_manual_recommendation_target(
            recommendation_id=row["recommendation_id"],
            target_kind=row["target_kind"],
            target_code=row["target_code"],
            justification_text=row.get("justification_text"),
        )

    engine = create_engine(db_config)
    try:
        async with engine.begin() as conn:
            await _validate_db_refs(conn, payload_to_seed)
            skus = {row["sku"] for row in payload_to_seed.get("recommendation_product_links", [])}
            skus.update({row["sku"] for row in payload_to_seed.get("care_order_items", [])})
            skus.update({row["sku"] for row in payload_to_seed.get("care_reservations", [])})
            sku_to_product_id = await _lookup_product_ids(conn, skus)
            missing_skus = sorted(skus - set(sku_to_product_id))
            if missing_skus:
                raise ValueError(f"Missing care catalog SKUs in DB: {missing_skus}")

            for row in payload_to_seed.get("recommendation_product_links", []):
                await care_repo.link_product_to_recommendation(
                    RecommendationProductLink(
                        recommendation_product_link_id=row["recommendation_product_link_id"],
                        recommendation_id=row["recommendation_id"],
                        care_product_id=sku_to_product_id[row["sku"]],
                        relevance_rank=int(row["relevance_rank"]),
                        justification_key=row.get("justification_key"),
                        justification_text_key=row.get("justification_text_key"),
                        created_at=datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00")),
                    )
                )

            counts_sql = await _seed_orders_items_reservations(conn, payload_to_seed, sku_to_product_id)
    finally:
        await engine.dispose()

    return {
        "recommendations": len(payload_to_seed.get("recommendations", [])),
        "manual_recommendation_targets": len(payload_to_seed.get("manual_recommendation_targets", [])),
        "recommendation_product_links": len(payload_to_seed.get("recommendation_product_links", [])),
        **counts_sql,
    }


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    counts = await seed_demo_recommendations_care_orders(
        settings.db,
        args.path,
        relative_dates=args.relative_dates,
        start_offset_days=args.start_offset_days,
        source_anchor_date=args.source_anchor_date,
    )
    print("Demo recommendations + care orders seed loaded")
    for key, value in counts.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(_run(_parse_args()))
