# PR_PW2_REPORT

## 1. Objective
Wire the key existing projectors into the projector worker runtime introduced in PW-1 so core derived operational and analytics layers stay fresh automatically via outbox-driven processing.

## 2. Docs Read
1. README.md
2. docs/10_architecture.md
3. docs/18_development_rules_and_baseline.md
4. docs/35_event_catalog.md
5. docs/50_analytics_and_owner_metrics.md
6. docs/68_admin_reception_workdesk.md
7. docs/69_google_calendar_schedule_projection.md
8. docs/80_integrations_and_infra.md
9. docs/90_pr_plan.md
10. docs/95_testing_and_launch.md
11. docs/report/PR_PW1_REPORT.md
12. docs/report/PR_STACK_8A_REPORT.md
13. docs/report/PR_STACK_8A1_REPORT.md
14. docs/report/PR_STACK_9A_REPORT.md
15. docs/report/PR_AW1_REPORT.md
16. docs/report/PR_AW2_REPORT.md
17. docs/report/PR_AW3_REPORT.md
18. docs/report/PR_AW4_REPORT.md
19. docs/report/PR_AW5_REPORT.md
20. docs/report/PR_AW5A_REPORT.md
21. docs/report/FULL_PROJECT_STATE_AUDIT.md

## 3. Scope Implemented
- Extended the default projector registry to include PW-2 key projectors.
- Kept worker runtime architecture from PW-1 intact (no new queue/distributed bus abstractions).
- Added/updated tests to verify key projector registration and execution through worker path.

## 4. Wired Projectors List
The default runtime registry now wires:
- `analytics.event_ledger` -> `AnalyticsEventLedgerProjector`
- `admin.workdesk` -> `AdminWorkdeskProjector`
- `owner.daily_metrics` -> `OwnerDailyMetricsProjector`
- `integrations.google_calendar_schedule` -> `GoogleCalendarScheduleProjector`
- `search.patient_projection` -> `PatientSearchProjector`

## 5. Admin Views Freshness Notes
- Admin workdesk projector is now part of the default worker projector registry.
- Booking, waitlist, care order, and reminder event handling in `AdminWorkdeskProjector` now flows through the live worker path (instead of relying on standalone/manual projection-only scripts).
- This covers today schedule, confirmations, reschedules, waitlist, care pickup, and ops issue queue freshness.

## 6. Owner Views Freshness Notes
- Owner daily metrics projector is now wired in the runtime registry and receives outbox events in worker batches.
- This keeps clinic-level, doctor-level, and service-level daily metrics and owner alerts updated via the worker pipeline.

## 7. Calendar Projection Freshness Notes
- Google Calendar schedule projector is now wired in the default worker projector registry.
- It remains one-way projection and configuration-gated by integration settings.
- Booking truth remains DentFlow canonical; projection failures remain isolated from booking state.

## 8. Search Projector Notes
- Patient incremental search projector is wired in the default worker registry.
- This was included because the patient search projector already existed as an accepted event-driven projector and fits the PW-2 scope.

## 9. Files Added
- `docs/report/PR_PW2_REPORT.md`

## 10. Files Modified
- `app/projections/runtime/registry.py`
- `tests/test_projector_worker_pw1.py`

## 11. Commands Run
- `pytest -q tests/test_projector_worker_pw1.py tests/test_event_projection_stack8a.py tests/test_admin_workdesk_aw1.py tests/test_owner_analytics_stack9a.py tests/test_google_calendar_projection_aw5.py tests/test_google_calendar_projection_aw5a.py`

## 12. Test Results
- Targeted PW-2 projector wiring and dependent projector tests passed (`27 passed`).

## 13. Remaining Known Limitations
- Worker runtime still processes outbox in polling batches; no advanced distribution/observability hardening was added in this PR (explicitly out of PW-2 scope).
- Calendar projection behavior remains integration-config-gated and requires credentials/config to perform real external calls.
- This PR does not add new projector families; it only wires already existing key projectors.

## 14. Readiness Assessment for PW-3
- PW-2 objective is met for live wiring of key projectors in worker runtime.
- Core derived layers (admin, owner, analytics ledger, calendar projection, and patient search incremental projection) now have default runtime registration.
- The codebase is ready for PW-3 hardening work (operational robustness, observability depth, and runtime tuning) without reworking projector selection/wiring.
