# PR PW-3 Report — Lag Visibility + Recovery Hardening

## 1. Objective
Implement bounded projector-runtime hardening so DentFlow projections are inspectable, failure-visible, and operationally recoverable for pilot use without rewriting worker architecture.

## 2. Docs Read
1. `README.md`
2. `docs/10_architecture.md`
3. `docs/18_development_rules_and_baseline.md`
4. `docs/35_event_catalog.md`
5. `docs/50_analytics_and_owner_metrics.md`
6. `docs/68_admin_reception_workdesk.md`
7. `docs/69_google_calendar_schedule_projection.md`
8. `docs/80_integrations_and_infra.md`
9. `docs/90_pr_plan.md`
10. `docs/95_testing_and_launch.md`
11. `docs/report/PR_PW1_REPORT.md`
12. `docs/report/PR_PW2_REPORT.md`
13. `docs/report/FULL_PROJECT_STATE_AUDIT.md`

## 3. Scope Implemented
- Added projector lag/freshness status service with outbox-tail and per-projector checkpoint lag visibility.
- Added coherent projector failure recording into `system_runtime.projector_failures` with projector identity + event context.
- Added bounded retry operation that safely rewinds one projector checkpoint to `failed_event_id - 1` and requeues the outbox event.
- Added operational CLI tooling for status/failure inspection and retry.
- Polished replay script to validate projector names and support explicit checkpoint set.
- Added/strengthened tests for lag visibility, failure tracking, checkpoint safety, retry after fix, and replay coherence behavior.

## 4. Lag Visibility Strategy
- Implemented `ProjectorOperationsService.lag_status()` that reports:
  - current outbox tail event id,
  - per-projector last processed outbox event id (checkpoint),
  - lag in events (`tail - checkpoint`),
  - freshness delay in seconds based on outbox produced timestamps where available.
- Exposed runtime operational visibility through `scripts/projector_ops.py status`.
- Kept scope bounded to machine-readable operational JSON (no dashboard build).

## 5. Failure Tracking Strategy
- Extended runtime failure path to record failure rows in `system_runtime.projector_failures` via `ProjectorCheckpointRepository.record_failure(...)`.
- Each failure row now carries:
  - projector name,
  - failed outbox event id,
  - event id,
  - error text,
  - failed timestamp (table default).
- Runtime continues to mark outbox event failed and does **not** advance failing projector checkpoint.
- Repeated failures remain visible as additional failure rows (bounded observability).

## 6. Retry/Recovery Strategy
- Added `ProjectorOperationsService.retry_failed_event(...)`:
  - rewinds specific projector checkpoint to `max(0, outbox_event_id - 1)`,
  - marks outbox event as `pending`,
  - returns structured operation result.
- Added `scripts/projector_ops.py retry <projector_name> <outbox_event_id>` for operator-safe retry.
- Kept behavior bounded and explicit (no unbounded auto-retry loops).

## 7. Rebuild/Replay Notes
- Existing rebuild scripts remain canonical for full projection rebuilds:
  - `scripts/rebuild_admin_projections.py`
  - `scripts/rebuild_owner_projections.py`
  - `scripts/rebuild_search_projections.py`
- Replay polish:
  - `scripts/replay_projector.py` now validates projector names against runtime registry.
  - Added `--to-event-id` to set checkpoint deterministically for bounded replay scenarios.
- Operational flow is now:
  1. inspect lag/status (`projector_ops.py status`),
  2. inspect failures (`projector_ops.py failures`),
  3. retry failed event or set checkpoint intentionally,
  4. fallback to full rebuild script when needed.

## 8. Files Added
- `app/projections/runtime/operations.py`
- `scripts/projector_ops.py`
- `docs/report/PR_PW3_REPORT.md`

## 9. Files Modified
- `app/infrastructure/outbox/repository.py`
- `app/projections/runtime/projectors.py`
- `app/projections/runtime/__init__.py`
- `scripts/replay_projector.py`
- `tests/test_projector_worker_pw1.py`
- `tests/test_event_projection_stack8a.py`

## 10. Commands Run
- `pytest -q tests/test_projector_worker_pw1.py tests/test_event_projection_stack8a.py`
- `pytest -q tests/test_worker.py`

## 11. Test Results
- `pytest -q tests/test_projector_worker_pw1.py tests/test_event_projection_stack8a.py` -> `10 passed`
- `pytest -q tests/test_worker.py` -> `2 passed`

## 12. Remaining Known Limitations
- Lag visibility is event-count/time-delay based and does not yet expose percentiles or per-event-name lag buckets.
- Retry tooling is operator-invoked and bounded; no automatic exponential backoff queue per projector is added.
- Runtime still uses polling batches; this PR intentionally avoids distributed processing redesign.

## 13. Pilot Readiness Assessment
- PW-3 hardening goal is met with bounded scope:
  - projection lag is inspectable,
  - failures are projector-attributed and auditable,
  - retry/recovery path is explicit and checkpoint-safe,
  - replay operations are less tribal and more deterministic,
  - regression tests cover key hardening behaviors.
- This materially improves pilot operational trust while preserving existing worker architecture.
