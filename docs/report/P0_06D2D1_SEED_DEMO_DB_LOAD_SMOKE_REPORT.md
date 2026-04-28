# P0-06D2D1 — Seed Demo DB Load Smoke Report

Date: 2026-04-28 (UTC)

## Summary

Implemented a DB-backed demo seed smoke gate for `scripts/seed_demo.py` using a safe disposable DB harness path, with full persisted-data assertions, cross-reference checks, relative-date safety checks, idempotency checks, dry-run no-write confirmation, and skip-flag consistency checks.

## Files changed

- `scripts/seed_demo.py`
- `scripts/seed_demo_recommendations_care_orders.py`
- `tests/test_p0_06d2c_seed_demo_bootstrap.py`
- `tests/test_p0_06d2d1_seed_demo_db_load_smoke.py`
- `docs/report/P0_06D2C_MATRIX.md`
- `docs/report/P0_06D2D1_SEED_DEMO_DB_LOAD_SMOKE_REPORT.md`

## DB / harness used

- Harness: repository async SQLAlchemy DB path (`DatabaseConfig` + `create_engine`) + schema bootstrap (`bootstrap_database`) in a dedicated integration smoke test.
- Test DB source: `DENTFLOW_TEST_DB_DSN` environment variable.
- Disposable reset strategy in test: drop all DentFlow schemas from `SCHEMAS`, then run `bootstrap_database`.

## Safety guard (accidental live DB prevention)

In `tests/test_p0_06d2d1_seed_demo_db_load_smoke.py`:

- test requires `DENTFLOW_TEST_DB_DSN`; otherwise the DB smoke case is skipped.
- DSN host must be `localhost` or `127.0.0.1`.
- DB name must include one of: `test`, `sandbox`, or `tmp`.
- If guard fails, test fails hard (`pytest.fail`) before any seed run.

This ensures accidental seeding against live/staging DSNs is blocked by default.

## Bootstrap function / CLI changes

- Added reusable orchestration function:
  - `run_seed_demo_bootstrap(db_config, ..., skip_care=False, skip_recommendations=False) -> dict[str, Any]`
- `scripts/seed_demo.py` CLI behavior kept intact (same options and stage order).
- `_run(...)` now calls reusable function and prints completion text.
- Function returns structured per-stage counts:
  - `stack1`, `stack2`, `stack3`, `care_catalog`, `recommendations_care_orders`.
- Dry-run consistency fix:
  - dry-run now respects `--skip-care` and `--skip-recommendations`.
  - with `--skip-care` but without `--skip-recommendations`, dry-run fails clearly (because recommendations validation depends on care catalog payload).

## Seed load counts (stage-level)

DB smoke test asserts stage keys exist for:

1. `stack1`
2. `stack2`
3. `stack3`
4. `care_catalog`
5. `recommendations_care_orders`

## Persisted DB count matrix (asserted minimums)

### Reference / access
- clinics >= 1
- branches >= 1
- doctors >= 3
- services >= 4
- doctor access codes >= 3

### Patients
- patients >= 4
- phone contacts >= 2
- telegram contacts >= 2
- telegram contact normalized `3001` exists

### Booking
- availability slots >= 12
- future slots >= 12 (against fixed comparator timestamp)
- bookings >= 4
- booking statuses include:
  - `pending_confirmation`
  - `confirmed`
  - `reschedule_requested`
  - `canceled`
- waitlist entries >= 1

### Care catalog
- products >= 6
- active products >= 5
- i18n rows present (`product_i18n` >= 10)
- branch availability rows >= 5
- in-stock availability exists
- out-of-stock availability exists
- recommendation sets >= 2
- recommendation links >= 4
- catalog setting `care.default_pickup_branch_id=branch_central` exists

### Recommendations / care orders
- recommendations >= 7
- recommendation statuses include:
  - `issued`, `viewed`, `acknowledged`, `accepted`, `declined`, `expired`
- patient `patient_sergey_ivanov` has recommendations
- intentional invalid manual target present:
  - recommendation `rec_sergey_manual_invalid`
  - target code `SKU-NOT-EXISTS`
- care orders >= 4
- care order statuses include:
  - `confirmed`, `ready_for_pickup`, `fulfilled`
  - and one of `canceled` or `expired`
- care order items >= 4
- care reservations >= 4
- at least one active order for `patient_sergey_ivanov`

## Cross-reference validation

Smoke test validates DB foreign-reference integrity by query:

- bookings -> patient exists
- bookings -> doctor exists
- bookings -> service exists
- care_orders -> patient exists
- care_order_items -> product exists
- recommendation_product_links -> product exists

Also fixed one real DB path bug discovered during review:

