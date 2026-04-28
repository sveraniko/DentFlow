# P0-07B1 — Booking mutation pre-live (DB-backed) report

## Summary
- Implemented doctor access-code semantic fix: non-public doctors remain hidden from public doctor listings but can be resolved via active scoped access code when doctor status is active.
- Added DB-backed booking mutation smoke test covering:
  - scenario A: protected/code-only doctor booking (`IRINA-TREAT` → `doctor_irina`);
  - scenario B: edit-time flow (hold release + reselection + finalize);
  - existing booking mutation action (patient confirms `bkg_sergey_pending`);
  - handler-level My Booking render with callback namespace and leakage guards;
  - explicit no-live-Google guard.
- Updated P0-07A and D2D2 read tests to assert `IRINA-TREAT` resolves in-scope.

## Files changed
- `app/application/clinic_reference.py`
- `tests/test_p0_07b1_booking_mutation_pre_live.py`
- `tests/test_p0_07a_patient_read_surfaces_pre_live.py`
- `tests/test_p0_06d2d2_db_backed_application_reads.py`
- `docs/report/P0_07A_PATIENT_READ_SURFACES_PRE_LIVE_REPORT.md`
- `docs/report/P0_07B1_BOOKING_MUTATION_PRE_LIVE_REPORT.md`

## DB lane execution
- DSN configured for attempted runs:
  - `postgresql+asyncpg://dentflow:dentflow@127.0.0.1:5432/dentflow_test`
- Status: **executed attempt, but DB service unreachable in current environment**.
- Failure: `ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 5432)`.
- Result: **NO-GO in this environment** (DB lane could not complete).

## Protected doctor access-code fix
- Old behavior: `resolve_doctor_access_code(...)` rejected non-public doctors (`public_booking_enabled=false`) and returned `None` even with valid scoped code.
- New behavior:
  - code must be active and not expired;
  - scope must match (`service_id` / `branch_id` if present);
  - doctor must exist and be `RecordStatus.ACTIVE`;
  - `public_booking_enabled` is **not** required for code-resolution.
- Public doctor list remains unaffected (still filtered by `public_booking_enabled`).

## Booking mutation scenario A (protected doctor code path)
- Flow implemented in `tests/test_p0_07b1_booking_mutation_pre_live.py`:
  1. start session (telegram user `3004`, patient `patient_maria_petrova`);
  2. select `service_treatment`;
  3. resolve `IRINA-TREAT`;
  4. assert resolved doctor = `doctor_irina`;
  5. select future open `doctor_irina` slot in `branch_central`;
  6. submit existing patient contact (`+7 (999) 888-44-00`);
  7. mark review ready;
  8. finalize;
  9. assert DB booking fields and expected status set (`pending_confirmation` or `confirmed`);
  10. assert hold consumed and slot cannot be reused.

## Booking mutation scenario B (review edit time)
- Flow implemented in same test:
  1. new session for `service_consult` with `doctor_anna`;
  2. select first slot;
  3. release selected slot for reselection;
  4. assert prior hold becomes `released`;
  5. select second slot;
  6. submit contact;
  7. review ready + finalize;
  8. assert finalized booking uses new slot/time.

## Existing booking action mutation
- Implemented patient confirm action for seeded `bkg_sergey_pending`.
- Validated via `confirm_existing_booking(...)` with session from `resolve_existing_booking_for_known_patient(...)`.
- Asserted persisted status transition to `confirmed`.

## Handler-level final read panel result
- Rendered `My Booking` via patient bot handler callback (`phome:my_booking`) for user `3004`.
- Asserted readable panel content and callback namespace restrictions.
- Added negative assertions to block raw/debug fields and timezone/internal leakage.

## No-live-Google assertion
- Test asserts `INTEGRATIONS_GOOGLE_CALENDAR_ENABLED` is not enabled (`1/true/yes/on` disallowed).
- Seeding/bootstrap assertions remain restricted to local demo stacks.

## Raw/debug leakage guard
- Panel text negative assertions include:
  - `Actions:`, `Channel:`, `Канал:`, `source_channel`, `booking_mode`, IDs (`booking_id/slot_id/patient_id/...`), `UTC`, `MSK`, `%Z`, `2026-04-`.
- Callback assertions allow only expected namespaces and runtime-encoded callbacks.

## Tests run (exact commands/results)
- `pytest -q tests/test_p0_07b1_booking_mutation_pre_live.py` → **failed in env** (DB connect refused).
- `pytest -q tests/test_p0_07a_patient_read_surfaces_pre_live.py` → **failed in env** (DB connect refused).
- `pytest -q tests/test_p0_06d2d2_db_backed_application_reads.py` → **failed in env** (DB connect refused).
- `python -m compileall app tests scripts` → passed.
- `pytest -q tests/test_p0_06e4_integration_readiness_smoke.py tests/test_p0_06c4_recommendations_smoke_gate.py tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py tests/test_p0_05c_my_booking_smoke_gate.py` → passed.
- `pytest -q tests -k "care or recommendation"` → passed.
- `pytest -q tests -k "patient and booking"` → passed.

## Grep checks (exact commands/results)
- `rg "IRINA-TREAT|doctor_irina|public_booking_enabled" app tests seeds docs/report` → confirms semantic coverage in app/tests/seeds.
- `rg "NoopOrchestration|_NoopOrchestration" tests/test_p0_07b1_booking_mutation_pre_live.py` → no matches (expected for mutation orchestration).
- `rg "DENTFLOW_TEST_DB_DSN|TEST_DB_DSN_ENV|run_seed_demo_bootstrap|safe_test_db_config" tests/test_p0_07b1_booking_mutation_pre_live.py` → DB harness/guard usage present.
- `rg "Actions:|Channel:|Канал:|source_channel|booking_mode|UTC|MSK|%Z|2026-04-" tests/test_p0_07b1_booking_mutation_pre_live.py` → negative-leakage assertions present.

## Defects found/fixed
- Fixed product/seed semantic mismatch: protected doctor access-code now works independently from public doctor list visibility.

## Carry-forward for P0-07B2
- DB-backed recommendation action mutation.
- DB-backed care reserve mutation.
- DB-backed care repeat mutation.

## GO/NO-GO for P0-07B2
- **NO-GO in this environment** because DB lane could not be executed successfully end-to-end (PostgreSQL unavailable at `127.0.0.1:5432`).
- Conditional GO once DB lane rerun succeeds with the same commands.
