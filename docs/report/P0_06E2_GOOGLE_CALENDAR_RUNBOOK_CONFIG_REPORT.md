# P0-06E2 — Google Calendar Integration Runbook + Env/Config Verification Report

## Summary

P0-06E2 scope is implemented:
- Added a dedicated Google Calendar projection runbook.
- Verified integration env/config coverage in docs, `.env.example`, and tests.
- Added no-live-API tests for gateway factory behavior (disabled/misconfigured/real/in-memory paths).
- Updated integration and seed docs for operator clarity.
- Corrected P0-06E1 matrix inconsistency by separating acceptance lane vs broader non-acceptance selector run.

## Files changed

- `docs/runbooks/google_calendar_projection_runbook.md` (new)
- `docs/80_integrations_and_infra.md` (updated)
- `docs/92_seed_data_and_demo_fixtures.md` (updated)
- `docs/p0-06e1-matrix.md` (updated)
- `tests/test_p0_06e2_google_calendar_runbook_config.py` (new)

## Runbook created

Created:
- `docs/runbooks/google_calendar_projection_runbook.md`

Coverage includes:
- Purpose and truth boundary.
- One-way DentFlow -> Google Calendar projection.
- Forbidden/non-goal list (no Calendar-to-DentFlow sync, no availability truth, no two-way sync).
- Required env variables.
- Google setup checklist.
- Calendar ID mapping model and fallback caveat.
- Admin/operator commands and surfaces.
- Operational flow.
- Troubleshooting checklist.
- Safety and privacy notes.

## Env/config verification

Documented and verified keys:
- `INTEGRATIONS_GOOGLE_CALENDAR_ENABLED`
- `INTEGRATIONS_GOOGLE_CALENDAR_CREDENTIALS_PATH`
- `INTEGRATIONS_GOOGLE_CALENDAR_SUBJECT_EMAIL`
- `INTEGRATIONS_GOOGLE_CALENDAR_APPLICATION_NAME`
- `INTEGRATIONS_GOOGLE_CALENDAR_TIMEOUT_SEC`
- `INTEGRATIONS_DENTFLOW_BASE_URL`

Validation method:
- Static key presence checks in `.env.example` + runbook.
- Parsing checks through `IntegrationsConfig` in tests.

## Gateway behavior (no live API calls)

Verified in `tests/test_p0_06e2_google_calendar_runbook_config.py`:

- Disabled path:
  - `create_google_calendar_gateway(enabled=False, ...)` returns `DisabledGoogleCalendarGateway`.
  - `upsert_event(...)` raises `google_calendar_integration_disabled`.
- Enabled without credentials:
  - returns `MisconfiguredGoogleCalendarGateway`.
  - `upsert_event(...)` raises `google_calendar_credentials_path_required`.
- Enabled with credentials path:
  - returns `RealGoogleCalendarGateway`.
  - test does not call `_get_service` and does not hit Google API.
- In-memory gateway:
  - upsert returns event id.
  - cancel removes event from in-memory store.

## Admin/operator commands

Documented surfaces:
- `/admin_calendar`
- `/admin_integrations`

Documented worker/retry commands:
- `python scripts/process_outbox_events.py --limit 200`
- `python scripts/retry_google_calendar_projection.py --limit 100`
- `python scripts/retry_google_calendar_projection.py --booking-id <booking_id>`

## Truth boundary

Explicitly documented and verified:
- DentFlow is booking truth.
- Google Calendar is mirror/projection.
- No Calendar-to-DentFlow sync in baseline.
- No two-way sync claim as a positive capability.

## Access/credentials model

Documented:
- Service account JSON path via env/runtime secret storage.
- Optional subject email for domain-wide delegation/impersonation.
- Calendar sharing/delegation requirements.
- No claim of automatic calendar creation.

## Troubleshooting checklist