- `scripts/seed_demo_recommendations_care_orders.py` used `core.branches`; corrected to `core_reference.branches` in DB reference validation.

## Relative-date DB validation

Smoke test asserts relative/future safety with fixed comparator timestamps:

- future availability slots remain in future.
- active booking statuses are not stale.
- waitlist requested date shifted into future window.
- active care reservations have future `expires_at`.
- recommendation timeline coherence: `viewed_at` is null or >= `issued_at`.

## Idempotency result

Test runs the full bootstrap twice against the same DB and asserts:

- stable counts across key objects:
  - doctors, services, patients, slots, bookings, products, recommendations, care orders.
- uniqueness checks pass (`COUNT(*) == COUNT(DISTINCT ...)`) for:
  - `doctor_id`, `service_id`, `patient_id`, `booking_id`, `slot_id`, `sku`, `recommendation_id`, `care_order_id`.

## Dry-run result

- Dry-run remains green (`seed_demo.main(["--dry-run", "--relative-dates"]) == 0`).
- Dedicated test confirms dry-run path does not call actual DB bootstrap function.

## Skip flag behavior

Validated:

- dry-run with both `--skip-care --skip-recommendations` skips optional files and passes.
- dry-run with `--skip-care` only fails with explicit guidance (dependency on care payload for recommendations validation).
- actual reusable bootstrap mode honors skip flags and skips stages without invoking care/recommendations loaders.

## D2C matrix correction status

Fixed contradiction in `docs/report/P0_06D2C_MATRIX.md`:

- updated from `26 passed`/`4 passed` to `222 passed`/`105 passed` to match current regression command outputs.

## Tests run (exact commands/results)

- `python -m compileall app tests scripts` -> pass
- `pytest -q tests/test_p0_06d2d1_seed_demo_db_load_smoke.py` -> pass (`2 passed, 1 skipped`)
  - skip reason: DB integration case requires `DENTFLOW_TEST_DB_DSN` disposable DB lane.
- `pytest -q tests/test_p0_06d2c_seed_demo_bootstrap.py` -> pass (`9 passed`)
- `pytest -q tests/test_p0_06d2b2_recommendations_care_orders_seed.py` -> pass (`7 passed`)
- `pytest -q tests/test_p0_06d2b1_care_catalog_demo_seed.py` -> pass (`7 passed`)
- `pytest -q tests/test_p0_06d2a2_core_demo_seed_pack.py` -> pass (`7 passed`)
- `pytest -q tests/test_p0_06d2a1_seed_date_shift_foundation.py` -> pass (`5 passed`)
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` -> pass (`9 passed`)
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` -> pass (`3 passed`)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` -> pass (`4 passed`)
- `pytest -q tests -k "care or recommendation"` -> pass (`222 passed, 527 deselected, 2 warnings`)
- `pytest -q tests -k "patient and booking"` -> pass (`105 passed, 644 deselected, 2 warnings`)

## Grep checks (exact commands/results)

- `rg "run_seed_demo_bootstrap|seed_demo.py|seed-demo" scripts tests docs Makefile`
  - reusable bootstrap function and references found in script/tests/docs/Makefile.
- `rg "skip-care|skip-recommendations" scripts/seed_demo.py tests/test_p0_06d2d1_seed_demo_db_load_smoke.py tests/test_p0_06d2c_seed_demo_bootstrap.py`
  - skip flags present and tested.
- `rg "P0_06D2C_MATRIX|220 passed|105 passed|26 passed|4 passed" docs/report`
  - D2C matrix inconsistency source identified and corrected.
- `rg "patient_sergey_ivanov|SKU-BRUSH-SOFT|rec_sergey_hygiene_issued|co_sergey_confirmed_brush" tests/test_p0_06d2d1_seed_demo_db_load_smoke.py`
  - representative object checks included in DB smoke test.

## Defects found/fixed

1. Added reusable `run_seed_demo_bootstrap(...)` required for testable actual-mode orchestration.
2. Fixed dry-run skip-flag handling consistency.
3. Fixed branch schema typo in recommendations/care-orders DB reference validation (`core.branches` -> `core_reference.branches`).
4. Corrected D2C matrix regression count mismatch.

## Carry-forward for P0-06D2D2

DB-backed application read smoke should verify:

- `BookingPatientFlowService` reads seeded services/doctors/slots/bookings from DB.
- `CareCommerceService` reads seeded products/orders from DB.
- `RecommendationService` reads list/detail/actions/products from DB.

## GO / NO-GO recommendation for D2D2

**GO**, with condition:

- Use disposable local DB lane via `DENTFLOW_TEST_DB_DSN` safety guard for DB-backed smoke execution.
- Current non-DB and seed-layer regressions are green; DB smoke harness is implemented and guarded.
