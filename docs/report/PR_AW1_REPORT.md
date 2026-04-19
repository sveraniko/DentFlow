# PR AW-1 Report — Admin Workdesk Foundation + Read Models

## 1. Objective
Build the foundational admin/reception operational read-model backbone for AW-2+: explicit `admin_views` tables, local-day-aware operational semantics, typed read services, event-driven projection updates, a rebuild path, and tests.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/10_architecture.md
4. docs/12_repo_structure_and_code_map.md
5. docs/25_state_machines.md
6. docs/30_data_model.md
7. docs/35_event_catalog.md
8. docs/50_analytics_and_owner_metrics.md
9. docs/68_admin_reception_workdesk.md
10. docs/69_google_calendar_schedule_projection.md
11. docs/16_unified_card_system.md
12. docs/16-1_card_profiles.md
13. docs/16-2_card_callback_contract.md
14. docs/16-3_card_media_and_navigation_rules.md
15. docs/16-4_booking_card_profile.md
16. docs/16-5_card_runtime_state_and_redis_rules.md
17. docs/70_bot_flows.md
18. docs/72_admin_doctor_owner_ui_contracts.md
19. docs/80_integrations_and_infra.md
20. docs/85_security_and_privacy.md
21. docs/90_pr_plan.md
22. docs/95_testing_and_launch.md
23. docs/report/PR_STACK_8A_REPORT.md
24. docs/report/PR_STACK_8A1_REPORT.md
25. docs/report/PR_STACK_9A_REPORT.md
26. docs/report/PR_UC3B_REPORT.md

## 3. Precedence Decisions
- Kept DentFlow canonical transactional tables as truth (`booking.*`, `communication.*`, `care_commerce.*`, `core_patient.*`, `core_reference.*`) and treated `admin_views.*` strictly as derived operational projections.
- Implemented admin workdesk data backbone without UI expansion (AW-2+ intentionally out of scope).
- Implemented local-day semantics with explicit timezone precedence: branch timezone -> clinic timezone -> app default.
- Used event-driven incremental projector updates where practical; used bounded rebuild strategy for full repair/recovery.

## 4. Admin Read-Model Schema Summary
Added `admin_views` schema and projection tables:
- `admin_views.today_schedule`
- `admin_views.confirmation_queue`
- `admin_views.reschedule_queue`
- `admin_views.waitlist_queue`
- `admin_views.care_pickup_queue`
- `admin_views.ops_issue_queue`

Also added queue-oriented indexes for clinic/day/branch/status lookups and severity/priority ordering.

## 5. Local-Day / Timezone Strategy
- Projection SQL computes local date/time using `AT TIME ZONE COALESCE(branch.timezone, clinic.timezone, :app_default_timezone)`.
- Read service computes “today” using branch-aware timezone resolution first, with clinic/app fallback.
- Admin “today” filtering is based on local dates in read models, not raw UTC day slicing.

## 6. Read Service Strategy
Implemented explicit typed service:
- `AdminWorkdeskReadService.get_today_schedule(...)`
- `AdminWorkdeskReadService.get_confirmation_queue(...)`
- `AdminWorkdeskReadService.get_reschedule_queue(...)`
- `AdminWorkdeskReadService.get_waitlist_queue(...)`
- `AdminWorkdeskReadService.get_care_pickup_queue(...)`
- `AdminWorkdeskReadService.get_ops_issue_queue(...)`

Service returns typed dataclass DTO rows (no raw tuple interface) and supports clinic/branch/doctor/status/day filtering where relevant.

## 7. Projection / Update Strategy
Implemented:
- `AdminWorkdeskProjector` (outbox projector) for event-driven refreshes.
- `AdminWorkdeskProjectionStore` for projection population and targeted refresh operations.

Event handling coverage:
- `booking.*` -> refresh booking-derived workdesk views + issue queue refresh.
- `waitlist.*` -> refresh affected waitlist queue row.
- `care_order.*` -> refresh affected care pickup row.
- `reminder.*` with `booking_id` -> refresh booking-derived views + issue queue refresh.

## 8. Rebuild / Repair Path
Added deterministic rebuild script:
- `scripts/rebuild_admin_projections.py`

Rebuild behavior:
1. Truncate all `admin_views.*` tables.
2. Recompute all admin projections from canonical transactional tables.
3. Return per-table row counts.

## 9. Files Added
- `app/application/admin/__init__.py`
- `app/application/admin/workdesk.py`
- `app/projections/admin/__init__.py`
- `app/projections/admin/workdesk_projector.py`
- `scripts/rebuild_admin_projections.py`
- `tests/test_admin_workdesk_aw1.py`
- `docs/report/PR_AW1_REPORT.md`

## 10. Files Modified
- `app/infrastructure/db/bootstrap.py`
- `scripts/process_outbox_events.py`
- `tests/test_db_bootstrap.py`

## 11. Commands Run
- `python -m py_compile app/application/admin/workdesk.py app/projections/admin/workdesk_projector.py scripts/rebuild_admin_projections.py scripts/process_outbox_events.py tests/test_admin_workdesk_aw1.py`
- `pytest -q tests/test_admin_workdesk_aw1.py tests/test_db_bootstrap.py tests/test_event_projection_stack8a.py`

## 12. Test Results
- `13 passed` for AW-1 targeted tests + bootstrap + projector regression test subset.

## 13. Known Limitations / Explicit Non-Goals
- No admin Telegram UI/workdesk rendering implemented in this PR.
- No Google Calendar integration/sync implemented.
- Ops issue queue currently includes baseline reminder failure + confirmation no-response issue families; broader issue taxonomy can expand in AW-2+.
- Rebuild script is full refresh (truncate/recompute), not per-tenant partial rebuild orchestration yet.

## 14. Deviations From Docs (if any)
- None intentional. Scope stayed on admin read-model backbone and avoided AW-2 UI expansion.

## 15. Readiness Assessment for AW-2
AW-2-ready data backbone is in place:
- explicit admin workdesk read tables,
- branch-aware local-day semantics,
- typed read services,
- event projector update strategy,
- rebuild/repair path,
- tests covering core behavior.

This enables AW-2 UI/workdesk surfaces to consume stable operational read models instead of ad hoc transactional queries.
