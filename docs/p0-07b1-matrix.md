# P0-07B1 matrix (post-PR verification)

_Date: 2026-04-28 (UTC)_

Execution basis in this environment:
- `pytest -q tests/test_p0_07b1_booking_mutation_pre_live.py` → skipped (no DB DSN configured).
- `pytest -q tests/test_p0_07a_patient_read_surfaces_pre_live.py tests/test_p0_06d2d2_db_backed_application_reads.py tests/test_p0_06e4_integration_readiness_smoke.py tests/test_p0_06c4_recommendations_smoke_gate.py tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py tests/test_p0_05c_my_booking_smoke_gate.py` → 23 passed, 2 skipped.
- `pytest -q tests -k "care or recommendation"` → 229 passed.
- `pytest -q tests -k "patient and booking"` → 105 passed.

## DB lane
- DENTFLOW_TEST_DB_DSN used: **no**
- DB test executed, not skipped: **no**
- safe DB guard active: **yes**
- seed-demo run before assertions: **no**

## Doctor code
- Dr. Irina hidden from public list: **no**
- IRINA-TREAT resolves with service_treatment: **no**
- wrong service does not resolve: **no**
- scoped branch behavior correct: **no**

## New booking mutation
- session created: **no**
- service selected: **no**
- protected doctor selected by code: **no**
- future slot selected: **no**
- contact submitted/resolved: **no**
- review ready: **no**
- booking finalized: **no**
- DB booking persisted: **no**

## Edit time mutation
- old hold released: **no**
- new slot selected: **no**
- final booking uses new slot/time: **no**

## Existing booking action
- pending/selected booking mutated: **no**
- status persisted: **no**

## Final UI read
- My Booking after mutation clean: **no**
- no raw/debug/timezone leakage: **no**

## Safety
- no live Google call: **no**

## Regression
- P0-07A: **pass** (suite green; DB-smoke test skipped)
- D2D2: **pass** (suite green; DB-smoke test skipped)
- E4: **pass**
- C4: **pass**
- B4: **pass**
- P0-05C: **pass**
- care or recommendation: **229 passed**
- patient and booking: **105 passed**
