# P0-06D2A1 Seed Harness Repair + Future-safe Stack3 Date Shift Foundation Report

## Summary
- Fixed the D1-reported seed harness failure in `tests/test_patient_db_load_and_seed.py` by implementing missing fake result API support for `.first()`.
- Added optional future-safe relative date shifting to stack3 booking seeding while preserving default static behavior.
- Added CLI flags for relative-date seeding in `scripts/seed_stack3_booking.py`.
- Added focused test coverage for date shifting semantics and static-mode compatibility.

## Files changed
- `tests/test_patient_db_load_and_seed.py`
- `app/infrastructure/db/booking_repository.py`
- `scripts/seed_stack3_booking.py`
- `tests/test_p0_06d2a1_seed_date_shift_foundation.py`
- `docs/92_seed_data_and_demo_fixtures.md`
- `docs/report/P0_06D2A1_SEED_HARNESS_DATE_SHIFT_REPORT.md`

## D1 harness failure fixed

### Root cause
- The test fake `_Result` in `tests/test_patient_db_load_and_seed.py` did not implement `.first()`.
- Production code path for outbox append uses `result.first()` after an insert-returning statement; this caused failure in test harness (not product logic).

### Fix
- Added `def first(self):` to `_Result`, returning first row or `None`.
- Existing fake behavior for `.mappings()` and iteration was preserved.
- No production code logic changes were made for this harness issue.

### Test result
- `pytest -q tests/test_patient_db_load_and_seed.py`
- Result: `3 passed`.

## Future-safe date shift implementation

### Default static mode
- `seed_stack3_booking(db_config, path)` remains backward-compatible.
- With default `relative_dates=False`, payload is loaded as-is.

### Relative mode
- Added optional parameters:
  - `relative_dates: bool = False`
  - `now: datetime | None = None`
  - `start_offset_days: int = 1`
  - `source_anchor_date: date | None = None`
- Added helper `_shift_stack3_seed_dates(...)` that deep-copies payload and shifts relevant fields by one computed day delta.
- Source anchor date resolution:
  1. explicit `source_anchor_date` if provided;
  2. otherwise earliest among: slot `start_at`, booking `scheduled_start_at`, session `requested_date`, and waitlist `date_window.from`/`date_window.to`.
- Target anchor date:
  - `(now or datetime.now(timezone.utc)).date() + timedelta(days=start_offset_days)`.

### Fields shifted
- Datetime-like values:
  - keys ending with `_at` (including `start_at`, `end_at`, `scheduled_start_at`, `scheduled_end_at`, `expires_at`, `created_at`, `updated_at`, etc.).
- Date-only values:
  - `requested_date`
  - `date_window.from`
  - `date_window.to`

### Fields intentionally not shifted
- IDs and ID-like strings, including date-encoded IDs (for example: `slot_anna_20260420_1000`).
- Non-parseable date/datetime strings are left unchanged.

## CLI behavior

### Existing command (unchanged)
```bash
python scripts/seed_stack3_booking.py
```

### New relative-date commands
```bash
python scripts/seed_stack3_booking.py --relative-dates
python scripts/seed_stack3_booking.py --relative-dates --start-offset-days 2
python scripts/seed_stack3_booking.py --relative-dates --source-anchor-date 2026-04-20
```

## Tests run (exact commands/results)
- `python -m compileall app tests` → pass
- `pytest -q tests/test_p0_06d2a1_seed_date_shift_foundation.py` → `5 passed`
- `pytest -q tests/test_patient_db_load_and_seed.py` → `3 passed`
- `pytest -q tests/test_p0_06d1_seed_content_readiness_audit.py` → `3 passed`
- `pytest -q tests/test_booking_seed_bootstrap.py` → `1 passed`
- `pytest -q tests/test_runtime_seed_behavior.py` → `1 passed`
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` → `9 passed`
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` → `3 passed`
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` → `4 passed`
- `pytest -q tests -k "care or recommendation"` → `204 passed, 512 deselected, 2 warnings`
- `pytest -q tests -k "patient and booking"` → `105 passed, 611 deselected, 2 warnings`

## Grep checks (exact commands/results)
- `rg "relative_dates|start_offset_days|source_anchor_date|_shift_stack3" app scripts tests`
  - helper, CLI wiring, and new tests present.
- `rg "2026-04-20|2026-04|2026-05" seeds/stack3_booking.json tests/test_p0_06d2a1_seed_date_shift_foundation.py`
  - static seed still contains fixture dates; tests include assertions proving relative shift output.
- `rg "def first\(" tests/test_patient_db_load_and_seed.py tests`
  - fake result object now supports `.first()` in `tests/test_patient_db_load_and_seed.py`.

## Defects found/fixed
- Fixed: test harness fake result missing `.first()` method.
- No additional production defects were introduced by this scope.

## Carry-forward for P0-06D2A2
- Expand stack1 doctors/services seed coverage.
- Add Telegram patient binding seed data.
- Expand stack3 slots/bookings/status coverage using new relative loader mode.

## GO / NO-GO recommendation for P0-06D2A2
- **GO**.
- Foundation acceptance for D2A1 is met: harness fixed, relative-date loading added (optional), default behavior preserved, and targeted + smoke regression tests are green.
