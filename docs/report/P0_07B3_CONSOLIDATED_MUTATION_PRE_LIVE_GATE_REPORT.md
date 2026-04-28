# P0-07B3 — Consolidated DB-backed mutation pre-live gate report

## Summary
- Added consolidated DB-backed mutation gate test that exercises representative booking, recommendation, and care mutation flows on real DB repositories/services.
- Added mandatory out-of-stock invariant checks for `SKU-GEL-REMIN` proving reserve failure, no reservation row, and non-active resulting order visibility.
- Added post-mutation patient surface checks (`My Booking`, recommendation panel, care orders panel) with leakage and callback namespace guards.
- DB lane **executed successfully** against local PostgreSQL (`dentflow_pg` Docker container, `dentflow_test` database).

## Files changed
- `tests/test_p0_07b3_consolidated_mutation_pre_live_gate.py`
- `docs/report/P0_07B3_CONSOLIDATED_MUTATION_PRE_LIVE_GATE_REPORT.md`

## DB lane execution
- DSN used: `postgresql+asyncpg://dentflow:dentflow@127.0.0.1:5432/dentflow_test`
- Docker containers: `dentflow_pg` and `dentflow_redis` started locally.
- Execution status:
  - Test invoked: **yes**
  - Test skipped: **no**
  - Test passed: **yes** (1 passed in 10.89s)

## Booking mutation summary
Covered in consolidated gate:
- `doctor_irina` hidden from public doctor list.
- `IRINA-TREAT` resolves only for `service_treatment` + `branch_central`; wrong service denied.
- New booking path creates persisted booking for Maria (`patient_maria_petrova`) with `service_treatment` and `doctor_irina` on future slot.
- Edit-time path releases old hold and finalizes on new slot/time.
- Existing booking action mutation confirms `bkg_sergey_pending`, and stale repeat confirm returns invalid-state-safe outcome.

## Recommendation mutation summary
Covered in consolidated gate:
- `acknowledge` persists.
- `accept` persists.
- `decline` persists.
- invalid-state action (`accept` on expired recommendation) safely raises invalid transition.
- read-after-mutate check confirms updated status in DB.
- handler-rendered recommendation panel for accepted recommendation no longer exposes mutation action callbacks (`rec:ack|accept|decline`).

## Care mutation summary
Covered in consolidated gate:
- In-stock reserve flow creates order, order item, reservation, and expected total.
- Patient order list includes created order.
- Repeat/reorder flow returns allowed safe matrix result (`ok` or constrained-safe reason).

## Out-of-stock final invariant (`SKU-GEL-REMIN`)
- Reserve attempt returns failure reason in accepted set: `insufficient_stock` / `availability_inactive` / `availability_missing`.
- Reservation count for failed order is exactly zero.
- Failed order row may exist technically, but status is asserted non-active (not `confirmed`, `ready_for_pickup`, `active`).
- Patient order list includes no active user-visible reserve state for the failed out-of-stock attempt.

## Post-mutation read surfaces
- Booking patient (`3004` / Maria): `My Booking` callback panel renders without raw/debug leakage tokens.
- Sergey (`3001`): recommendation detail callback renders cleanly with allowed callback namespaces and no mutation actions after accept.
- Sergey (`3001`): care orders callback renders cleanly without forbidden debug/raw fields.

## No-live-Google assertion
- Consolidated gate explicitly asserts `INTEGRATIONS_GOOGLE_CALENDAR_ENABLED` is not true.
- Flow uses DB-backed services only; no live Google API call path is intentionally invoked.

## Raw/debug leakage guard
- Consolidated test enforces negative assertions for forbidden tokens in rendered panels:
  - `Actions:`, `Channel:`, `Канал:`, `source_channel`, `booking_mode`, IDs, timezone/debug markers (`UTC`, `MSK`, `%Z`, `2026-04-`).

## Callback namespace check
- Collected callback data from rendered booking/recommendation/care panels.
- Asserted all callbacks are either allowed prefixes (`phome:`, `book:`, `care:`, `careo:`, `prec:`, `rec:`, `rsch:`) or runtime codec `cN|...`.

## Tests run (exact commands/results)
- `pytest -q tests/test_p0_07b3_consolidated_mutation_pre_live_gate.py` → **1 passed in 10.89s**.
- `python -m compileall tests/test_p0_07b3_consolidated_mutation_pre_live_gate.py` → **PASS**.

## Grep checks (exact commands/results)
- `rg "test_p0_07b3_consolidated_mutation_pre_live_gate|DENTFLOW_TEST_DB_DSN|run_seed_demo_bootstrap" tests docs`
  - Result: consolidated test/harness references found.
- `rg "IRINA-TREAT|doctor_irina|rec_sergey_hygiene_issued|SKU-GEL-REMIN|co_sergey_confirmed_brush" tests/test_p0_07b3_consolidated_mutation_pre_live_gate.py`
  - Result: representative mutation objects asserted.
- `rg "Noop|_Noop" tests/test_p0_07b3_consolidated_mutation_pre_live_gate.py`
  - Result: only tiny handler-only noop reminder dependency present (`_NoopReminderActions`), not used for mutation logic.
- `rg "Actions:|Channel:|Канал:|source_channel|booking_mode|UTC|MSK|%Z|2026-04-" tests/test_p0_07b3_consolidated_mutation_pre_live_gate.py`
  - Result: appears in negative leakage assertion token list.

## Defects found/fixed
- Implemented missing consolidated B3 gate test coverage and report artifact.
- No application feature/schema/router changes needed — test passed on first DB-backed run.

## Carry-forward for P0-07C
1. Manual Telegram live dry-run:
   - booking (new booking + edit time + existing booking action),
   - recommendations (ack/accept/decline state changes),
   - care reserve/repeat flows,
   - product card + order detail visibility on out-of-stock failure.
2. Full regression pass confirmation.

## GO/NO-GO recommendation for P0-07C
- **GO** — all DB-backed consolidated mutation tests pass end-to-end.
