# PR_CC4_REPORT

## 1. Objective
Implement CC-4 patient-facing care-commerce UX as a bounded, recommendation-first, narrow catalog flow in Telegram with explicit branch-aware reserve/pickup behavior, repeat baseline, and explicit localized invalid-manual-target messaging.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/10_architecture.md
4. docs/12_repo_structure_and_code_map.md
5. docs/60_care_commerce.md
6. docs/shop/00_shop_readme.md
7. docs/shop/61_care_catalog_model.md
8. docs/shop/62_care_catalog_workbook_spec.md
9. docs/shop/63_recommendation_to_product_engine.md
10. docs/shop/64_care_patient_catalog_and_flow.md
11. docs/shop/66_care_stock_and_pickup_semantics.md
12. docs/shop/67_care_media_and_content_rules.md
13. docs/15_ui_ux_and_product_rules.md
14. docs/17_localization_and_i18n.md
15. docs/22_access_and_identity_model.md
16. docs/23_policy_and_configuration_model.md
17. docs/70_bot_flows.md
18. docs/80_integrations_and_infra.md
19. docs/85_security_and_privacy.md
20. docs/90_pr_plan.md
21. docs/95_testing_and_launch.md
22. docs/report/PR_CC2_REPORT.md
23. docs/report/PR_CC2A_REPORT.md
24. docs/report/PR_CC3_REPORT.md
25. docs/report/PR_CC3A_REPORT.md

## 3. Precedence Decisions
- Kept patient commerce recommendation-first while adding a secondary narrow `Care / Уход` entry.
- Used synced catalog content (`product_i18n` + fallback locale) for product title/description/short label; no new hardcoded product copy in handlers.
- Implemented explicit branch visibility/override before reserve action and stock-aware failure handling.
- Did not implement broad storefront/search/sort UX to stay within narrow catalog product constraints.

## 4. Patient Catalog Entry Strategy
- Added patient `/care` entry that opens a compact category panel.
- Category list is derived from active synced catalog products only.
- Navigation is shallow: category list -> product list -> product card -> reserve/branch change.

## 5. Category/Product Card Strategy
- Added category-localized labels (`care.category.*`) with safe code fallback.
- Added compact product list rows showing title, short label/category hint, price, and compact availability label.
- Added product detail card with localized content, category, price, availability, selected/preferred branch hint, usage hint, and recommendation context snippet when present.

## 6. Branch-Aware Reserve Flow Strategy
- Preferred branch selection baseline:
  - first valid stock branch from `care.default_pickup_branch_id` if available,
  - otherwise first in-stock branch.
- Branch is always visible on product card and can be explicitly changed with a branch picker.
- Reserve action validates current free quantity and fails clearly when stock is insufficient.
- Successful reserve creates care order (`confirmed`) and reservation row, and returns compact result panel (product, branch, status, next step).

## 7. Repeat Purchase Strategy
- Implemented baseline from prior care orders:
  - `/care_orders` now includes `/care_order_repeat <care_order_id>` hint.
  - `/care_order_repeat` revalidates product active status and current stock before creating a new reserve order.
- Repeat path reuses current truth and does not blindly clone stale assumptions.

## 8. Invalid Manual Target UX Handling
- Implemented explicit localized patient-facing message when recommendation resolution returns `manual_target_invalid`.
- Message keeps recommendation context and provides bounded next actions:
  - back to recommendation detail,
  - open care catalog (`/care`).
- No silent fallback to unrelated rule/direct mappings.

## 9. Files Added
- docs/report/PR_CC4_REPORT.md

## 10. Files Modified
- app/interfaces/bots/patient/router.py
- app/application/care_commerce/service.py
- tests/test_care_commerce_stack11a.py
- locales/en.json
- locales/ru.json

## 11. Commands Run
- `pytest -q tests/test_care_commerce_stack11a.py tests/test_i18n.py`
- `pytest -q tests/test_runtime_wiring.py`

## 12. Test Results
- `tests/test_care_commerce_stack11a.py`: passed (including new catalog category navigation and repeat stock revalidation checks).
- `tests/test_i18n.py`: passed.
- `tests/test_runtime_wiring.py`: passed.

## 13. Known Limitations / Explicit Non-Goals
- No giant storefront UX, no full-text product search, no filter/sort labyrinth.
- No warehouse accounting/ledger logic, no shipping/delivery flow.
- Product media is still constrained by currently available runtime content fields; this PR surfaces synced textual content and usage hints coherently in card flow.
- Repeat baseline currently uses order-first command path; it does not yet include advanced multi-item repeat wizard UX.

## 14. Deviations From Docs (if any)
- None intentional.

## 15. Readiness Assessment for the next commerce PR
- Ready for next commerce PR.
- Patient-facing narrow catalog and recommendation-first paths are now coherent and branch-aware in Telegram.
- Manual invalid target no longer disappears silently for patients.
- Branch-aware reserve and repeat baseline are in place with regression tests.
