# PR Stack 11A Report — Care-Commerce Baseline

## 1. Objective
Implement a bounded, recommendation-driven care-commerce baseline with canonical schema, product catalog, recommendation linkage, care order/reservation lifecycle, patient/admin operational flows, lifecycle events, and mandatory carry-forward recommendation fixes from Stack 10A.

## 2. Docs Read
Read and applied (in requested precedence):
- README.md
- docs/18_development_rules_and_baseline.md
- docs/60_care_commerce.md
- docs/25_state_machines.md
- docs/30_data_model.md
- docs/35_event_catalog.md
- docs/70_bot_flows.md

## 3. Precedence Decisions
1. **Recommendation semantics fix:** Introduced explicit separation between `recommendation.created` (entity creation) and `recommendation.prepared` (lifecycle status). This resolves the prior ambiguity where prepared emitted created only.
2. **Patient resolution safety:** For recommendation-facing patient lookup by Telegram contact, ambiguity now resolves to safe failure (`None`) rather than selecting first match.
3. **Aftercare trigger content:** Removed hardcoded English in doctor completion trigger path and switched to compact locale template mapping (EN/RU), avoiding CMS scope expansion.

## 4. Care-Commerce Schema Summary
Added canonical baseline tables under `care_commerce` in bootstrap baseline:
- `products`
- `recommendation_product_links`
- `care_orders`
- `care_order_items`
- `care_reservations`

Also added indexes and compact `available_qty` practical field without warehouse ledger complexity.

## 5. Product Catalog Strategy
Implemented DB-backed product catalog repository/service with:
- create/update product
- list active products by clinic
- product lookup
- localized title via `title_key` strategy

## 6. Recommendation-to-Product Link Strategy
Implemented explicit bridge table and service methods:
- link product to recommendation
- list linked products for recommendation
- preserve ordering via `relevance_rank`
- preserve justification metadata keys

## 7. Care Order / Reservation Lifecycle Strategy
Implemented care order state transitions in service (single mutation path):
- create, confirm, payment-required, paid, ready_for_pickup, issued, fulfilled, cancel, expire
- invalid transitions rejected with `ValueError`

Implemented reservation lifecycle baseline:
- create
- release
- consume

Reservation lifecycle remains distinct from care order lifecycle.

## 8. Patient Flow Scope
Added patient recommendation-driven care commands:
- `/recommendation_products <recommendation_id>`
- `/care_order_create <recommendation_id> <care_product_id>`
- `/care_orders`

Flow remains recommendation-anchored; no broad storefront introduced.

## 9. Admin Flow Scope
Added admin operational commands:
- `/care_orders` (pending list)
- `/care_order_action <ready|issue|fulfill|cancel|pay_required|paid> <care_order_id>`

Focus is pickup/issue baseline, not ERP functionality.

## 10. Carry-Forward Fixes from 10A
1. **Hardcoded aftercare text removed:** now locale-template-backed EN/RU.
2. **Ambiguous Telegram patient resolution hardened:** safe failure on multiple patient matches.
3. **Created/prepared event semantics corrected:** explicit `recommendation.created` + `recommendation.prepared` behavior.

## 11. Event Emission Coverage
Added/updated outbox event emission:
- product: `care_product.created`, `care_product.updated`
- orders: `care_order.created`, `care_order.confirmed`, `care_order.payment_required`, `care_order.paid`, `care_order.ready_for_pickup`, `care_order.issued`, `care_order.fulfilled`, `care_order.canceled`
- reservations: `care_reservation.created`, `care_reservation.released`, `care_reservation.expired`, `care_reservation.consumed`
- recommendation semantics: `recommendation.created` and `recommendation.prepared` made explicit

## 12. Files Added
- app/domain/care_commerce/models.py
- app/domain/care_commerce/__init__.py
- app/application/care_commerce/service.py
- app/application/care_commerce/__init__.py
- app/infrastructure/db/care_commerce_repository.py
- tests/test_care_commerce_stack11a.py
- docs/report/PR_STACK_11A_REPORT.md

## 13. Files Modified
- app/infrastructure/db/bootstrap.py
- app/infrastructure/db/recommendation_repository.py
- app/application/doctor/operations.py
- app/interfaces/bots/patient/router.py
- app/interfaces/bots/admin/router.py
- app/bootstrap/runtime.py
- locales/en.json
- locales/ru.json
- docs/35_event_catalog.md
- tests/test_recommendation_stack10a.py

## 14. Commands Run
- `pytest -q tests/test_recommendation_stack10a.py tests/test_care_commerce_stack11a.py`
- `python -m compileall -q app`

## 15. Test Results
- Recommendation lifecycle tests: pass
- Care-commerce baseline service tests: pass
- Compile check: pass

## 16. Known Limitations / Explicit Non-Goals
Not implemented in this stack:
- warehouse accounting/movement ledger
- supplier/procurement subsystem
- external commerce integrations
- delivery logistics platform
- broad catalog marketplace UX

## 17. Deviations From Docs (if any)
- Added `recommendation.prepared` event to make lifecycle semantics explicit. This is an extension to existing event catalog wording to satisfy carry-forward semantic correction.

## 18. Readiness Assessment for Next Stack
Baseline is ready for next stack expansion:
- canonical schema exists
- explicit order/reservation lifecycles exist
- recommendation bridge exists
- patient/admin path exists
- outbox events exist
- mandatory 10A carry-forwards completed

Next stack can focus on deeper policy, payment adapters, richer UI contracts, and analytics projections without refactoring this baseline boundary.
