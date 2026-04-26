# DentFlow Live Pilot Start Report

**Date:** 2026-04-26  
**Environment:** local, polling mode  
**Prepared by:** pilot launch automation

---

## Summary

| Step | Result |
|------|--------|
| env prepared | yes (no secrets in this report) |
| DB bootstrap | OK |
| smoke-import | OK |
| smoke-settings | OK |
| smoke-worker-modes | OK |
| smoke-dispatcher | OK |
| run-bootstrap | OK (clean exit) |
| worker startup | OK (WORKER_MODE=all, separate process) |
| run-bots (polling) | OK — all four bots connected |
| Telegram command smoke | PENDING (manual step) |

---

## Infrastructure

- Postgres: `dentflow_pg` Docker container, localhost:5432, db=dentflow
- Redis: `dentflow_redis` Docker container, localhost:6379/0
- Python venv: `C:\Users\UraJura\DentFlow\.venv` (Python 3.13, deps installed directly)

---

## Bots Connected (polling)

| Role | Bot username | Telegram ID |
|------|-------------|-------------|
| patient | @Dent_Flow_bot | 8443139395 |
| clinic_admin | @Dentflow_admin_bot | 7842974313 |
| doctor | @Dentflow_doctor_bot | 7710694449 |
| owner | @Dentflow_owner_bot | 8625714373 |

Token values not included in this report.

---

## Seed Data Loaded

- Stack 1: clinics=1, branches=1, doctors=1, services=1, doctor_access_codes=1,
  actor_identities=3, telegram_bindings=3, staff_members=3, clinic_role_assignments=3,
  policy_sets=2, policy_values=3, feature_flags=1
- Stack 2: patients=3, patient_contacts=1, patient_preferences=1, patient_flags=1,
  patient_photos=1, patient_medical_summaries=1, patient_external_ids=1
- Stack 3 (booking): not run (optional, skipped for first smoke)

---

## Blockers Found and Fixed

### 1. pydantic-settings sub-model env_file missing (HARD BLOCKER)
**File:** `app/config/settings.py`  
**Problem:** All nested `BaseSettings` sub-models (`TelegramConfig`, `DatabaseConfig`, etc.)
lacked `env_file=".env"` in their `model_config`. They only read from OS env vars, not
the `.env` file, causing token validation failure on every sub-model instantiation.  
**Fix:** Added `env_file=".env", env_file_encoding="utf-8"` to all 10 sub-config classes.

### 2. `make_patient_router()` called with `recommendation_delivery_service` kwarg (HARD BLOCKER)
**File:** `app/bootstrap/runtime.py` line ~227  
**Problem:** `RuntimeRegistry.build_dispatcher()` passed `recommendation_delivery_service=`
to `make_patient_router()`, which does not accept that parameter.  
**Fix:** Removed the extra kwarg from the call. The delivery service is instantiated in
`RuntimeRegistry` and available for future use.

### 3. Seed `_seed_rows`: list/dict values not JSON-serialized for JSONB columns
**File:** `app/infrastructure/db/repositories.py`  
**Problem:** JSONB columns (`service_scope`, `branch_scope`, `value_json`, etc.) received
raw Python lists/dicts/strings — asyncpg rejected them.  
**Fix 1:** Changed to dynamic INSERT (omitting None-valued columns so DB DEFAULT applies).  
**Fix 2:** Added `_SEED_JSONB_COLUMNS` set; columns in that set are always `json.dumps`-encoded.

### 4. Seed `_seed_rows`: NOT NULL columns with DB DEFAULT still fail when NULL passed explicitly
**File:** `app/infrastructure/db/repositories.py`  
**Problem:** Seed JSON omitted fields like `status`, `scope_type`, `is_active` that have
`NOT NULL DEFAULT '...'` in schema. Passing `None` explicitly overrides the DB default.  
**Fix:** Dynamic INSERT excludes None-valued non-PK columns from the INSERT statement,
letting DB defaults apply for absent seed fields.

### 5. `persist_patient`: birth_date string not coerced to `datetime.date`
**File:** `app/infrastructure/db/patient_repository.py`  
**Problem:** Seed JSON passes `"1988-04-11"` (str) for `DATE` column; asyncpg requires
a `datetime.date` object.  
**Fix:** Added `date.fromisoformat()` coercion in `persist_patient` when value is a string.

### 6. `persist_preferences`: `contact_time_window` dict not JSON-serialized
**File:** `app/infrastructure/db/patient_repository.py`  
**Problem:** JSONB column `contact_time_window` received a raw Python dict from `asdict()`.  
**Fix:** Added explicit `json.dumps()` coercion before the insert.

### 7. `seed_stack2_patients`: `persist_flag()` called without required `event_name` kwarg
**File:** `app/infrastructure/db/patient_repository.py` (seed_stack2_patients function)  
**Problem:** `persist_flag()` requires `event_name` as keyword-only argument, but the
seed loop omitted it.  
**Fix:** Added `event_name="patient.flag_set"` to the call.

### 8. `pyproject.toml`: missing `[tool.hatch.build.targets.wheel] packages` declaration
**File:** `pyproject.toml`  
**Problem:** `pip install -e .` and `pip install .` fail because hatchling cannot discover
the `app` package (no packages declaration, no `src/` layout).  
**Fix (workaround):** Installed all dependencies directly by name. The Makefile runs
`python -m app.main` from project root — no package install required for runtime.  
**Recommended fix:** Add `[tool.hatch.build.targets.wheel] packages = ["app"]` to `pyproject.toml`.

---

## Telegram Command Smoke (Manual — Next Step)

Test in Telegram after confirming bots are live:

| Bot | Commands to test |
|-----|-----------------|
| Patient `@Dent_Flow_bot` | `/start` |
| Admin `@Dentflow_admin_bot` | `/admin_today`, `/admin_integrations`, `/admin_calendar` |
| Doctor `@Dentflow_doctor_bot` | `/today_queue` |
| Owner `@Dentflow_owner_bot` | `/owner_today`, `/owner_doctors`, `/owner_staff` |

Do not run destructive actions during first smoke.

---

## Next Fixes Recommended

1. Fix `pyproject.toml` — add `packages = ["app"]` under `[tool.hatch.build.targets.wheel]`
2. Register `patient_recommendation_delivery_service` properly in `make_patient_router` if
   it needs to be used for patient-facing delivery triggers
3. Provide seed Stack 3 booking data after Telegram smoke passes
4. Consider adding `env_file` support note to project README so future developers don't
   hit the same pydantic-settings sub-model issue
