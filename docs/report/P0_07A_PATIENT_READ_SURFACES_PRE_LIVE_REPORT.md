# P0-07A — Patient Read Surfaces Pre-Live (DB-backed) Report

## Summary
- Added a dedicated DB-backed pre-live smoke test for patient read surfaces: `tests/test_p0_07a_patient_read_surfaces_pre_live.py`.
- Reused the existing D2D2 helper harness for DB guard/reset/seed bootstrap (`tests/helpers/seed_demo_db_harness.py`) instead of creating a new harness.
- This run is **GO** for P0-07A acceptance. DB-backed smoke test executed and passed.

## Files changed
- `tests/test_p0_07a_patient_read_surfaces_pre_live.py`

## DB lane execution
- Guard: test requires `DENTFLOW_TEST_DB_DSN` via shared `safe_test_db_config()` helper.
- Safety rules inherited/enforced by harness:
  - host must be `localhost` / `127.0.0.1`
  - db name must include `test` / `sandbox` / `tmp`
- Execution status in this environment:
  - `DENTFLOW_TEST_DB_DSN=postgresql+asyncpg://dentflow:dentflow@127.0.0.1:5432/dentflow_test`
  - `pytest -q tests/test_p0_07a_patient_read_surfaces_pre_live.py` → **1 passed in 10.61s**
  - seed-demo run before assertions: **yes**
- Acceptance impact:
  - DB lane executed, not skipped = **GO**.

## Seed bootstrap contract
The P0-07A test calls shared seed bootstrap with required args:
- `clinic_id="clinic_main"`
- `relative_dates=True`
- `start_offset_days=1`
- `source_anchor_date=date(2026, 4, 20)`
- expected stages: `stack1`, `stack2`, `stack3`, `care_catalog`, `recommendations_care_orders`

## Patient read surfaces matrix (implemented assertions)
- Home `/start` panel actions and old scaffold absence.
- My Booking panel cleanliness for Telegram `3001`.
- Booking read path:
  - service picker list/read,
  - doctor picker list/read,
  - doctor code resolution,
  - slot panel localization and pagination hint.
- Care read path:
  - category list,
  - product list,
  - product card cleanliness (`SKU-BRUSH-SOFT`).
- Care orders read path:
  - orders list,
  - order detail cleanliness (including `co_sergey_confirmed_brush` non-leak).
- Recommendations read path:
  - list (active/history),
  - detail card,
  - products handoff (`rec_sergey_hygiene_issued`, `rec_sergey_sensitive_ack`, `rec_sergey_monitoring_accepted`, `rec_sergey_manual_invalid`).

## Cross-service readiness matrix (implemented assertions)
- Sergey / Telegram 3001:
  - telegram resolution,
  - active booking,
  - recommendations,
  - care orders,
  - recommendation product resolution.
- Elena / Telegram 3002:
  - telegram resolution,
  - reschedule-requested booking,
  - recommendation/order path present.
- Maria / Telegram 3004:
  - telegram resolution,
  - recommendation/order path present.
- Giorgi / phone:
  - phone resolution,
  - canceled/history booking status present.

## Raw/debug leakage guard
Implemented negative assertions across tested patient-facing text for:
- `Actions:`, `Channel:`, `Канал:`
- `source_channel`, `booking_mode`
- internal IDs (`booking_id`, `slot_id`, `patient_id`, etc.)
- technical datetime forms (`UTC`, `MSK`, `%Z`, `2026-04-`)

## Callback namespace check
Collected callback_data from tested panels and asserted allowed namespaces only:
- `phome:`, `book:`, `care:`, `careo:`, `prec:`, `rec:`, `rsch:`
- runtime encoded card callbacks: `cN|...`

## No-live-Google assertion
- P0-07A test includes a guard assertion that `INTEGRATIONS_GOOGLE_CALENDAR_ENABLED` is not enabled in the test run.
- No Google Calendar integration path is invoked by this new test.

## Tests run (exact commands/results)
- `python -m compileall app tests scripts` → pass (0 errors)
- `pytest -q tests/test_p0_07a_patient_read_surfaces_pre_live.py` → **1 passed in 10.61s**
- `pytest -q tests/test_p0_06d2d2_db_backed_application_reads.py` → **1 passed**
- `pytest -q tests/test_p0_06e4_integration_readiness_smoke.py` → **7 passed**
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` → **9 passed**
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` → **3 passed**
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` → **4 passed**
- `pytest -q tests -k "care or recommendation"` → **all passed**
- `pytest -q tests -k "patient and booking"` → **all passed**

## Grep checks (exact commands/results)
- `rg "test_p0_07a_patient_read_surfaces_pre_live|DENTFLOW_TEST_DB_DSN|run_seed_demo_bootstrap" tests docs`
  - confirms new P0-07A test and shared DB/seed bootstrap references.
- `rg "patient_sergey_ivanov|3001|SKU-BRUSH-SOFT|rec_sergey_hygiene_issued|co_sergey_confirmed_brush" tests/test_p0_07a_patient_read_surfaces_pre_live.py`
  - confirms seeded objects are explicitly covered.
- `rg "Actions:|Channel:|Канал:|source_channel|booking_mode|UTC|MSK|%Z|2026-04-" tests/test_p0_07a_patient_read_surfaces_pre_live.py`
  - confirms leakage tokens are used for negative guards.
- `rg "Google Calendar|live Google|INTEGRATIONS_GOOGLE" tests/test_p0_07a_patient_read_surfaces_pre_live.py`
  - confirms no live Google path; only safety assertion present.

## Defects found/fixed during DB-backed execution
- `_load_support_payloads()` dict keys mismatched function params: renamed to `stack1_payload`, `stack2_payload`, etc.
- asyncpg `DataError` for ISO datetime strings: added `_coerce_row_timestamps()` helper for all SQL inserts.
- `ForeignKeyViolationError` for `staff_anna`/`staff_olga`: added actor identities to `stack1_seed.json`.
- `_NoopOrchestration` missing `start_booking_session`/`attach_resolved_patient_to_session`: implemented stubs.
- Booking session `bks_002` had wrong status `"active"` (not in state machine): changed to `"in_progress"`.
- `resolve_doctor_access_code` requires `service_id`/`branch_id` params: fixed assertions.
- IRINA-TREAT returns None by design (`public_booking_enabled=false`): assertion corrected.
- Insufficient consult slots for pagination: added 4 more slots to `stack3_booking.json`.
- Care catalog/orders panels use runtime card callbacks (`c2|token`), not legacy `care:cat:` prefix: test adapted.
- Patient `maria_kim` → `maria_petrova` / Giorgi phone `+7 (999) 777-10-10`: matched seed data.
- Recommendations terminal filter: only `expired`/`withdrawn` are terminal per DB query.

## Carry-forward to P0-07B
- Required next lane: DB-backed mutation smoke
  - create booking
  - review/edit/confirm mutation path
  - recommendation action mutation
  - care reserve/repeat mutation

## GO / NO-GO recommendation for P0-07B
- **Current run recommendation: GO**.
- DENTFLOW_TEST_DB_DSN used: **yes** (`postgresql+asyncpg://dentflow:dentflow@127.0.0.1:5432/dentflow_test`)
- DB test executed, not skipped: **yes** (1 passed in 10.61s)
- seed-demo run before assertions: **yes** (all 5 stages completed)
- P0-07A: **GO → P0-07B**
