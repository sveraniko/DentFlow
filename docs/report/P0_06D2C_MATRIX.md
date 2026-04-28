# P0-06D2C Matrix

Дата проверки: 2026-04-28 (UTC).

## Script
- scripts/seed_demo.py exists: **yes**
- dry-run mode exists: **yes**
- actual mode exists: **yes**
- fail-fast behavior: **yes**

## Order
- stack1 first: **yes**
- stack2 second: **yes**
- stack3 third: **yes**
- care catalog fourth: **yes**
- recommendations/care orders fifth: **yes**

## Relative dates
- --relative-dates supported: **yes**
- --start-offset-days supported: **yes**
- --source-anchor-date supported: **yes**
- flags propagated to stack3: **yes**
- flags propagated to recommendations/care-orders: **yes**

## Validation
- seed files existence checked: **yes**
- care catalog parsed in dry-run: **yes**
- recommendations/care orders validated in dry-run: **yes**
- intentional invalid SKU warning not fatal: **yes**

## Makefile/docs
- make seed-demo exists: **yes**
- docs updated: **yes**

## Regression
- D2B2: **pass**
- D2B1: **pass**
- D2A2: **pass**
- D2A1: **pass**
- C4 recommendations smoke: **pass**
- B4 care smoke: **pass**
- P0-05C smoke: **pass**
- care or recommendation: **26 passed**
- patient and booking: **4 passed**

## Evidence quick map
- Script/flow/options/validation: `scripts/seed_demo.py`
- Intentional invalid SKU warning behavior: `scripts/seed_demo_recommendations_care_orders.py`
- Required order and D2C docs section: `docs/92_seed_data_and_demo_fixtures.md`
- Make target: `Makefile`
- Regression checks:
  - `tests/test_p0_06d2b2_recommendations_care_orders_seed.py`
  - `tests/test_p0_06d2b1_care_catalog_demo_seed.py`
  - `tests/test_p0_06d2a2_core_demo_seed_pack.py`
  - `tests/test_p0_06d2a1_seed_date_shift_foundation.py`
  - `tests/test_p0_06c4_recommendations_smoke_gate.py`
  - `tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py`
  - `tests/test_p0_05c_my_booking_smoke_gate.py`
  - `tests/test_p0_06d2c_seed_demo_bootstrap.py`
