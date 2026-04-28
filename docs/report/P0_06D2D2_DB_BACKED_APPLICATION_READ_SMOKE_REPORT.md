# P0-06D2D2 — DB-backed Application Read Smoke Report

Date: 2026-04-28 (UTC)

## Summary

Added DB-backed application-service smoke coverage that seeds demo data into a guarded disposable DB and validates read paths through real application services (`BookingPatientFlowService`, `CareCommerceService`, `RecommendationService`) plus patient-contact resolution helpers.

## Files changed

- `tests/helpers/seed_demo_db_harness.py`
- `tests/test_p0_06d2d2_db_backed_application_reads.py`
- `docs/report/P0_06D2D2_DB_BACKED_APPLICATION_READ_SMOKE_REPORT.md`

## DB lane execution

- DSN source: `DENTFLOW_TEST_DB_DSN`.
- Guard enforced in helper:
  - host must be `localhost` or `127.0.0.1`;
  - db name must include `test` or `sandbox` or `tmp`.
- In this run, `DENTFLOW_TEST_DB_DSN` was **not set**.
- Result: DB-backed D2D2 smoke test was skipped by safety harness.
- Acceptance classification for D2D2 in this run: **NO-GO** (required DB lane did not execute).

## Seed bootstrap configuration (in test)

`run_seed_demo_bootstrap(...)` is invoked with:
- `clinic_id="clinic_main"`
- `relative_dates=True`
- `start_offset_days=1`
- `source_anchor_date=date(2026, 4, 20)`
- default seed pack paths for stack1/stack2/stack3/care/recommendations.

## Booking service read assertions implemented

- Reference reads via `ClinicReferenceService`:
  - clinic lookup for `clinic_main`;
  - `branch_central` present;
  - services >= 4;
  - doctors >= 3;
  - public doctors via `BookingPatientFlowService.list_doctors` >= 2;
  - access-code resolution for `ANNA-001`, `BORIS-HYG`, and scoped behavior for `IRINA-TREAT`.
- Booking session read:
  - `bks_001` resolved with expected clinic/user/patient/status/contact snapshot.
- Slot read:
  - sorted, future-safe slots from `list_slots_for_session(...)`.
- Booking read:
  - `bkg_sergey_confirmed` confirmed and future-safe.
- Recent prefill read:
  - `get_recent_booking_prefill(...)` returns service/doctor/branch ids and labels.

## Patient contact resolution assertions implemented

- Exact telegram contact `3001` -> `patient_sergey_ivanov`.
- Exact telegram contact `3002` -> `patient_elena_ivanova`.
- Exact phone contact `+995598123456` -> `patient_giorgi_beridze`.
- Non-existing telegram contact -> `None`.

## CareCommerceService read assertions implemented

- Category reads include hygiene catalog groups (`toothbrush`, `toothpaste`, `floss`, `rinse`, `irrigator`, remineralization-like category).
- Category product read includes `SKU-BRUSH-SOFT` with active status and price/currency.
- Recommendation target resolution:
  - `rec_sergey_hygiene_issued` resolves hygiene product targets;
  - `rec_sergey_sensitive_ack` resolves `SKU-PASTE-SENSITIVE`;
  - `rec_sergey_monitoring_accepted` resolves `SKU-FLOSS-WAXED`;
  - `rec_sergey_manual_invalid` returns `manual_target_invalid` with no products (expected).
- Orders/reservations:
  - patient orders include `confirmed`/`ready_for_pickup`;
  - `co_sergey_confirmed_brush` retrievable;
  - item/reservation linkage validated via repository reads.

## RecommendationService read/action assertions implemented

- Patient list read (`include_terminal=True`) checks history breadth and statuses.
- Non-terminal filter (`include_terminal=False`) excludes terminal statuses.
- Detail read validates populated recommendation payload.
- Action mutation:
  - acknowledges `rec_sergey_hygiene_issued`, verifies persisted status/stamp.
- Invalid transition behavior:
  - `accept(rec_giorgi_expired)` asserts `ValueError`.

## Cross-service patient readiness assertions implemented

- Sergey / Telegram `3001`: patient resolution + booking + recommendations + orders + product resolution.
- Elena / Telegram `3002`: patient resolution + reschedule booking + recommendation/order availability.
- Maria / Telegram `3004`: patient resolution + seeded history recommendation/order availability.

## SQL fallback checks

- Core D2D2 checks are service-level (Booking/Care/Recommendation/Patient contact functions).
- No SQL-only pass criteria used for primary assertions.

## Tests run (exact commands/results)

- `python -m compileall app tests scripts` -> pass.
- `pytest -q tests/test_p0_06d2d2_db_backed_application_reads.py` -> `1 skipped` (DB env missing).
- `pytest -q tests/test_p0_06d2d1_seed_demo_db_load_smoke.py` -> `2 passed, 1 skipped`.
- `pytest -q tests/test_p0_06d2c_seed_demo_bootstrap.py` -> `9 passed`.
- `pytest -q tests/test_p0_06d2b2_recommendations_care_orders_seed.py` -> `7 passed`.
- `pytest -q tests/test_p0_06d2b1_care_catalog_demo_seed.py` -> `7 passed`.
- `pytest -q tests/test_p0_06d2a2_core_demo_seed_pack.py` -> `7 passed`.
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` -> `9 passed`.
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` -> `3 passed`.
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` -> `4 passed`.
- `pytest -q tests -k "care or recommendation"` -> `222 passed, 528 deselected, 2 warnings`.
- `pytest -q tests -k "patient and booking"` -> `105 passed, 645 deselected, 2 warnings`.

## Grep checks (exact commands/results)

- `rg "test_p0_06d2d2_db_backed_application_reads|BookingPatientFlowService|CareCommerceService|RecommendationService" tests app docs`
  - D2D2 test present and application services usage present.
- `rg "DENTFLOW_TEST_DB_DSN|localhost|127.0.0.1|sandbox|tmp|test" tests/test_p0_06d2d2_db_backed_application_reads.py tests/helpers`
  - safe DB guard present via shared helper.
- `rg "rec_sergey_hygiene_issued|rec_sergey_sensitive_ack|rec_sergey_manual_invalid|co_sergey_confirmed_brush|SKU-BRUSH-SOFT|patient_sergey_ivanov" tests/test_p0_06d2d2_db_backed_application_reads.py`
  - representative seeded entities asserted in D2D2 test.
- `rg "pytest.skip|skip" tests/test_p0_06d2d2_db_backed_application_reads.py`
  - no local skip usage; skip path is centralized in shared DB harness.

## Defects found/fixed

- No domain defects discovered in this change.
- One temporary local regression during implementation (`tests/__init__.py` side-effect on imports) was reverted before final run.

## Carry-forward

- P0-06E: Sheets templates + integration runbook.
- P0-07: final patient pre-live smoke.

## GO / NO-GO recommendation for P0-06E

**NO-GO for this run**, because required DB-backed D2D2 smoke did not execute (missing `DENTFLOW_TEST_DB_DSN`).

To flip to GO:
1. set `DENTFLOW_TEST_DB_DSN` to a safe disposable local DB (`localhost`/`127.0.0.1`, db name including `test|sandbox|tmp`),
2. re-run `pytest -q tests/test_p0_06d2d2_db_backed_application_reads.py` and confirm no skip,
3. keep regressions green.
