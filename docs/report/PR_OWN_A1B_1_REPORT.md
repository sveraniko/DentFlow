# PR OWN-A1B-1 Report — Owner branch performance metrics panel

## What changed
Implemented a bounded owner-facing branch/location performance panel with no migrations and no BI/revenue scope expansion.

## Exact files changed
- app/application/owner/service.py
- app/application/owner/__init__.py
- app/interfaces/bots/owner/router.py
- locales/en.json
- locales/ru.json
- tests/test_owner_analytics_stack9a.py
- docs/report/PR_OWN_A1B_1_REPORT.md

## Command added
- `/owner_branches`

Optional argument:
- `/owner_branches <days>`

## Metrics fields included
- branch_id
- branch_label (optional, from `core_reference.branches.display_name` when available)
- bookings_created_count
- bookings_confirmed_count
- bookings_completed_count
- bookings_canceled_count
- bookings_no_show_count
- bookings_reschedule_requested_count

## Data source and window behavior
- Data source: bounded live/read query over `booking.bookings` (with optional branch label from `core_reference.branches`).
- No `owner_views.daily_branch_metrics` table was introduced.
- No migrations were added.
- Window default: 7 days.
- Accepted window: 1..90 days.
- Invalid window: bounded localized error + usage hint.
- Output rows bounded to max 10.
- Query window is clinic-local day bounded via the existing owner local-day helper.
- Aggregation uses booking lifecycle timestamps where available (`created_at`, `confirmed_at`, `completed_at`, `canceled_at`, `no_show_at`) and `status='reschedule_requested'` over `updated_at`.

## Tests added/updated
Updated `tests/test_owner_analytics_stack9a.py` with focused coverage for:
- `/owner_branches` owner-role guard.
- default 7-day window for `/owner_branches`.
- explicit valid window parse for `/owner_branches`.
- invalid window handling and usage hint for `/owner_branches`.
- empty-state rendering for `/owner_branches`.
- branch metrics service query bounded limit and aggregation behavior.
- branch label presence and fallback behavior (`branch_label is None` path).
- non-regression for existing `/owner_doctors` and `/owner_services` behavior.

## Environment limitations
No environment limitation prevented targeted test execution for this PR slice.

## Explicit non-goals left for OWN-A1B-2 and OWN-A1C
- No care-performance panel in this PR.
- No owner governance shell in this PR.
- No AI owner summaries/Q&A in this PR.
- No revenue/payment metrics in this PR.
- No branch projection table migration in this PR.
- No BI/dashboard framework redesign.
