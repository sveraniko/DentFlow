# PR OWN-A1B-2 Report — Owner care-commerce performance metrics panel

## What changed
Implemented a bounded owner-facing care-commerce performance panel focused on reserve/pickup operational status metrics (no revenue/payment analytics).

## Exact files changed
- app/application/owner/service.py
- app/application/owner/__init__.py
- app/interfaces/bots/owner/router.py
- locales/en.json
- locales/ru.json
- tests/test_owner_analytics_stack9a.py
- docs/report/PR_OWN_A1B_2_REPORT.md

## Command added
- `/owner_care`

Optional argument:
- `/owner_care <days>`

## Care metrics fields included
- orders_created_count
- orders_confirmed_count
- orders_ready_for_pickup_count
- orders_issued_count
- orders_fulfilled_count
- orders_canceled_count
- orders_expired_count
- active_orders_count
- active_reservations_count

## Data source and window behavior
- Data source:
  - `care_commerce.care_orders`
  - `care_commerce.care_reservations` (active reservations count)
- Window default: 7 days.
- Accepted window: 1..90 days.
- Invalid window: bounded localized error + usage hint.
- Clinic-local day semantics are applied via existing owner local-day helper.
- Windowed counts use clinic-local date conversion:
  - created count by `created_at`
  - confirmed count by `confirmed_at`
  - ready count by `ready_for_pickup_at`
  - issued count by `issued_at`
  - fulfilled count by `fulfilled_at`
  - canceled count by `canceled_at`
  - expired count by `expired_at`
- Active counts are operational “current state” snapshots:
  - active orders by active statuses in `care_orders`
  - active reservations by `care_reservations.status IN ('created','active')`

## Tests added/updated
Updated `tests/test_owner_analytics_stack9a.py` with focused coverage for:
- `/owner_care` owner-role guard.
- default 7-day window for `/owner_care`.
- explicit valid window parse for `/owner_care`.
- invalid window handling and usage hint for `/owner_care`.
- empty-state rendering for `/owner_care`.
- care metrics service query status counts.
- active orders/reservations counting.
- no revenue/payment labels in owner care output.
- non-regression check continuity for existing owner commands.

## Environment limitations
No environment limitation prevented targeted test execution for this PR slice.

## Explicit non-goals left for OWN-A1C
- No revenue metrics.
- No payment analytics.
- No owner governance shell.
- No owner AI summaries/Q&A.
- No care-commerce state machine redesign.
- No patient/admin/doctor operational flow changes.
- No migrations.
