from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json

from scripts import seed_demo_recommendations_care_orders as seed_script

SEED_PATH = Path("seeds/demo_recommendations_care_orders.json")
STACK1_PATH = Path("seeds/stack1_seed.json")
STACK2_PATH = Path("seeds/stack2_patients.json")
STACK3_PATH = Path("seeds/stack3_booking.json")
CATALOG_PATH = Path("seeds/care_catalog_demo.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_seed_file_structure() -> None:
    payload = _load(SEED_PATH)
    for key in (
        "recommendations",
        "manual_recommendation_targets",
        "recommendation_product_links",
        "care_orders",
        "care_order_items",
        "care_reservations",
    ):
        assert isinstance(payload.get(key), list)

    assert len(payload["recommendations"]) >= 7
    assert len(payload["care_orders"]) >= 4
    assert len(payload["manual_recommendation_targets"]) >= 4
    assert len(payload["recommendation_product_links"]) >= 1


def test_recommendation_readiness() -> None:
    payload = _load(SEED_PATH)
    stack2 = _load(STACK2_PATH)
    stack3 = _load(STACK3_PATH)

    allowed_types = {"aftercare", "follow_up", "next_step", "hygiene_support", "monitoring", "general_guidance"}
    allowed_source_kinds = {"doctor_manual", "booking_trigger", "system_template"}

    patients = {row["patient_id"] for row in stack2["patients"]}
    bookings = {row["booking_id"] for row in stack3["bookings"]}
    statuses = {row["status"] for row in payload["recommendations"]}

    assert {"issued", "viewed", "acknowledged", "accepted", "declined", "expired"}.issubset(statuses)

    ts_map = seed_script.STATUS_TIMESTAMP_FIELD
    for row in payload["recommendations"]:
        assert row["recommendation_type"] in allowed_types
        assert row["source_kind"] in allowed_source_kinds
        assert row["patient_id"] in patients
        if row.get("booking_id"):
            assert row["booking_id"] in bookings
        assert str(row.get("title") or "").strip()
        assert str(row.get("body_text") or "").strip()
        req = ts_map.get(row["status"])
        if req:
            assert row.get(req)


def test_manual_targets_readiness() -> None:
    payload = _load(SEED_PATH)
    catalog = _load(CATALOG_PATH)
    products = {row["sku"] for row in catalog["products"]}
    sets = {row["set_code"] for row in catalog["recommendation_sets"]}
    categories = {row["category"] for row in catalog["products"]}

    invalid_seen = False
    for row in payload["manual_recommendation_targets"]:
        assert row["target_kind"] in {"product", "set", "category"}
        if row["target_kind"] == "product":
            if row["target_code"] == "SKU-NOT-EXISTS":
                assert row["recommendation_id"] == "rec_sergey_manual_invalid"
                invalid_seen = True
            else:
                assert row["target_code"] in products
        elif row["target_kind"] == "set":
            assert row["target_code"] in sets
        else:
            assert row["target_code"] in categories

    assert invalid_seen


def test_direct_product_links_readiness() -> None:
    payload = _load(SEED_PATH)
    catalog = _load(CATALOG_PATH)
    skus = {row["sku"] for row in catalog["products"]}
    rec_ids = {row["recommendation_id"] for row in payload["recommendations"]}

    for row in payload["recommendation_product_links"]:
        assert row["recommendation_id"] in rec_ids
        assert row["sku"] in skus
        assert int(row["relevance_rank"]) > 0


def test_care_order_readiness() -> None:
    payload = _load(SEED_PATH)
    stack1 = _load(STACK1_PATH)
    stack2 = _load(STACK2_PATH)
    stack3 = _load(STACK3_PATH)
    catalog = _load(CATALOG_PATH)

    statuses = {row["status"] for row in payload["care_orders"]}
    assert {"confirmed", "ready_for_pickup", "fulfilled"}.issubset(statuses)
    assert "canceled" in statuses or "expired" in statuses

    patients = {row["patient_id"] for row in stack2["patients"]}
    bookings = {row["booking_id"] for row in stack3["bookings"]}
    branches = {row["branch_id"] for row in stack1["branches"]}
    rec_ids = {row["recommendation_id"] for row in payload["recommendations"]}
    skus = {row["sku"] for row in catalog["products"]}

    items_by_order = {}
    for item in payload["care_order_items"]:
        assert item["sku"] in skus
        items_by_order.setdefault(item["care_order_id"], []).append(item)

    for order in payload["care_orders"]:
        assert order["patient_id"] in patients
        if order.get("booking_id"):
            assert order["booking_id"] in bookings
        if order.get("recommendation_id"):
            assert order["recommendation_id"] in rec_ids
        assert order["pickup_branch_id"] in branches

        total = sum(int(it["line_total"]) for it in items_by_order[order["care_order_id"]])
        assert total == int(order["total_amount"])

        req_field = seed_script.ORDER_STATUS_TIMESTAMP_FIELD.get(order["status"])
        if req_field:
            assert order.get(req_field)

    order_by_id = {row["care_order_id"]: row for row in payload["care_orders"]}
    expected = {
        "confirmed": "active",
        "ready_for_pickup": "active",
        "fulfilled": "consumed",
        "canceled": "released",
        "expired": "expired",
    }
    for reservation in payload["care_reservations"]:
        order = order_by_id[reservation["care_order_id"]]
        assert reservation["status"] == expected[order["status"]]


def test_relative_date_helper() -> None:
    payload = _load(SEED_PATH)
    original = deepcopy(payload)

    shifted = seed_script.shift_demo_recommendations_care_orders_dates(
        payload,
        now=datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc),
        start_offset_days=1,
    )

    assert payload == original
    assert shifted["recommendations"][0]["recommendation_id"] == payload["recommendations"][0]["recommendation_id"]
    assert shifted["care_orders"][0]["care_order_id"] == payload["care_orders"][0]["care_order_id"]

    original_created = datetime.fromisoformat(payload["recommendations"][0]["created_at"].replace("Z", "+00:00"))
    shifted_created = datetime.fromisoformat(shifted["recommendations"][0]["created_at"].replace("Z", "+00:00"))
    assert shifted_created > original_created

    now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    future_expiry = datetime.fromisoformat(shifted["care_reservations"][0]["expires_at"].replace("Z", "+00:00"))
    assert future_expiry > now


def test_validation_function_allows_only_expected_invalid_manual_target() -> None:
    payload = _load(SEED_PATH)
    result = seed_script.validate_demo_recommendations_care_orders_payload(
        payload,
        stack1_payload=_load(STACK1_PATH),
        stack2_payload=_load(STACK2_PATH),
        stack3_payload=_load(STACK3_PATH),
        catalog_payload=_load(CATALOG_PATH),
    )

    assert result["errors"] == []
    assert any("SKU-NOT-EXISTS" in warning for warning in result["warnings"])
