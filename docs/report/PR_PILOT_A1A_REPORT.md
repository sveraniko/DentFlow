# PR PILOT-A1A Report — Live bot startup entrypoint and launch env sanity

## What changed
- Added explicit application startup mode selection through `APP_RUN_MODE` with two bounded modes:
  - `bootstrap` (default): build runtime registry + dispatcher only.
  - `polling`: build runtime + start real aiogram polling for configured bots.
- Added bounded launch settings sanity validation with fast-fail checks.
- Kept import safety: importing `app.main` does not start polling.
- Added startup logging for selected mode and configured bot roles (without secrets).
- Updated `.env.example` to reflect current launch, integrations, and worker knobs used by runtime.
- Added Makefile launch targets for bootstrap, polling bots, and explicit worker modes.
- Added focused startup/launch tests and env/Makefile contract checks.

## Exact files changed
- `app/main.py`
- `app/config/settings.py`
- `.env.example`
- `Makefile`
- `tests/test_startup_launch_pilot_a1a.py`
- `docs/report/PR_PILOT_A1A_REPORT.md`

## Startup modes added
- `APP_RUN_MODE=bootstrap`
  - validates baseline launch settings
  - builds `RuntimeRegistry`
  - builds dispatcher
  - exits after logging readiness
- `APP_RUN_MODE=polling`
  - validates strict launch settings (including all bot tokens)
  - builds `RuntimeRegistry`
  - starts `Dispatcher.start_polling(...)` with all four role tokens as bot instances

## Env sanity rules
Validation helper checks:
- Always required:
  - `DB_DSN`
  - `REDIS_URL`
  - `APP_DEFAULT_LOCALE`
  - `APP_DEFAULT_TIMEZONE`
- In `polling` mode additionally required and non-placeholder:
  - `TELEGRAM_PATIENT_BOT_TOKEN`
  - `TELEGRAM_CLINIC_ADMIN_BOT_TOKEN`
  - `TELEGRAM_DOCTOR_BOT_TOKEN`
  - `TELEGRAM_OWNER_BOT_TOKEN`
- Placeholder values (e.g. `replace_me`) fail fast.
- Errors are explicit and do not print token secret values.

## Makefile targets added/updated
Added/updated bounded launch targets:
- `run-bootstrap`
- `run-bots`
- `run-worker-projector`
- `run-worker-reminder`
- `run-worker-all`

Backward compatibility:
- `run-app` remains available and now aliases `run-bootstrap`.
- `run-worker` remains available.

## Tests added/updated
Added `tests/test_startup_launch_pilot_a1a.py` to cover:
1. importing `app.main` does not start polling,
2. bootstrap mode builds dispatcher without polling,
3. polling mode rejects placeholder/missing tokens,
4. validation error messages do not leak token values,
5. unsupported `APP_RUN_MODE` fails clearly,
6. `.env.example` includes current launch/worker/integration keys,
7. `Makefile` contains expected launch targets,
8. no migration directories/files were introduced.

## Environment limits
- Full test suite was not required for this bounded PR.
- Focused target tests were run for startup/launch behavior.

## Explicit non-goals deferred
Deferred for subsequent phases:
- **PILOT-A1B**
  - webhook deployment mode,
  - broader runtime topology redesign,
  - canned scenario/e2e launch packs.
- **PILOT-A2**
  - broader pilot hardening program,
  - product feature expansion,
  - migration/schema changes.
