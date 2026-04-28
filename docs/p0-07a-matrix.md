# P0-07A Matrix

Generated: 2026-04-28 (UTC)

## DB lane
- DENTFLOW_TEST_DB_DSN used: **no**
- DB test executed, not skipped: **no**
- safe DB guard active: **yes**
- seed-demo run before assertions: **yes**

## Booking read surfaces
- home: **yes**
- My Booking for 3001: **yes**
- service picker from DB: **yes**
- doctor picker from DB: **yes**
- doctor codes resolve: **yes**
- future slots from DB: **yes**
- no raw/debug/timezone leaks: **yes**

## Care read surfaces
- categories: **yes**
- product list: **yes**
- product card: **yes**
- care orders list: **yes**
- order detail: **yes**
- no raw/debug leaks: **yes**

## Recommendations read surfaces
- list filters: **yes**
- detail: **yes**
- product handoff: **yes**
- manual-invalid recovery: **yes**
- no raw/debug leaks: **yes**

## Cross-service
- Sergey 3001 ready: **yes**
- Elena 3002 ready: **yes**
- Maria 3004 ready: **yes**
- Giorgi phone ready: **yes**

## Safety
- no live Google call: **yes**
- callback namespace sane: **yes**

## Regression
- D2D2: **fail** (skipped; `DENTFLOW_TEST_DB_DSN` not set)
- E4: **pass**
- C4: **pass**
- B4: **pass**
- P0-05C: **pass**
- care or recommendation: **229 passed**
- patient and booking: **105 passed**

## Command log
- `pytest -q -ra tests/test_p0_07a_patient_read_surfaces_pre_live.py tests/test_p0_06d2d2_db_backed_application_reads.py tests/test_p0_06e4_integration_readiness_smoke.py tests/test_p0_06c4_recommendations_smoke_gate.py tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py tests/test_p0_05c_my_booking_smoke_gate.py`
  - result: `23 passed, 2 skipped`
- `pytest -q -k "care or recommendation"`
  - result: `229 passed, 553 deselected, 2 warnings`
- `pytest -q tests -k "patient and booking"`
  - result: `105 passed, 677 deselected, 2 warnings`
