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
- `app/application/booking/telegram_flow.py`
- `app/infrastructure/db/booking_repository.py`
- `tests/test_p0_07b1_booking_mutation_pre_live.py`
- `tests/test_p0_07a_patient_read_surfaces_pre_live.py`
- `tests/test_p0_06d2d2_db_backed_application_reads.py`
- `docs/report/P0_07A_PATIENT_READ_SURFACES_PRE_LIVE_REPORT.md`
- `docs/report/P0_07B1_BOOKING_MUTATION_PRE_LIVE_REPORT.md`
- `docs/p0-07b1-matrix.md`

## DB lane execution
- DSN configured: `postgresql+asyncpg://dentflow:dentflow@127.0.0.1:5432/dentflow_test`
- Status: **executed successfully, all DB-backed tests pass**.
- Docker containers: `dentflow_pg` and `dentflow_redis` started locally.
- Database: `dentflow_test` confirmed present.

## Defects found and fixed during DB-backed execution

### 1. `list_open_slots` returned slots with live bookings
- **Root cause**: `DbBookingRepository.list_open_slots` query filtered only by `status='open'` on `availability_slots` but did not exclude slots that already had live bookings (`pending_confirmation`, `confirmed`, `reschedule_requested`, `checked_in`, `in_service`).
- **Impact**: Scenario B `select_slot` returned `SlotUnavailableOutcome` because the first doctor_anna consult slot was already occupied by seeded `bkg_sergey_pending`.
- **Fix**: Added `NOT EXISTS` subquery to `list_open_slots` SQL to exclude slots with live bookings.
- **File**: `app/infrastructure/db/booking_repository.py`

### 2. Stale `existing_booking_control` session shadowed new session
- **Root cause**: `start_new_existing_booking_session` created a new session without expiring prior active `existing_booking_control` sessions. With relative-date seed shifting, the seeded `bks_002` had `updated_at` in the future, so `_latest_for_route_types` picked the stale session instead of the new one.
- **Impact**: `confirm_existing_booking` returned `InvalidStateOutcome(reason='stale_or_mismatched_session')`.
- **Fix**: `start_new_existing_booking_session` now expires all active `existing_booking_control` sessions for the user before creating a new one.
- **File**: `app/application/booking/telegram_flow.py`

### 3. `list_active_sessions_for_telegram_user` included expired sessions
- **Root cause**: The active sessions query had no `expires_at` filter.
- **Fix**: Added `AND (expires_at IS NULL OR expires_at > now())` to the query.
- **File**: `app/infrastructure/db/booking_repository.py`

### 4. `_NoopOrchestration` in P0-07A test missing `expire_session`
- **Root cause**: The `_NoopOrchestration` stub in `test_p0_07a` did not have `expire_session`, causing `AttributeError` in `start_new_existing_booking_session`.
- **Fix**: Added `expire_session` stub to `_NoopOrchestration`.
- **File**: `tests/test_p0_07a_patient_read_surfaces_pre_live.py`

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
- `python -m compileall app tests scripts` → **passed**.
- `pytest -q tests/test_p0_07b1_booking_mutation_pre_live.py` → **1 passed in 9.09s**.
- `pytest -q tests/test_p0_07a_patient_read_surfaces_pre_live.py` → **1 passed in 9.53s**.
- `pytest -q tests/test_p0_06d2d2_db_backed_application_reads.py` → **1 passed in 6.39s**.
- `pytest -q tests/test_p0_06e4_integration_readiness_smoke.py` → **7 passed in 0.09s**.
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` → **9 passed in 1.59s**.
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` → **3 passed in 1.52s**.
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` → **4 passed in 1.40s**.
- `pytest -q tests -k "care or recommendation"` → **229 passed**.
- `pytest -q tests -k "patient and booking"` → **105 passed**.

## Grep checks (exact commands/results)
- `rg "IRINA-TREAT|doctor_irina|public_booking_enabled" app tests seeds docs/report` → confirms semantic coverage in app/tests/seeds.
- `rg "NoopOrchestration|_NoopOrchestration" tests/test_p0_07b1_booking_mutation_pre_live.py` → no matches (expected for mutation orchestration).
- `rg "DENTFLOW_TEST_DB_DSN|TEST_DB_DSN_ENV|run_seed_demo_bootstrap|safe_test_db_config" tests/test_p0_07b1_booking_mutation_pre_live.py` → DB harness/guard usage present.
- `rg "Actions:|Channel:|Канал:|source_channel|booking_mode|UTC|MSK|%Z|2026-04-" tests/test_p0_07b1_booking_mutation_pre_live.py` → negative-leakage assertions present.

## Defects found/fixed
- Fixed product/seed semantic mismatch: protected doctor access-code now works independently from public doctor list visibility.
- Fixed `list_open_slots` to exclude slots with live bookings via `NOT EXISTS` subquery.
- Fixed `start_new_existing_booking_session` to expire stale `existing_booking_control` sessions before creating new ones.
- Fixed `list_active_sessions_for_telegram_user` to filter out sessions past `expires_at`.
- Fixed `_NoopOrchestration` in P0-07A read test to include `expire_session` stub.

## Carry-forward for P0-07B2
- DB-backed recommendation action mutation.
- DB-backed care reserve mutation.
- DB-backed care repeat mutation.

## GO/NO-GO for P0-07B2
- **GO** — all DB-backed tests pass end-to-end with local PostgreSQL (`DENTFLOW_TEST_DB_DSN` active, no skips).
- All regression tests green (P0-07A, D2D2, E4, C4, B4, P0-05C, care/recommendation, patient/booking).
