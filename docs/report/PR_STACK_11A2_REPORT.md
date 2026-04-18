# PR Stack 11A2 Report — Pickup Branch Selection + Baseline Stock Availability

## 1. Objective
Implement a compact hardening pass for care-commerce baseline by replacing hidden pickup-branch defaults with explicit branch selection and adding minimal branch/product stock availability semantics that actively gate reservation and reserve→issue flow.

## 2. Docs Read
1. `README.md`
2. `docs/18_development_rules_and_baseline.md`
3. `docs/10_architecture.md`
4. `docs/12_repo_structure_and_code_map.md`
5. `docs/60_care_commerce.md`
6. `docs/20_domain_model.md`
7. `docs/25_state_machines.md`
8. `docs/30_data_model.md`
9. `docs/35_event_catalog.md`
10. `docs/50_analytics_and_owner_metrics.md`
11. `docs/15_ui_ux_and_product_rules.md`
12. `docs/17_localization_and_i18n.md`
13. `docs/22_access_and_identity_model.md`
14. `docs/23_policy_and_configuration_model.md`
15. `docs/70_bot_flows.md`
16. `docs/72_admin_doctor_owner_ui_contracts.md`
17. `docs/80_integrations_and_infra.md`
18. `docs/85_security_and_privacy.md`
19. `docs/90_pr_plan.md`
20. `docs/95_testing_and_launch.md`
21. `docs/report/PR_STACK_11A_REPORT.md`
22. `docs/report/PR_STACK_11A1_REPORT.md`

## 3. Precedence Decisions
- Followed baseline-only schema discipline: edited bootstrap baseline in place; no migration chain added.
- Kept care-commerce bounded context separate from recommendation context.
- Implemented minimal availability truth (availability + reserved quantities) without adding inventory ledger/procurement/transfers.
- Replaced patient pickup branch heuristic with explicit branch input in patient order command path.

## 4. Availability Model Summary
Added canonical table:
- `care_commerce.branch_product_availability`

Fields:
- `branch_product_availability_id`
- `clinic_id`
- `branch_id`
- `care_product_id`
- `available_qty`
- `reserved_qty`
- `status`
- `updated_at`
- `created_at`

Constraints/indices:
- unique `(branch_id, care_product_id)`
- branch/status index for quick operational checks

## 5. Reservation/Stock Rule Chosen
Rule used in this stack:
- Free stock = `max(0, available_qty - reserved_qty)`.
- Reservation create requires active availability row and `free_qty >= requested_qty`; otherwise explicit typed failure reason.
- Reservation create increases `reserved_qty`.
- Reservation release decreases `reserved_qty`.
- Reservation consume decreases both `reserved_qty` and `available_qty`.

This keeps semantics deterministic and operational without introducing accounting behavior.

## 6. Pickup Branch Selection Strategy
Patient care order create flow now requires explicit pickup branch id:
- `/care_order_create <recommendation_id> <care_product_id> <pickup_branch_id>`

Behavior:
- branch id must resolve to a clinic branch
- stock check runs for that branch
- out-of-stock returns explicit localized message
- selected branch is persisted on care order

Hidden “first branch” heuristic was removed from patient path.

## 7. Patient/Admin Flow Updates
Patient flow updates:
- explicit branch parameter in care order create command
- branch validity check before order creation
- branch-specific out-of-stock handling before order create
- order list now displays branch context

Admin flow updates:
- admin care order list displays pickup branch
- `ready` action enforces branch-aware stock sufficiency
- localized insufficient-stock error surfaced for invalid ready transition
- issue/cancel flows remain reservation-stock coherent

## 8. Files Added
- `docs/report/PR_STACK_11A2_REPORT.md`

## 9. Files Modified
- `app/infrastructure/db/bootstrap.py`
- `app/domain/care_commerce/models.py`
- `app/domain/care_commerce/__init__.py`
- `app/application/care_commerce/service.py`
- `app/infrastructure/db/care_commerce_repository.py`
- `app/interfaces/bots/patient/router.py`
- `app/interfaces/bots/admin/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_care_commerce_stack11a.py`

## 10. Commands Run
- `python -m py_compile app/infrastructure/db/care_commerce_repository.py app/application/care_commerce/service.py app/domain/care_commerce/models.py app/domain/care_commerce/__init__.py`
- `python -m py_compile app/interfaces/bots/patient/router.py app/interfaces/bots/admin/router.py app/infrastructure/db/bootstrap.py app/infrastructure/db/care_commerce_repository.py app/application/care_commerce/service.py tests/test_care_commerce_stack11a.py`
- `pytest -q tests/test_care_commerce_stack11a.py tests/test_recommendation_stack10a.py`

## 11. Test Results
- `pytest -q tests/test_care_commerce_stack11a.py tests/test_recommendation_stack10a.py` → **13 passed**

## 12. Remaining Known Limitations
- No cross-branch transfer logic (out of scope by design).
- No inventory movement ledger/audit history beyond current availability state (out of scope by design).
- No expanded patient UI branch picker panel yet; explicit command parameter baseline is implemented.

## 13. Deviations From Docs (if any)
- No material deviations. Approach stays bounded and non-ERP.

## 14. Readiness Assessment for Next Stack
Ready for next stack:
- branch/product availability baseline exists
- reservations are availability-gated
- pickup branch selection is explicit in patient flow
- admin reserve/issue path is branch-aware and stock-coherent
- regression tests remain green
