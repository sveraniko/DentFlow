# PR Stack 9A Report — Owner Analytics Baseline

## 1. Objective
Implement the first owner-facing analytics and monitoring baseline on top of event/projection foundations: projection tables, daily clinic/doctor/service metrics, live owner snapshot, bounded anomaly candidates, owner bot surfaces, replay/rebuild path, and tests.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/10_architecture.md
4. docs/12_repo_structure_and_code_map.md
5. docs/50_analytics_and_owner_metrics.md
6. docs/35_event_catalog.md
7. docs/25_state_machines.md
8. docs/20_domain_model.md
9. docs/30_data_model.md
10. docs/15_ui_ux_and_product_rules.md
11. docs/17_localization_and_i18n.md
12. docs/22_access_and_identity_model.md
13. docs/23_policy_and_configuration_model.md
14. docs/70_bot_flows.md
15. docs/72_admin_doctor_owner_ui_contracts.md
16. docs/80_integrations_and_infra.md
17. docs/85_security_and_privacy.md
18. docs/90_pr_plan.md
19. docs/95_testing_and_launch.md
20. docs/report/PR_STACK_8A_REPORT.md
21. docs/report/PR_STACK_8A1_REPORT.md

## 3. Precedence Decisions
- Kept owner analytics strictly projection-based (`owner_views.*` + `analytics_raw.event_ledger`) per README + development rules.
- Did not implement AI owner interpretation layer in this stack.
- Did not introduce revenue metrics due lack of canonical billing/payment truth.
- Used bounded direct canonical queries only for live `/owner_today` snapshot counts.

## 4. Owner Projection Schema Summary
Added owner projection/read-model tables in bootstrap baseline:
- `owner_views.daily_clinic_metrics`
- `owner_views.daily_doctor_metrics`
- `owner_views.daily_service_metrics`
- `owner_views.owner_alerts`

Also added dedupe index for open alerts:
- `uq_owner_alerts_open_dedupe` partial unique index on open alerts by clinic/type/date/entity scope.

## 5. Metrics Semantics Summary
- Date buckets are clinic-local dates resolved from clinic timezone.
- Daily clinic metrics include patient/booking/reminder/chart/encounter baseline counts.
- Doctor metrics are derived via booking-linked doctor dimensions and encounter payload doctor_id.
- Service metrics are derived via booking-linked service dimensions.
- No financial/revenue metrics introduced.

## 6. Projector Strategy
Implemented `OwnerDailyMetricsProjector` consuming outbox events with idempotent upsert counters.
Supported event families:
- `patient.*` (baseline `patient.created` increment)
- `booking.*` for key booking transitions
- `reminder.*` for scheduled/sent/ack/failed
- `chart.opened`
- `encounter.created`

Projector updates owner metric tables and refreshes bounded alert candidates per affected local date.

## 7. Alert/Anomaly Strategy
Implemented threshold-based, explainable, bounded alerts:
- `low_confirmation_rate`
- `no_show_spike`
- `reminder_failure_spike`
- `open_confirmation_backlog`

Deduping approach:
- open-alert partial unique index
- update existing open alert row for same clinic/type/date/entity before insert

No AI interpretation text generation implemented.

## 8. Owner Bot Surface Scope
Implemented minimal owner-only Telegram commands:
- `/owner_digest`
- `/owner_today`
- `/owner_alerts`
- `/owner_alert_open <owner_alert_id>`

Characteristics:
- owner-role access guard
- RU/EN localized compact summaries
- no raw chart note or sensitive clinical text exposure

## 9. Replay/Rebuild Strategy
Two rebuild paths are available:
1. Outbox replay path: reset `owner.daily_metrics` checkpoint and process outbox.
2. Event ledger rebuild path: `scripts/rebuild_owner_projections.py` truncates owner projections and recomputes from `analytics_raw.event_ledger`.

## 10. Files Added
- `app/projections/owner/daily_metrics_projector.py`
- `app/application/owner/service.py`
- `scripts/rebuild_owner_projections.py`
- `tests/test_owner_analytics_stack9a.py`
- `docs/report/PR_STACK_9A_REPORT.md`

## 11. Files Modified
- `app/infrastructure/db/bootstrap.py`
- `app/bootstrap/runtime.py`
- `app/interfaces/bots/owner/router.py`
- `app/application/owner/__init__.py`
- `app/projections/owner/__init__.py`
- `scripts/process_outbox_events.py`
- `tests/test_db_bootstrap.py`
- `locales/en.json`
- `locales/ru.json`

## 12. Commands Run
- `pytest -q tests/test_owner_analytics_stack9a.py tests/test_db_bootstrap.py tests/test_runtime_wiring.py`

## 13. Test Results
- Passed: owner analytics stack tests, db bootstrap assertions, runtime wiring tests.

## 14. Known Limitations / Explicit Non-Goals
- No AI narrative/interpretation layer.
- No revenue/billing analytics.
- Alert thresholds are intentionally simple baseline heuristics.
- Backlog alert currently uses booking schedule-day count and does not yet include branch-specific timezone variation.

## 15. Deviations From Docs (if any)
- None intentional. Kept scope bounded to owner analytics baseline and monitoring surfaces.

## 16. Readiness Assessment for Next Stack
Ready for next stack to add:
- richer owner drill-downs by doctor/service/branch,
- alert lifecycle controls (ack/resolve flows),
- optional AI interpretation layer over these projections,
- improved data quality/freshness telemetry on owner surfaces.
