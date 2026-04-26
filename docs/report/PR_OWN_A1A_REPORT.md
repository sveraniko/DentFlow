# PR OWN-A1A Report — Owner doctor and service metrics panels

## What changed
Implemented bounded owner-facing doctor/service performance panels on top of existing owner projection tables.

## Exact files changed
- app/application/owner/service.py
- app/application/owner/__init__.py
- app/interfaces/bots/owner/router.py
- locales/en.json
- locales/ru.json
- tests/test_owner_analytics_stack9a.py
- docs/report/PR_OWN_A1A_REPORT.md

## Commands added
- `/owner_doctors`
- `/owner_services`

Optional argument:
- `/owner_doctors <days>`
- `/owner_services <days>`

## Metrics fields included
### Doctor panel
- doctor_id
- bookings_created_count
- bookings_confirmed_count
- bookings_completed_count
- bookings_no_show_count
- bookings_reschedule_requested_count
- reminders_sent_count
- reminders_failed_count
- encounters_created_count

### Service panel
- service_id
- bookings_created_count
- bookings_confirmed_count
- bookings_completed_count
- bookings_no_show_count
- bookings_reschedule_requested_count

## Window/limit behavior
- Default window: 7 days.
- Accepted window: 1..90 days.
- Invalid window: localized bounded error + usage hint.
- Result rows are bounded to max 10.
- Aggregation is projection-based over:
  - `owner_views.daily_doctor_metrics`
  - `owner_views.daily_service_metrics`

## Tests added/updated
Updated `tests/test_owner_analytics_stack9a.py` with focused coverage for:
- owner guards for new commands
- default/explicit window parsing
- invalid window behavior
- empty-state rendering
- doctor/service metrics aggregation + bounded limit behavior
- non-regression checks for `/owner_today` and `/owner_digest`

## Environment limitations
No environment limitations prevented targeted test execution.

## Explicit non-goals left for OWN-A1B and OWN-A1C
- No branch metrics panel in this PR.
- No care-performance panel in this PR.
- No owner governance shell in this PR.
- No AI owner summaries in this PR.
- No revenue/payment metrics in this PR.
- No broad owner projection redesign in this PR.
- No migrations.
