# PR WR-1 Report — Worker Topology Contract + Reminder Worker Runtime

## 1. Objective
Make production worker topology explicit and implement a real continuous reminder worker runtime so reminder delivery/recovery is no longer operationally ambiguous or one-shot driven.

## 2. Docs Read
Read in requested order:
1. `README.md`
2. `docs/10_architecture.md`
3. `docs/18_development_rules_and_baseline.md`
4. `docs/35_event_catalog.md`
5. `docs/68_admin_reception_workdesk.md`
6. `docs/69_google_calendar_schedule_projection.md`
7. `docs/80_integrations_and_infra.md`
8. `docs/85_security_and_privacy.md`
9. `docs/90_pr_plan.md`
10. `docs/95_testing_and_launch.md`
11. `docs/report/PR_PW1_REPORT.md`
12. `docs/report/PR_PW2_REPORT.md`
13. `docs/report/PR_PW3_REPORT.md`
14. `docs/report/FULL_PROJECT_STATE_AUDIT.md`

## 3. Scope Implemented
- Added explicit worker topology contract document with production/deployment runtime expectations.
- Added reminder worker runtime loop with bounded polling, bounded startup catch-up, and graceful shutdown boundaries.
- Added explicit reminder and projector worker entrypoint modules.
- Updated worker module to support explicit worker mode dispatch (`projector`, `reminder`, `all`) while preserving one-shot helper path for dev/tests.
- Added behavioral WR-1 tests for reminder runtime catch-up, bounded loop behavior, graceful shutdown, and worker entrypoint mode dispatch.

## 4. Worker Topology Strategy
- Topology now documents two canonical continuous worker lines:
  - projector worker line;
  - reminder worker line.
- Production guidance is explicit: run bot runtime + projector worker + reminder worker as separate processes/services.
- `run_worker_once()` remains available as a one-shot utility path, but is explicitly non-canonical for production.

## 5. Reminder Worker Runtime Strategy
- Implemented `ReminderWorkerRuntime` and `ReminderWorkerRunner`.
- Runtime executes reminder delivery and recovery in bounded per-batch limits.
- Runtime loop is polling-based with sleep-on-idle behavior (stop-event-aware wait).
- No hidden dependency on manual one-shot helper for production continuity.

## 6. EntryPoint / Deployment Notes
Explicit entrypoints now exist:
- `python -m app.projector_worker` for projector runtime.
- `python -m app.reminder_worker` for reminder runtime.
- `python -m app.worker` remains available with explicit `WORKER_MODE` dispatch.

Deployment expectation documented:
- `app.main` for bot interface runtime,
- projector worker process for projection freshness,
- reminder worker process for reminder continuity.

## 7. Startup Catch-Up Notes
- Reminder worker performs bounded startup catch-up before steady-state polling.
- Catch-up exits when backlog is drained (zero processed), stop requested, or max catch-up batches reached.
- This ensures due reminder backlog is handled after restarts without operator/manual intervention.

## 8. Shutdown Notes
- Reminder worker installs signal handlers where supported (`SIGINT`, `SIGTERM`).
- Shutdown occurs at safe batch boundary:
  - active batch completes,
  - no new batch starts after stop signal.
- This avoids fake-success semantics for partially processed loops.

## 9. Files Added
- `app/infrastructure/workers/reminder_runtime.py`
- `app/projector_worker.py`
- `app/reminder_worker.py`
- `docs/81_worker_topology_and_runtime.md`
- `tests/test_reminder_worker_wr1.py`
- `docs/report/PR_WR1_REPORT.md`

## 10. Files Modified
- `app/worker.py`
- `tests/test_worker.py`

## 11. Commands Run
- `rg --files`
- `sed -n '1,220p' README.md`
- `sed -n '1,220p' docs/10_architecture.md`
- `sed -n '1,220p' docs/18_development_rules_and_baseline.md`
- `sed -n '1,220p' docs/35_event_catalog.md`
- `sed -n '1,240p' docs/68_admin_reception_workdesk.md`
- `sed -n '1,260p' docs/69_google_calendar_schedule_projection.md`
- `sed -n '1,220p' docs/80_integrations_and_infra.md`
- `sed -n '1,220p' docs/85_security_and_privacy.md`
- `sed -n '1,240p' docs/90_pr_plan.md`
- `sed -n '1,240p' docs/95_testing_and_launch.md`
- `sed -n '1,260p' docs/report/PR_PW1_REPORT.md`
- `sed -n '1,260p' docs/report/PR_PW2_REPORT.md`
- `sed -n '1,280p' docs/report/PR_PW3_REPORT.md`
- `sed -n '1,320p' docs/report/FULL_PROJECT_STATE_AUDIT.md`
- `pytest -q tests/test_worker.py tests/test_reminder_worker_wr1.py tests/test_projector_worker_pw1.py tests/test_reminder_delivery_stack4b1.py tests/test_reminder_recovery_stack4c1.py`

## 12. Test Results
- `pytest -q tests/test_worker.py tests/test_reminder_worker_wr1.py tests/test_projector_worker_pw1.py tests/test_reminder_delivery_stack4b1.py tests/test_reminder_recovery_stack4c1.py` -> `30 passed`

## 13. Remaining Known Limitations
- Reminder worker runtime remains single-process polling without distributed lease/leader election (intentionally out of WR-1 scope).
- Combined `WORKER_MODE=all` is provided for convenience; production recommendation remains separate worker processes.
- Advanced duplicate-prevention sophistication is deferred to WR-2.

## 14. Readiness Assessment for WR-2
WR-1 goals are met:
- worker topology is explicitly documented,
- reminder runtime is an explicit continuous production path,
- projector vs reminder worker entrypoints are explicit,
- reminder startup catch-up and graceful shutdown boundaries are implemented,
- behavioral tests cover the new runtime path and mode dispatch.

System is ready for WR-2 hardening work focused on duplicate prevention / leasing sophistication.
