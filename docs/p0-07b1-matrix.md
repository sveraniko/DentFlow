# P0-07B1 matrix (post-PR verification)

_Date: 2026-04-28 (local DB execution)_

Execution basis:
- `python -m compileall app tests scripts` → passed.
- `pytest -q tests/test_p0_07b1_booking_mutation_pre_live.py` → 1 passed in 9.09s.
- `pytest -q tests/test_p0_07a_patient_read_surfaces_pre_live.py` → 1 passed in 9.53s.
- `pytest -q tests/test_p0_06d2d2_db_backed_application_reads.py` → 1 passed in 6.39s.
- `pytest -q tests/test_p0_06e4_integration_readiness_smoke.py` → 7 passed.
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` → 9 passed.
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` → 3 passed.
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` → 4 passed.
- `pytest -q tests -k "care or recommendation"` → 229 passed.
- `pytest -q tests -k "patient and booking"` → 105 passed.

## DB lane
- DENTFLOW_TEST_DB_DSN used: **yes**
- DB test executed, not skipped: **yes**
- safe DB guard active: **yes**
- seed-demo run before assertions: **yes**

## Doctor code
- Dr. Irina hidden from public list: **yes**
- IRINA-TREAT resolves with service_treatment: **yes**
- wrong service does not resolve: **yes**
- scoped branch behavior correct: **yes**

## New booking mutation
- session created: **yes**
- service selected: **yes**
- protected doctor selected by code: **yes**
- future slot selected: **yes**
- contact submitted/resolved: **yes**
- review ready: **yes**
- booking finalized: **yes**
- DB booking persisted: **yes**

## Edit time mutation
- old hold released: **yes**
- new slot selected: **yes**
- final booking uses new slot/time: **yes**

## Existing booking action
- pending/selected booking mutated: **yes**
- status persisted: **yes**

## Final UI read
- My Booking after mutation clean: **yes**
- no raw/debug/timezone leakage: **yes**

## Safety
- no live Google call: **yes**

## Regression
- P0-07A: **pass** (1 passed, DB-backed)
- D2D2: **pass** (1 passed, DB-backed)
- E4: **pass** (7 passed)
- C4: **pass** (9 passed)
- B4: **pass** (3 passed)
- P0-05C: **pass** (4 passed)
- care or recommendation: **229 passed**
- patient and booking: **105 passed**

## Defects fixed during execution
1. `list_open_slots` excluded slots with live bookings (`NOT EXISTS` subquery)
2. `start_new_existing_booking_session` expires stale control sessions
3. `list_active_sessions_for_telegram_user` filters expired sessions
4. `_NoopOrchestration` in P0-07A test: added `expire_session` stub

## GO/NO-GO
- **GO to P0-07B2**
