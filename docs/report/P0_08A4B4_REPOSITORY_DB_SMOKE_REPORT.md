# P0-08A4B4 — Repository DB Smoke Report

**Date:** 2026-04-29
**Executor:** Qoder (automated)
**Status:** **GO for P0-08A4C**

---

## Environment

| Item | Value |
|---|---|
| DENTFLOW_TEST_DB_DSN used | yes |
| DSN target | `postgresql+asyncpg://dentflow:dentflow@127.0.0.1:5432/dentflow_test` |
| Host safety | 127.0.0.1 (localhost only) |
| DB name safety | `dentflow_test` (contains "test") |
| DB test executed, not skipped | yes |
| No migrations created | yes |

## Bugs Found & Fixed

### 1. Bootstrap DDL ordering — FK to `booking.bookings` before table exists

`core_patient.pre_visit_questionnaires` had `REFERENCES booking.bookings(booking_id)` inline,
but `booking.bookings` is defined later in `STACK1_TABLES`. Caused `UndefinedTableError`.

**Fix:** Removed inline FK from column definition; added deferred `ALTER TABLE … ADD CONSTRAINT fk_pvq_booking` after `booking.bookings` is created. Idempotent (checks `information_schema.table_constraints`).

**File:** `app/infrastructure/db/bootstrap.py`

### 2. Media repository — NULL `created_at`/`updated_at` on insert

`upsert_media_asset` and `attach_media` passed raw `:created_at` / `:updated_at` to INSERT.
When caller omits timestamps (compat/legacy path), this violates NOT NULL constraint.

**Fix:** Changed VALUES clause to `COALESCE(:created_at, NOW())` / `COALESCE(:updated_at, NOW())`.

**File:** `app/infrastructure/db/media_repository.py`

### 3. Media repository — asyncpg ambiguous parameter type on nullable filters

`list_media_links` and `list_media_for_owner` used `(:role IS NULL OR role=:role)` pattern.
asyncpg cannot determine the type when the parameter is NULL.

**Fix:** Changed to `(CAST(:role AS TEXT) IS NULL OR role=:role)` and same for `:visibility`.

**File:** `app/infrastructure/db/media_repository.py`

### 4. B2 test fixture — missing `address_text` column

`_build_db_repo` in `test_p0_08a4b2` inserted into `core_reference.branches` without `address_text` (NOT NULL).

**Fix:** Added `address_text` column and value to the INSERT.

**File:** `tests/test_p0_08a4b2_pre_visit_questionnaire_repository.py`

### 5. B4 test — interface mismatches with actual repository

The original B4 test draft had:
- `get_patient_preferences(clinic_id=..., patient_id=...)` — method only accepts `patient_id`
- `update_branch_preferences(clinic_id=..., ...)` — method doesn't accept `clinic_id`
- `deactivate_relationship` returns `PatientRelationship | None`, test asserted `is True`
- Media repo methods (`list_media_links`, `set_primary_media`, `list_media_for_owner`) use keyword-only `*` args but test passed positional

**Fix:** Corrected all calls to match actual repository signatures.

**File:** `tests/test_p0_08a4b4_repository_db_smoke.py`

---

## Repository Smoke Results

| Area | Result |
|---|---|
| Profile details (upsert, get, completion state) | **PASS** |
| Relationships / family (upsert, list, deactivate, linked profiles) | **PASS** |
| Preferences (get, update notification, update branch) | **PASS** |
| Questionnaire (upsert, list, answers JSONB, complete, latest) | **PASS** |
| Questionnaire answers (upsert, list, delete, JSONB types) | **PASS** |
| Media assets (upsert, get, telegram lookup, list by IDs, compat) | **PASS** |
| Media links (attach, list, primary, remove, join) | **PASS** |
| Primary media invariant (set, missing link returns None, preserves) | **PASS** |
| Cross-repo compatibility checks | **PASS** |

## Regression Results

| Suite | Result |
|---|---|
| `test_p0_08a4b4_repository_db_smoke` | 1 passed |
| `test_p0_08a4b3_media_repository` | 8 passed |
| `test_p0_08a4b2_pre_visit_questionnaire_repository` | 8 passed |
| `test_p0_08a4b1_patient_profile_family_repositories` | 5 passed |
| `test_p0_08a4a_baseline_schema_models` | 6 passed |
| `test_p0_08a3_baseline_schema_contract_docs` | passed |
| `test_p0_08a2_db_service_gap_audit_docs` | passed |
| `test_p0_08a1_patient_profile_family_media_docs` | passed |
| `test_p0_07c_manual_pre_live_checklist` | passed |
| Total A-lane regressions | 24 passed |
| Broad: `care or recommendation` | 231 passed, 607 deselected |
| Broad: `patient and booking` | 105 passed, 733 deselected |

**Zero failures across all suites.**

---

## Verdict

**GO for P0-08A4C.**

All repository DB smoke tests pass against a real PostgreSQL instance. Bootstrap DDL ordering bug, media repository NULL-timestamp bug, and asyncpg parameter-type bug have been fixed. No migrations were created. No schema changes beyond the deferred FK constraint rewrite.
