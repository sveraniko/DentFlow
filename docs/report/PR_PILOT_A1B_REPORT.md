# PR PILOT-A1B Report — Smoke scripts, launch checks, and pilot runbook baseline

## What changed after PILOT-A1A
- Added bounded smoke scripts for import checks, safe settings visibility, dispatcher construction, and worker mode validation.
- Added launch-smoke Makefile targets and an aggregate `smoke-launch` pipeline.
- Added a practical pilot launch runbook focused on environment checklist, startup order, role-based smoke, and rollback basics.
- Added focused tests to lock smoke script safety, Makefile targets, runbook presence/content, README pointer, and migration absence.

## Exact files changed
- `scripts/smoke_import_app.py`
- `scripts/smoke_settings.py`
- `scripts/smoke_dispatcher.py`
- `scripts/smoke_worker_modes.py`
- `Makefile`
- `docs/PILOT_LAUNCH_RUNBOOK.md`
- `README.md`
- `tests/test_pilot_smoke_scripts_a1b.py`
- `docs/report/PR_PILOT_A1B_REPORT.md`

## Smoke scripts added
- `smoke_import_app.py`: verifies core modules import safely without starting polling.
- `smoke_settings.py`: loads settings and prints sanitized launch summary without secrets; validates polling token placeholders.
- `smoke_dispatcher.py`: attempts `RuntimeRegistry + dispatcher` construction and prints bounded guidance on failure.
- `smoke_worker_modes.py`: validates `WORKER_MODE` contract and parses worker config helpers without running forever loops.

## Makefile targets added
- `smoke-import`
- `smoke-settings`
- `smoke-dispatcher`
- `smoke-worker-modes`
- `smoke-launch` (ordered safe chain)

## Runbook contents summary
`docs/PILOT_LAUNCH_RUNBOOK.md` includes:
1. required env checklist,
2. DB/bootstrap steps,
3. Redis requirement,
4. bot startup (bootstrap + polling),
5. worker startup (projector/reminder/all),
6. first smoke commands per role,
7. integration toggles,
8. stop/rollback basics,
9. known limitations.

## Tests added/updated
- Added `tests/test_pilot_smoke_scripts_a1b.py` with focused static checks for scripts/docs/Makefile/README and migration absence.

## Environment limits
- Full integration runtime (DB/Redis-backed dispatcher build and live polling) was not executed in unit tests.
- Tests are intentionally bounded to static compile/content contract checks for this launch-readiness PR.

## Explicit non-goals left for PILOT-A2
- Canned role scenario runner.
- Live Telegram API smoke execution.
- Webhook deployment path.
- Docker compose/runtime topology overhaul.
- Full E2E framework.
- Schema migrations.
