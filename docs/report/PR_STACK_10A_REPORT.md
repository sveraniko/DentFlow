# PR Stack 10A Report — Recommendation Engine Baseline

## 1. Objective
Implement the first canonical recommendation layer with explicit recommendation truth, lifecycle, doctor issuance, patient response baseline, trigger-based issuance path, outbox events, and the carry-forward 9A local-day backlog fix.

## 2. Docs Read
Read and applied guidance from:
- `README.md`
- `docs/18_development_rules_and_baseline.md`
- `docs/20_domain_model.md`
- `docs/25_state_machines.md`
- `docs/30_data_model.md`
- `docs/35_event_catalog.md`
- `docs/50_analytics_and_owner_metrics.md`
- `docs/70_bot_flows.md`
- `docs/72_admin_doctor_owner_ui_contracts.md`
- `docs/report/PR_STACK_9A_REPORT.md`

## 3. Precedence Decisions
- Implemented recommendation as a dedicated first-class context (`recommendation.recommendations`) instead of overloading reminders or chart notes.
- Used canonical recommendation lifecycle states from state machine/event catalog docs.
- Added explicit bounded enums for recommendation type and source kind.
- Kept care-commerce out of scope; only future-compatible hooks were retained via structured type/source fields.

## 4. Recommendation Schema Summary
- Added schema namespace: `recommendation`.
- Added canonical table: `recommendation.recommendations` with required linkage fields (clinic/patient/booking/encounter/chart), source/type, status, lifecycle timestamps, and audit timestamps.
- Added supporting indexes for patient, booking, and chart query paths.

## 5. Lifecycle Strategy
- Canonical states supported: `draft`, `prepared`, `issued`, `viewed`, `acknowledged`, `accepted`, `declined`, `expired`, `withdrawn`.
- Transition guard map implemented in application service.
- Patient actions are bounded and idempotent enough for repeated clicks (`accept`/`decline`/`acknowledge`/`view`).
- Invalid transitions raise controlled `ValueError` and are surfaced safely in handlers.

## 6. Doctor-Issued Flow Scope
- Added doctor command flow: `/recommend_issue <patient_id> <type> <booking_id|-> <title|body>`.
- Flow validates doctor access to booking/patient context and issues recommendation immediately.
- Compact one-command baseline, no template CMS/wizard expansion.

## 7. Patient Response Flow Scope
- Added patient commands:
  - `/recommendations`
  - `/recommendation_open <recommendation_id>`
  - `/recommendation_action <ack|accept|decline> <recommendation_id>`
- Patient identity resolution baseline uses linked Telegram contact in canonical patient contacts.
- Recommendation open marks `issued -> viewed`.

## 8. Trigger Strategy
- Implemented trigger baseline from booking context:
  - when doctor marks booking `completed`, system auto-creates and issues an `aftercare` recommendation (`source_kind=booking_trigger`).
- Kept trigger logic narrow and explicit; no rule engine introduced.

## 9. Event Emission Coverage
Implemented outbox-backed emission for:
- `recommendation.created`
- `recommendation.issued`
- `recommendation.viewed`
- `recommendation.acknowledged`
- `recommendation.accepted`
- `recommendation.declined`
- `recommendation.expired`
- `recommendation.withdrawn`

Events are emitted transactionally from DB repository save path on status changes.

## 10. Carry-Forward Local-Day Fix Notes
Fixed `open_confirmation_backlog` alert computation:
- removed raw UTC day slicing (`AT TIME ZONE 'UTC'`) for backlog rule;
- switched to clinic/branch-aware local day semantics via `COALESCE(branch.timezone, clinic.timezone, 'UTC')`;
- added coverage test to enforce non-UTC slicing rule.

## 11. Files Added
- `app/domain/recommendations/models.py`
- `app/application/recommendation/services.py`
- `app/infrastructure/db/recommendation_repository.py`
- `tests/test_recommendation_stack10a.py`
- `docs/report/PR_STACK_10A_REPORT.md`

## 12. Files Modified
- `app/domain/recommendations/__init__.py`
- `app/application/recommendation/__init__.py`
- `app/infrastructure/db/bootstrap.py`
- `app/projections/owner/daily_metrics_projector.py`
- `app/application/doctor/operations.py`
- `app/bootstrap/runtime.py`
- `app/interfaces/bots/doctor/router.py`
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_owner_analytics_stack9a.py`

## 13. Commands Run
- `pytest -q tests/test_recommendation_stack10a.py tests/test_owner_analytics_stack9a.py tests/test_runtime_wiring.py tests/test_db_bootstrap.py`

## 14. Test Results
- 17 tests passed in targeted run above.
- Added recommendation lifecycle, doctor trigger flow, event emission, and local-day backlog semantic coverage.

## 15. Known Limitations / Explicit Non-Goals
- No care-commerce/product/order/reservation flows were implemented.
- No owner recommendation dashboard/UI was added.
- No recommendation template CMS was introduced.
- Patient flow is command-first baseline; richer panel UX can be layered later.

## 16. Deviations From Docs (if any)
- None intentional on canonical semantics.
- Trigger path implemented for booking completion; additional encounter/clinical trigger variants intentionally deferred.

## 17. Readiness Assessment for Next Stack
- Recommendation truth is now canonical and queryable.
- Lifecycle and patient response outcomes are evented for analytics/projection growth.
- Booking-triggered issuance path is in place and can be extended to richer clinical triggers and care-commerce linkage in the next stack.
