# PR 12B-3 Report — Convergence guardrails + outdated-claim cleanup

## What changed

- Hardened `tests/test_worker.py::test_worker_bootstrap` to monkeypatch `build_reminder_worker_services(...)` directly with a fake `ReminderWorkerServices` instance, removing unit coupling to real DB bootstrap/repository load paths.
- Preserved bootstrap behavior assertions in the same test:
  - logging setup is called,
  - reminder services are built,
  - worker tasks still execute in sequence (`heartbeat`, `reminder_delivery`, `reminder_recovery`).
- Added explicit worker mode dispatch coverage for `WORKER_MODE=all`.
- Kept projector/reminder/invalid dispatch coverage in focused unit tests.
- Added bounded outdated-claim notices at the top of legacy audit docs to prevent stale planning drift and point to the current source of truth.

## Exact files changed

- `tests/test_worker.py`
- `docs/report/FULL_PROJECT_STATE_AUDIT.md`
- `docs/redis_audit_2026-04-19.md`
- `docs/report/PR_12B3_REPORT.md`

## Runtime impact

- Runtime production code behavior: **unchanged**.
- This PR changes **tests/docs only**.

## Tests added/updated

- Updated: `tests/test_worker.py`
  - `test_worker_bootstrap` no longer relies on live DB bootstrap paths.
  - `test_worker_mode_dispatch_projector`
  - `test_worker_mode_dispatch_reminder`
  - `test_worker_mode_dispatch_all` (added)
  - `test_worker_mode_dispatch_invalid`

## Migrations

- No migrations were added.

## Environment / execution notes

- Targeted unit tests were executed for this bounded PR scope.
- No environment limitation blocked the targeted test run.

## Convergence pack status

- **12B convergence pack is complete after this PR**, with acceptance criteria satisfied for:
  - worker bootstrap unit seam decoupled from DB bootstrap,
  - mode dispatch coverage for projector/reminder/all/invalid,
  - stale legacy audit claims explicitly superseded and redirected to the delta audit source of truth,
  - no runtime behavior changes,
  - no migrations.
