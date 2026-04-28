# P0-07B2 — Recommendation + care mutation pre-live (DB-backed) report

## Summary
- Added DB-backed pre-live mutation smoke test for recommendations and care commerce mutations.
- Test enforces safe DB harness (`DENTFLOW_TEST_DB_DSN`, localhost/127.0.0.1 policy via helper, disposable DB reset, seeded bootstrap).
- In this environment run, DB lane **did not execute successfully** because PostgreSQL at `127.0.0.1:5432` refused connection.

## Files changed
- `tests/test_p0_07b2_recommendation_care_mutation_pre_live.py`
- `docs/report/P0_07B2_RECOMMENDATION_CARE_MUTATION_PRE_LIVE_REPORT.md`

## DB lane execution
- DSN used: `postgresql+asyncpg://dentflow:dentflow@127.0.0.1:5432/dentflow_test`
- Result: **execution attempted, failed before seed/bootstrap due to connection refusal**.
- Status for acceptance: **NO-GO** (required DB-backed lane did not complete).

## Recommendation mutation scenarios covered in test
- Acknowledge active recommendation (`rec_sergey_hygiene_issued`) and persist asserted.
- Accept recommendation after acknowledge and persist asserted.
- Decline separate recommendation (`rec_elena_post_treatment_viewed`) and persist asserted.
- Invalid-state action on terminal recommendation (`rec_giorgi_expired`) expects current domain behavior (`ValueError`).
- Handler-level recommendation detail render (`prec:open:...`) includes leakage guard assertions.

## Recommendation product resolution coverage
- Set target (`rec_sergey_hygiene_issued`) expects `SKU-BRUSH-SOFT`, `SKU-FLOSS-WAXED`, `SKU-PASTE-SENSITIVE`.
- Product target (`rec_sergey_sensitive_ack`) expects `SKU-PASTE-SENSITIVE`.
- Direct link (`rec_sergey_monitoring_accepted`) expects `SKU-FLOSS-WAXED`.
- Invalid manual target (`rec_sergey_manual_invalid`) expects `manual_target_invalid`.

## Care reservation mutation coverage
- In-stock reserve path:
  - product lookup by SKU,
  - branch availability check,
  - create order,
  - transition to confirmed,
  - create reservation,
  - verify items/reservations/order read/list outcomes.

## Out-of-stock mutation behavior coverage
- Uses `SKU-GEL-REMIN` and asserts reserve failure outcome (`insufficient_stock`/availability failure) after order creation attempt.

## Repeat/reorder mutation coverage
- Calls `repeat_order_as_new(...)` for `co_sergey_confirmed_brush` and asserts safe outcomes:
  - created order path, or
  - explicit branch/stock constraints reason.

## Post-mutation reads
- Recommendation get/list and care order get/list assertions are included in the test body.

## No-live-Google assertion
- Test hard-asserts `INTEGRATIONS_GOOGLE_CALENDAR_ENABLED` is not enabled.

## Raw/debug leakage guard
- Guarded tokens include Actions/Channel/internal ids/timezone/date internals and callback namespace checks.

## Tests run (exact commands/results)
- `pytest -q tests/test_p0_07b2_recommendation_care_mutation_pre_live.py` → failed: connection refused (`127.0.0.1:5432`).
- `pytest -q tests/test_p0_07b1_booking_mutation_pre_live.py` → failed: connection refused (`127.0.0.1:5432`).
- `pytest -q tests/test_p0_07a_patient_read_surfaces_pre_live.py` → failed: connection refused (`127.0.0.1:5432`).
- `python -m compileall app tests scripts` → passed.

## Grep checks (exact commands/results)
- `rg "test_p0_07b2_recommendation_care_mutation_pre_live|DENTFLOW_TEST_DB_DSN|run_seed_demo_bootstrap" tests docs` → B2 test/harness references present.
- `rg "rec_sergey_hygiene_issued|rec_sergey_sensitive_ack|rec_sergey_manual_invalid|SKU-BRUSH-SOFT|SKU-GEL-REMIN|co_sergey_confirmed_brush" tests/test_p0_07b2_recommendation_care_mutation_pre_live.py` → representative seed entities asserted.
- `rg "Noop|_Noop" tests/test_p0_07b2_recommendation_care_mutation_pre_live.py` → **found noop classes** for minimal handler smoke only.
- `rg "Actions:|Channel:|Канал:|source_channel|booking_mode|UTC|MSK|%Z|2026-04-" tests/test_p0_07b2_recommendation_care_mutation_pre_live.py` → leakage-guard tokens present.

## Defects found/fixed
- No new domain defect fix was made in this run due DB connectivity blocker.

## Carry-forward for P0-07B3
- Re-run full DB lane with live local test Postgres available.
- Validate complete mutation matrix end-to-end and consolidate final gate report.

## GO/NO-GO recommendation for P0-07B3
- **NO-GO** for this run: required DB-backed B2 lane did not complete due DB connection failure.
