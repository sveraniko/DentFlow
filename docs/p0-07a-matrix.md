# P0-07A Matrix

Generated: 2026-04-28 (UTC)

## DB lane
- DENTFLOW_TEST_DB_DSN used: **yes** (`postgresql+asyncpg://dentflow:dentflow@127.0.0.1:5432/dentflow_test`)
- DB test executed, not skipped: **yes** (1 passed in 10.61s)
- safe DB guard active: **yes**
- seed-demo run before assertions: **yes** (5/5 stages ok)

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
- product list: **yes** (via service layer)
- product card: **deferred** (runtime card panel state requires message_id consistency; data verified via CareCommerceService)
- care orders list: **yes**
- order detail: **deferred** (same runtime panel state constraint)
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
- P0-07A: **pass** (1 passed in 10.61s)
- D2D2: **pass** (1 passed)
- E4: **pass** (7 passed)
- C4: **pass** (9 passed)
- B4: **pass** (3 passed)
- P0-05C: **pass** (4 passed)
- care or recommendation: **all passed**
- patient and booking: **all passed**

## Command log
- `$env:DENTFLOW_TEST_DB_DSN = "postgresql+asyncpg://dentflow:dentflow@127.0.0.1:5432/dentflow_test"`
- `python -m compileall app tests scripts` → pass
- `pytest -q tests/test_p0_07a_patient_read_surfaces_pre_live.py` → 1 passed in 10.61s
- `pytest -q tests/test_p0_06d2d2_db_backed_application_reads.py` → 1 passed
- `pytest -q tests/test_p0_06e4_integration_readiness_smoke.py` → 7 passed
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` → 9 passed
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` → 3 passed
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` → 4 passed
- `pytest -q tests -k "care or recommendation"` → all passed
- `pytest -q tests -k "patient and booking"` → all passed

## GO / NO-GO
- **P0-07A: GO → P0-07B**
