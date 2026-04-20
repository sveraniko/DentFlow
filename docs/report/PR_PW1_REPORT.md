# PR PW-1 Report — Projector Worker Runtime Foundation

## 1. Objective
Build a production-usable projector worker runtime foundation so projection freshness no longer relies mainly on manual scripts. The scope is runtime convergence: explicit registry, bounded polling loop, checkpoint-aware execution, startup catch-up, graceful shutdown, runtime wiring, and tests.

## 2. Docs Read
Read in requested order:
1. `README.md`
2. `docs/10_architecture.md`
3. `docs/18_development_rules_and_baseline.md`
4. `docs/30_data_model.md`
5. `docs/35_event_catalog.md`
6. `docs/50_analytics_and_owner_metrics.md`
7. `docs/68_admin_reception_workdesk.md`
8. `docs/69_google_calendar_schedule_projection.md`
9. `docs/80_integrations_and_infra.md`
10. `docs/85_security_and_privacy.md`
11. `docs/90_pr_plan.md`
12. `docs/95_testing_and_launch.md`
13. `docs/report/PR_STACK_8A_REPORT.md`
14. `docs/report/PR_STACK_8A1_REPORT.md`
15. `docs/report/PR_STACK_9A_REPORT.md`
16. `docs/report/FULL_PROJECT_STATE_AUDIT.md`

## 3. Scope Implemented
- Added explicit projector registry abstraction with explicit registration entries.
- Added projector worker runtime loop with bounded batches and polling interval.
- Added startup catch-up phase (bounded by configurable max catch-up batches).
- Added graceful shutdown semantics via stop event and signal handlers.
- Wired runtime worker entrypoint (`app/worker.py`) to run projector runtime continuously.
- Routed one real existing projector through runtime worker foundation (`analytics.event_ledger`).
- Added behavioral tests for registry, bounded loop behavior, checkpoint safety, startup catch-up, shutdown boundary safety, and real projector execution through runtime path.

## 4. Registry Strategy
- Implemented explicit `ProjectorRegistry` + `RegisteredProjector` with factory-based projector construction.
- No implicit module scanning.
- Added `build_default_projector_registry()` that currently registers:
  - `analytics.event_ledger` (`AnalyticsEventLedgerProjector`)

This keeps PW-1 focused on infrastructure convergence while proving real runtime execution with one existing projector.

## 5. Worker Loop Strategy
- Introduced `ProjectorWorkerRuntime` with config:
  - `batch_limit`
  - `poll_interval_sec`
  - `startup_catchup_max_batches`
- Runtime uses `ProjectorRunner.run_once(limit=batch_limit)` repeatedly.
- Loop is bounded and idle-safe:
  - no unbounded tight spin
  - sleeps by waiting on stop event with poll timeout
- `ProjectorRunner.run_once` now returns `ProjectorRunResult` including:
  - `scanned_events`
  - per-projector handled counts
  - optional failed outbox event id

## 6. Startup Catch-Up Notes
- On worker start, runtime runs catch-up batches before steady-state polling.
- Catch-up exits when:
  - no events scanned,
  - failure happens in a batch, or
  - configured max catch-up batch count reached.
- This allows restart continuity from persisted checkpoints without assuming projections are already fresh.

## 7. Shutdown Safety Notes
- Runtime uses an explicit stop event and signal handlers (`SIGINT`, `SIGTERM` where supported).
- Shutdown happens at safe boundary:
  - current batch is allowed to complete,
  - no false checkpoint advancement beyond what the runner confirms.
- Runner behavior preserves checkpoint safety:
  - checkpoints save only after projector handle success,
  - failed events are marked failed and batch stops.

## 8. Runtime Wiring Notes
- `app/worker.py` main path now calls `run_worker_forever()` instead of one-shot execution.
- Projector runtime wiring is explicit and production-usable in worker entrypoint.
- Runtime env knobs added:
  - `PROJECTOR_WORKER_ENABLED` (default enabled)
  - `PROJECTOR_WORKER_BATCH_LIMIT`
  - `PROJECTOR_WORKER_POLL_INTERVAL_SEC`
  - `PROJECTOR_WORKER_STARTUP_CATCHUP_MAX_BATCHES`

## 9. Example Projector Wiring
- Real existing projector wired via runtime registry:
  - `AnalyticsEventLedgerProjector` as `analytics.event_ledger`.
- Behavioral test verifies the default registered projector runs through the new worker runtime foundation.

## 10. Files Added
- `app/projections/runtime/registry.py`
- `app/projections/runtime/worker.py`
- `tests/test_projector_worker_pw1.py`
- `docs/report/PR_PW1_REPORT.md`

## 11. Files Modified
- `app/projections/runtime/projectors.py`
- `app/projections/runtime/__init__.py`
- `app/worker.py`
- `tests/test_event_projection_stack8a.py`

## 12. Commands Run
- `find . -maxdepth 3 -type f | head -n 200`
- `rg -n "projector|projection|outbox|checkpoint|event" ...`
- `pytest -q tests/test_event_projection_stack8a.py tests/test_projector_worker_pw1.py tests/test_worker.py`

## 13. Test Results
- `pytest -q tests/test_event_projection_stack8a.py tests/test_projector_worker_pw1.py tests/test_worker.py`
  - Passed (9 tests).

## 14. Remaining Known Limitations
- Only one projector is intentionally wired via default runtime registry in PW-1.
- Other existing projectors are still primarily script-driven and should be incrementally moved in PW-2.
- No projector lag/readiness health gate added yet (not required for PW-1 scope).

## 15. Readiness Assessment for PW-2
- PW-1 establishes core runtime substrate needed for broader projector convergence:
  - explicit registry,
  - managed loop,
  - bounded batch control,
  - checkpoint-aware restart continuity,
  - graceful stop boundary.
- System is now ready for PW-2 incremental projector onboarding with lower operational freshness risk.