Included runbook checks for:
- `google_calendar_integration_disabled`
- `google_calendar_credentials_path_required`
- `google_calendar_dependencies_missing`
- Google API 403 / sharing/delegation issues
- wrong calendar id / fallback id caveat
- mapping missing
- worker not running
- outbox backlog
- timezone mismatch
- service-account subject/delegation confusion

## E1 matrix correction status

Updated `docs/p0-06e1-matrix.md` to:
- keep acceptance lane clear: `patient and booking (E1 acceptance command): 105 passed`.
- retain broader run result as non-acceptance classification:
  - `pytest -q -k "patient or booking"` -> `343 passed, 5 failed, 407 deselected`
  - explicitly labeled broader non-E1 acceptance selection.

## Tests run with exact commands/results

- `python -m compileall app tests scripts` -> PASS
- `pytest -q tests/test_p0_06e2_google_calendar_runbook_config.py` -> initial FAIL (1 failed, 10 passed), then PASS (11 passed) after runbook phrase correction
- `pytest -q tests/test_google_calendar_projection_aw5.py` -> PASS (7 passed)
- `pytest -q tests/test_google_calendar_projection_aw5a.py` -> PASS (4 passed)
- `pytest -q tests/test_admin_calendar_awareness_s13a.py` -> PASS (7 passed)
- `pytest -q tests/test_admin_integrations_s13c.py` -> PASS (4 passed)
- `pytest -q tests/test_p0_06e1_care_catalog_sheets_template.py` -> PASS (5 passed)
- `pytest -q tests/test_p0_06d2c_seed_demo_bootstrap.py` -> PASS (9 passed)
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` -> PASS (9 passed)
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` -> PASS (3 passed)
- `pytest -q tests -k "care or recommendation"` -> PASS (227 passed, 539 deselected, 2 warnings)
- `pytest -q tests -k "patient and booking"` -> PASS (105 passed, 661 deselected, 2 warnings)

DB lane note:
- No DB-dependent command in this E2 task list required `DENTFLOW_TEST_DB_DSN`; no DB skip occurred in the executed E2 command set.

## Grep checks with exact commands/results

- `rg "Google Calendar|one-way|mirror|source of truth|Calendar-to-DentFlow|admin_calendar|retry_google_calendar_projection" docs/runbooks docs/80_integrations_and_infra.md tests/test_p0_06e2_google_calendar_runbook_config.py`
  - Result: runbook/docs/tests include truth-boundary and operator command coverage.

- `rg "INTEGRATIONS_GOOGLE_CALENDAR" .env.example app/config/settings.py docs/runbooks tests/test_p0_06e2_google_calendar_runbook_config.py`
  - Result: keys present in `.env.example`, settings model, runbook, and tests.

- `rg "two-way sync|Calendar edits update DentFlow|Calendar is source of truth" docs/runbooks docs/80_integrations_and_infra.md`
  - Result: no direct positive-claim matches (exit code 1; expected for this literal pattern set).

- `rg "343 passed|5 failed|patient or booking|patient and booking" docs/p0-06e1-matrix.md docs/report/P0_06E1_CARE_CATALOG_GOOGLE_SHEETS_TEMPLATE_REPORT.md`
  - Result: acceptance result shown as 105 passed; broader 343/5 run retained and explicitly contextualized in matrix.

## Defects found/fixed

- Defect: runbook initially missed exact phrase token expected by new test (`not booking truth` / exact `one-way` form).
  - Fix: runbook wording normalized to include expected truth-boundary strings.
- Defect: E1 matrix mixed targeted acceptance and broader selector outcome without explicit classification.
  - Fix: acceptance row corrected and broader run labeled non-E1 acceptance selection.

## Carry-forward for P0-06E3

- Patients/doctors/services Sheets templates/manual import docs remain next-scope items.
- Reuse this runbook/test pattern for E3 truth-boundary and command-contract checks.

## GO / NO-GO recommendation for E3

Recommendation: **GO**.

Rationale:
- E2 acceptance scope is documented and tested.
- Truth boundary is explicit and guarded by tests.
- No live Google API dependencies introduced in tests.
- Regression lanes requested in scope pass.
