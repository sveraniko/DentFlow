# DentFlow Live Pilot — Stack 3 Booking Smoke Report

**Date:** 2026-04-26  
**Base commit:** bef0707 (PR #178 — PILOT-A1C hardening merged)  
**Environment:** local, polling mode

---

## Summary Table

| Step | Result |
|------|--------|
| DB bootstrap | OK |
| seed-stack1 | OK |
| seed-stack2 | OK |
| seed-stack3 booking | OK (after fix) |
| smoke-import | OK |
| smoke-settings | OK |
| smoke-worker-modes | OK |
| smoke-dispatcher | OK |
| run-bootstrap | OK (clean exit) |
| worker startup (WORKER_MODE=all) | OK — projector + reminder both started |
| bot polling startup | OK — all 4 bots connected |
| Telegram role smoke | PENDING (manual step — see below) |

---

## Infrastructure

- Postgres: `dentflow_pg` Docker container, localhost:5432
- Redis: `dentflow_redis` Docker container, localhost:6379/0
- Python venv: `C:\Users\UraJura\DentFlow\.venv` (Python 3.13, restored manually)

---

## Seed Data Loaded

### Stack 1 (reference baseline)
```
clinics=1  branches=1  doctors=1  services=1  doctor_access_codes=1
actor_identities=3  telegram_bindings=3  staff_members=3
clinic_role_assignments=3  policy_sets=2  policy_values=3  feature_flags=1
```

### Stack 2 (patients)
```
patients=3  patient_contacts=1  patient_preferences=1  patient_flags=1
patient_photos=1  patient_medical_summaries=1  patient_external_ids=1
```

### Stack 3 (booking)
```
booking_sessions=1  session_events=1  availability_slots=1
slot_holds=1  bookings=1  booking_status_history=1
waitlist_entries=1  admin_escalations=1
```

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

## Blockers Found and Fixed

### 1. `booking_repository._seed_rows` — date/timestamp strings not coerced (HARD BLOCKER)

**File:** `app/infrastructure/db/booking_repository.py`  
**Root cause:** The `_seed_rows` function in `booking_repository.py` passed raw ISO string
values from the seed JSON directly to asyncpg for `DATE` and `TIMESTAMPTZ` columns.
asyncpg requires native `datetime.date` / `datetime.datetime` objects, not strings.

Columns affected:
- `requested_date` (DATE) → needed `date.fromisoformat()`
- `expires_at`, `created_at`, `updated_at`, `start_at`, `end_at`, `scheduled_start_at`,
  `scheduled_end_at`, `occurred_at` (TIMESTAMPTZ) → needed `datetime.fromisoformat()`

**Fix:**
- Added `_coerce_seed_value(col, value)` helper with suffix-based rule:
  any column ending in `_at` is coerced via `datetime.fromisoformat(value.replace("Z", "+00:00"))`
- `requested_date` matched by explicit `_SEED_DATE_COLUMNS` set
- JSONB columns (payload_json, service_scope, date_window, payload_summary) serialized via `json.dumps`
- Replaced static INSERT with dynamic INSERT (omit `None`-valued non-PK columns so DB DEFAULT applies)

### 2. `tzdata` missing from venv — projector worker timezone crash (WORKER BLOCKER)

**File:** `pyproject.toml`  
**Root cause:** Windows has no system timezone database. Python's `zoneinfo` module
requires the `tzdata` pip package. Without it, `ZoneInfo('Europe/Berlin')` raises
`ZoneInfoNotFoundError` at runtime, causing the projector worker to fail on every
event batch that involves timezone conversion.

**Fix:** Installed `tzdata` into venv; added `"tzdata>=2024.1"` to `pyproject.toml`
dependencies so future venv setups include it automatically.

---

## Telegram Command Smoke (Manual — Next Step)

In Telegram, test each bot in order:

| Bot | Commands |
|-----|----------|
| Patient `@Dent_Flow_bot` | `/start` → tap **Записаться на приём** |
| Admin `@Dentflow_admin_bot` | `/admin_today`, `/admin_patients`, `/admin_integrations` |
| Doctor `@Dentflow_doctor_bot` | `/today_queue` |
| Owner `@Dentflow_owner_bot` | `/owner_today`, `/owner_doctors`, `/owner_staff` |

Do not run destructive actions during first smoke.

---

## Next Actions

1. Complete manual Telegram role smoke above and record results
2. Commit `booking_repository.py` fix + `pyproject.toml` tzdata addition to repo
3. After booking smoke passes — run `seed_stack3_booking.py` with realistic future dates
   for a live booking flow test (current seed uses 2026-04-20 which is in the past)
