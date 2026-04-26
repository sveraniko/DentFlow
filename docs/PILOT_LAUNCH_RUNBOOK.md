# DentFlow Pilot Launch Runbook (PILOT-A1B)

## 1) Required environment checklist
- Copy `.env.example` to `.env` and set real values.
- Security: never commit `.env`, never include `.env` in zip archives/reports sent to tools, and rotate Telegram bot tokens immediately if `.env` was shared.
- Required launch keys:
  - `APP_RUN_MODE=bootstrap|polling`
  - `APP_DEFAULT_LOCALE`, `APP_DEFAULT_TIMEZONE`
  - `DB_DSN`
  - `REDIS_URL`
- Polling-only keys (must be real, not placeholders):
  - `TELEGRAM_PATIENT_BOT_TOKEN`
  - `TELEGRAM_CLINIC_ADMIN_BOT_TOKEN`
  - `TELEGRAM_DOCTOR_BOT_TOKEN`
  - `TELEGRAM_OWNER_BOT_TOKEN`
- Worker selector:
  - `WORKER_MODE=projector|reminder|all`

## 2) DB/bootstrap steps
1. `make db-bootstrap`
2. Optional seed for demo baselines: `make seed-stack1` and `make seed-stack2`
3. Run `make smoke-dispatcher` to confirm registry/dispatcher build.

## 3) Redis requirement
- Redis must be reachable before bot and worker start.
- Verify URL in `.env` (`REDIS_URL`) and run `make smoke-settings`.

## 4) Bot startup
### Bootstrap mode (safe preflight)
- `make run-bootstrap`
- Expected: runtime initializes and exits without polling.

### Polling mode (live bot runtime)
- `make run-bots`
- Expected: polling starts only after smoke checks pass.

## 5) Worker startup
- Projector only: `make run-worker-projector`
- Reminder only: `make run-worker-reminder`
- Combined local mode: `make run-worker-all`

## 6) First smoke commands per role
- Patient role readiness: `make smoke-launch` then verify patient token configured in `make smoke-settings` output.
- Admin role readiness: `make smoke-launch` then verify clinic_admin token configured.
- Doctor role readiness: `make smoke-launch` then verify doctor token configured.
- Owner role readiness: `make smoke-launch` then verify owner token configured.

## 7) Integration toggles
- Calendar mirror:
  - `INTEGRATIONS_GOOGLE_CALENDAR_ENABLED=true|false`
  - Keep false unless credentials + subject email are set.
- Sheets/catalog sync:
  - `INTEGRATIONS_GOOGLE_SHEETS_ENABLED=true|false`
  - Enable only for controlled import windows.

## 8) Stop/rollback basics
- Stop bot/worker processes with `CTRL+C` (graceful stop path).
- Roll back to bootstrap-only mode by setting `APP_RUN_MODE=bootstrap`.
- Disable integrations by setting related `INTEGRATIONS_*_ENABLED=false`.
- If polling is unhealthy, stop polling and keep only smoke/bootstrap checks active.

## 9) Known limitations
- No webhook deployment path yet.
- No patient-facing public docs yet.
- No staff mutation/offboarding operations yet.
- No full worker liveness dashboard yet.
