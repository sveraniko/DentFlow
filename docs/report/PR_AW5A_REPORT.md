# PR AW-5A Report — Real Google Calendar Gateway + Human-Readable Event Rendering

## 1. Objective
Complete AW-5 by replacing fake production Google Calendar behavior with a real adapter path, wiring projector/runtime to use that path when integration is enabled, and ensuring calendar event content is human-readable without leaking raw localization keys.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/10_architecture.md
4. docs/12_repo_structure_and_code_map.md
5. docs/68_admin_reception_workdesk.md
6. docs/69_google_calendar_schedule_projection.md
7. docs/17_localization_and_i18n.md
8. docs/80_integrations_and_infra.md
9. docs/85_security_and_privacy.md
10. docs/90_pr_plan.md
11. docs/95_testing_and_launch.md
12. docs/report/PR_AW5_REPORT.md

## 3. Scope Implemented
- Added a real Google Calendar API gateway adapter (service-account based) with create/update/cancel behavior.
- Rewired projection runtime to use a real gateway factory when integration is enabled.
- Kept disabled/in-memory gateways for inert mode and tests.
- Implemented human-readable service label rendering with locale lookup and non-key fallback formatting.
- Added AW-5A tests for gateway path selection, inert disabled mode, and raw-title-key leak prevention.

## 4. Real Gateway Strategy
- Implemented `RealGoogleCalendarGateway` using Google Calendar v3 API with service-account credentials.
- Calls are performed via:
  - `events.insert` (create)
  - `events.patch` (update existing external event)
  - `events.delete` (cancel)
- Added `create_google_calendar_gateway(...)` factory:
  - disabled -> `DisabledGoogleCalendarGateway`
  - enabled + credentials path -> `RealGoogleCalendarGateway`
  - enabled + missing credentials -> `MisconfiguredGoogleCalendarGateway` (explicit failure signal)

## 5. Production Wiring Notes
- `GoogleCalendarScheduleProjector` now builds gateway instances via factory and integration config instead of hard-coded `DisabledGoogleCalendarGateway(enabled=True)` behavior.
- `scripts/process_outbox_events.py` and `scripts/retry_google_calendar_projection.py` now pass credential/application config into gateway factory.
- Projection failures remain non-blocking for DentFlow booking truth because mapping sync status captures failure while booking state is unchanged.

## 6. Human-Readable Rendering Strategy
- Calendar rendering path now resolves service labels with locale fallback order:
  1. preferred booking locale
  2. `ru`
  3. `en`
- If translation lookup misses, fallback now humanizes key-like text (`service.deep_cleaning` -> `Deep cleaning`) rather than leaking raw key.
- Repository now includes `service_locale` (clinic default locale fallback) so renderer has explicit locale input.

## 7. Files Added
- tests/test_google_calendar_projection_aw5a.py
- docs/report/PR_AW5A_REPORT.md

## 8. Files Modified
- app/config/settings.py
- app/integrations/google_calendar.py
- app/integrations/__init__.py
- app/projections/integrations/google_calendar_schedule_projector.py
- scripts/process_outbox_events.py
- scripts/retry_google_calendar_projection.py
- app/application/integration/google_calendar_projection.py
- app/infrastructure/db/google_calendar_projection_repository.py
- tests/test_google_calendar_projection_aw5.py
- pyproject.toml

## 9. Commands Run
- `pytest -q tests/test_google_calendar_projection_aw5.py tests/test_google_calendar_projection_aw5a.py`
- `pytest -q tests/test_db_bootstrap.py::test_aw5_google_calendar_projection_tables_declared`

## 10. Test Results
- `tests/test_google_calendar_projection_aw5.py` + `tests/test_google_calendar_projection_aw5a.py`: passed (`10 passed`)
- `tests/test_db_bootstrap.py::test_aw5_google_calendar_projection_tables_declared`: passed (`1 passed`)

## 11. Remaining Known Limitations
- Real gateway currently uses service-account credentials path and optional domain-wide delegation subject; no OAuth UI flow is added (out of scope).
- API client call timeout wiring is currently config-exposed but not passed into a custom HTTP transport (acceptable for AW-5A scope; can be hardened later).
- Event description status text remains raw status code (readable but not localized label mapping yet).

## 12. Deviations From Docs (if any)
- None intentional. DentFlow remains source of truth, Google Calendar remains one-way projection.

## 13. Readiness Assessment for AW-6
- AW-5A acceptance blockers are addressed:
  - real adapter path exists
  - production projector uses real adapter factory when enabled
  - raw service title keys no longer leak into event title path
  - projection failure handling remains isolated from booking truth
  - targeted tests pass
- This is ready for AW-6 without reopening AW-5 core boundaries.
