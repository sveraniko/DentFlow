# PR AW-5 Report — Google Calendar Schedule Projection

## 1. Objective
Implement a bounded, one-way DentFlow -> Google Calendar schedule projection for admin/reception visual mirror usage, with explicit booking/event mapping, local-time-aware rendering, privacy-bounded event content, and retry/failure handling.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/10_architecture.md
4. docs/12_repo_structure_and_code_map.md
5. docs/68_admin_reception_workdesk.md
6. docs/69_google_calendar_schedule_projection.md
7. docs/25_state_machines.md
8. docs/35_event_catalog.md
9. docs/80_integrations_and_infra.md
10. docs/85_security_and_privacy.md
11. docs/90_pr_plan.md
12. docs/95_testing_and_launch.md
13. docs/report/PR_AW1_REPORT.md
14. docs/report/PR_AW2_REPORT.md
15. docs/report/PR_AW3_REPORT.md
16. docs/report/PR_AW4_REPORT.md

## 3. Precedence Decisions
- Preserved DentFlow booking state as canonical truth; Google Calendar remains derived projection only.
- Implemented one-way projector behavior from booking outbox events to Google Calendar integration layer.
- Used explicit integration mapping table; no fuzzy matching by event title/description.
- Followed timezone fallback order branch -> clinic -> app default for calendar event projection.

## 4. Calendar Segmentation Strategy
- Implemented the preferred baseline: **one target calendar per doctor**.
- Added explicit doctor->calendar mapping table `integration.google_calendar_doctor_calendars`.
- If doctor mapping is absent, repository falls back to deterministic `doctor_<doctor_id>` target key to keep projection behavior bounded/testable.

## 5. Mapping Strategy
- Added canonical mapping table `integration.google_calendar_booking_event_map` keyed by `booking_id` and storing:
  - `target_calendar_id`
  - `external_event_id`
  - `sync_status`
  - `sync_attempts`
  - `payload_hash`
  - `last_error_text`
  - `last_synced_at`
- Mapping writes are explicit and updateable for create/update/cancel/retry paths.

## 6. Projection Behavior Notes
- `booking.*` outbox events are consumed by `GoogleCalendarScheduleProjector`.
- Projection behavior in `GoogleCalendarProjectionService`:
  - visible status create/update (`pending_confirmation`, `confirmed`, `reschedule_requested`, `checked_in`, `in_service`, `completed`, `no_show`)
  - canceled booking triggers event cancel and mapping state transition to `canceled`
  - payload hash dedupe prevents unnecessary updates
- Added `booking.rescheduled` outbox event emission in booking orchestration reschedule flow.

## 7. Event Rendering / Privacy Notes
- Calendar title is compact: `HH:MM • <masked patient> • <service>`.
- Patient name is masked to first name + initial where possible (`Anna Petrova` -> `Anna P.`).
- Description includes only bounded operational fields:
  - DentFlow booking reference
  - status
  - doctor
  - branch
  - DentFlow return-path URL
- No chart text, diagnosis, treatment details, or reminder internals included.

## 8. Local-Time Notes
- Timezone resolved with SQL fallback chain:
  - `COALESCE(branch.timezone, clinic.timezone, app_default_timezone)`
- Rendered local start/end values use resolved timezone via `zoneinfo` conversion before projection payload generation.

## 9. Failure/Retry Strategy
- Projection failures do not mutate booking truth and do not block booking transitions.
- Mapping row stores failure visibility (`sync_status='failed'|'cancel_failed'`, `last_error_text`, attempts).
- Added bounded retry script `scripts/retry_google_calendar_projection.py`:
  - retries by explicit booking id or oldest failed mappings.

## 10. Files Added
- app/application/integration/google_calendar_projection.py
- app/infrastructure/db/google_calendar_projection_repository.py
- app/integrations/google_calendar.py
- app/projections/integrations/__init__.py
- app/projections/integrations/google_calendar_schedule_projector.py
- scripts/retry_google_calendar_projection.py
- tests/test_google_calendar_projection_aw5.py
- docs/report/PR_AW5_REPORT.md

## 11. Files Modified
- app/application/booking/orchestration.py
- app/application/integration/__init__.py
- app/config/settings.py
- app/infrastructure/db/bootstrap.py
- app/integrations/__init__.py
- scripts/process_outbox_events.py
- tests/test_booking_orchestration.py
- tests/test_db_bootstrap.py

## 12. Commands Run
- `pytest -q tests/test_google_calendar_projection_aw5.py tests/test_db_bootstrap.py tests/test_booking_orchestration.py tests/test_event_projection_stack8a.py` (initial run with failures in existing booking test fake tx contract)
- `pytest -q tests/test_google_calendar_projection_aw5.py tests/test_db_bootstrap.py tests/test_booking_orchestration.py`

## 13. Test Results
- Final targeted run passed: `35 passed`.
- Added AW-5 behavioral coverage for mapping, create/update/cancel, local-time rendering, privacy-bounded payload, and failure+retry flow.

## 14. Known Limitations / Explicit Non-Goals
- No bidirectional Calendar -> DentFlow editing.
- No direct Google API credential exchange or OAuth setup in this PR.
- Projector is gated by `integrations.google_calendar_enabled`; when disabled it is intentionally inert.
- No Calendar UI surface in Telegram added here (projection backend only).

## 15. Deviations From Docs (if any)
- No intentional deviations from the stated AW-5 scope docs.

## 16. Readiness Assessment for AW-6
- AW-5 baseline is in place: explicit mapping, one-way projection semantics, local-time/privacy discipline, and retry visibility.
- AW-6 can focus on hardening: real Google API adapter wiring, richer observability/metrics, and operational tooling (rebuild/replay dashboards) without revisiting truth boundaries.
