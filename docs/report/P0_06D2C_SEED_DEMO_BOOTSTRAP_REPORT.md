# P0-06D2C — Seed Demo Bootstrap Report

## Summary

Implemented `scripts/seed_demo.py` as a one-command bootstrap for the full demo seed pack with deterministic order, dry-run validation mode, and relative-date propagation for stack3 and recommendations/care-orders seed stages.

## Files changed

- `scripts/seed_demo.py` (new)
- `Makefile`
- `docs/92_seed_data_and_demo_fixtures.md`
- `tests/test_p0_06d2c_seed_demo_bootstrap.py` (new)

## Bootstrap order

Implemented in exact order:

1. stack1 reference seed
2. stack2 patients
3. stack3 booking seed
4. care catalog import
5. recommendations + care orders seed

## CLI options

Implemented options:

- `--clinic-id` (default `clinic_main`)
- `--relative-dates`
- `--start-offset-days` (default `1`)
- `--source-anchor-date YYYY-MM-DD`
- `--stack1-path`
- `--stack2-path`
- `--stack3-path`
- `--care-catalog-path`
- `--recommendations-care-orders-path`
- `--dry-run`
- `--skip-care` (optional)
- `--skip-recommendations` (optional)

## Dry-run behavior

`--dry-run` now:

- does not write to DB;
- checks required files exist;
- parses all JSON files;
- validates stack3 cross-reference integrity (stack1/stack2 IDs used by stack3 bookings);
- validates care catalog with `parse_catalog_workbook`;
- validates recommendations/care-orders with existing D2B2 validator;
- applies relative-date validation transformations when enabled;
- prints planned execution steps and effective paths/mode.

Returns non-zero on missing files or validation failures.

## Actual run behavior

Non-dry-run mode now:

- fails fast on errors;
- prints clear `[N/5]` step headers;
- prints per-step count summaries;
- exits non-zero when care catalog result is `ok=False`;
- runs stack3 + recommendations/care-orders with propagated relative-date options.

## Makefile target

Added:

- `seed-demo` → `python scripts/seed_demo.py --relative-dates --start-offset-days 1`
- `seed-demo-dry-run` → `python scripts/seed_demo.py --relative-dates --start-offset-days 1 --dry-run`

## Relative-date propagation

Validated via test monkeypatching:

- stack3 receives `relative_dates`, `start_offset_days`, `source_anchor_date`
- recommendations/care-orders receives the same values

## Tests run (commands and results)

- `python -m compileall app tests scripts` → pass
- `pytest -q tests/test_p0_06d2c_seed_demo_bootstrap.py` → `7 passed`
- `pytest -q tests/test_p0_06d2b2_recommendations_care_orders_seed.py` → `7 passed`
- `pytest -q tests/test_p0_06d2b1_care_catalog_demo_seed.py` → `7 passed`
- `pytest -q tests/test_p0_06d2a2_core_demo_seed_pack.py` → `7 passed`
- `pytest -q tests/test_p0_06d2a1_seed_date_shift_foundation.py` → `5 passed`
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` → `9 passed`
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` → `3 passed`
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` → `4 passed`
- `pytest -q tests -k "care or recommendation"` → `220 passed, 524 deselected` (2 known pytest mark warnings)
- `pytest -q tests -k "patient and booking"` → `105 passed, 639 deselected` (2 known pytest mark warnings)

## Grep checks (commands and results)

- `rg "seed-demo|seed_demo.py" Makefile scripts docs tests` → target/script/docs/tests presence confirmed.
- `rg "stack1.*stack2.*stack3|care catalog|recommendations.*care orders" scripts/seed_demo.py docs/92_seed_data_and_demo_fixtures.md tests/test_p0_06d2c_seed_demo_bootstrap.py` → required order and stage references visible in code/docs/tests.
- `rg "relative-dates|start-offset-days|source-anchor-date" scripts/seed_demo.py docs tests` → relative-date options documented and tested.

## Defects found/fixed

- Added missing one-command bootstrap entrypoint for D2 seed pack.
- Added dry-run validation path to prevent accidental failing runs due to missing/invalid seed files.
- Added regression test coverage for order and parameter propagation.

## Carry-forward for P0-06D2D

- Run real DB demo-load smoke using safe harness.
- Capture insert/update counts stage-by-stage on real DB.
- Add UI/API round-trip read validations after seeding.

## GO / NO-GO recommendation for D2D

**GO** for P0-06D2D.

Reason: bootstrap CLI, dry-run validation, order guarantees, and regression gates are in place; no schema/UI changes introduced.
