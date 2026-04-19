# PR_CC4D1_REPORT

## 1. Objective
Implement CC-4D-1 by replacing remaining text-list-first product selection UX with true compact product object rows/cards, unified across recommendation-linked and category-linked browsing, while preserving existing full product card and reserve flow behavior.

## 2. Docs Read
1. README.md  
2. docs/18_development_rules_and_baseline.md  
3. docs/10_architecture.md  
4. docs/12_repo_structure_and_code_map.md  
5. docs/15_ui_ux_and_product_rules.md  
6. docs/17_localization_and_i18n.md  
7. docs/16_unified_card_system.md  
8. docs/16-1_card_profiles.md  
9. docs/16-2_card_callback_contract.md  
10. docs/16-3_card_media_and_navigation_rules.md  
11. docs/16-5_card_runtime_state_and_redis_rules.md  
12. docs/60_care_commerce.md  
13. docs/shop/00_shop_readme.md  
14. docs/shop/61_care_catalog_model.md  
15. docs/shop/63_recommendation_to_product_engine.md  
16. docs/shop/64_care_patient_catalog_and_flow.md  
17. docs/shop/66_care_stock_and_pickup_semantics.md  
18. docs/shop/67_care_media_and_content_rules.md  
19. docs/report/PR_CC4A_REPORT.md  
20. docs/report/PR_CC4B_REPORT.md  
21. docs/report/PR_CC4C_REPORT.md  
22. docs/report/PR_UC3B_REPORT.md

## 3. Scope Implemented
- Replaced the ad hoc compact picker struct with a compact product row/card object that directly wraps unified `CardShell` output in `LIST_ROW` mode.
- Updated both category product lists and recommendation-linked product lists to use this same compact row/card object.
- Kept product-open action flow unchanged: selecting a compact row opens the existing full product card object and existing reserve flow remains intact.
- Added/updated tests to validate compact row object grammar and unified behavior across category/recommendation contexts.

## 4. Compact Product Row/Card Strategy
- Introduced `_CompactProductRowCard` in patient router as the browsing primitive.
- The primitive stores the actual `ProductCardAdapter.build(..., mode=CardMode.LIST_ROW)` shell instead of copying values into a string-first shape.
- Button label grammar is derived from card object content (`title`, `meta_lines`, `badges`) to preserve unified card semantics and localized text.
- Compact row explicitly exposes open-action capability via card actions (`CardAction.OPEN`).

## 5. Recommendation Browsing Strategy
- Recommendation picker now builds `_CompactProductRowCard` objects via shared helper and recommendation source context.
- Recommendation badge rendering is preserved through unified card badges for recommendation context.
- Selecting a recommendation row/card continues to open full product card with preserved recommendation source reference/context.

## 6. Category Browsing Strategy
- Category picker now builds the same `_CompactProductRowCard` objects via the same helper.
- Category rows keep compact object grammar without recommendation-only metadata.
- Selecting a category row/card continues to open full product card with category source context.

## 7. Pagination/Back Behavior Notes
- Existing page slice and page-state persistence logic were preserved.
- Category list pagination (`products_page:*`) and recommendation pagination (`rec_page:*`) remain unchanged in behavior.
- Back behavior from product detail was not redesigned in this PR and remains compatible with existing recommendation/category context handling.

## 8. Files Added
- docs/report/PR_CC4D1_REPORT.md

## 9. Files Modified
- app/interfaces/bots/patient/router.py
- tests/test_patient_care_ui_cc4c.py

## 10. Commands Run
- `pwd && rg --files -g 'AGENTS.md'`
- `find . -maxdepth 3 -type f | head -200`
- `rg -n "product|recommend|category|care|compact|card" app tests | head -200`
- `sed -n '1,260p' tests/test_patient_care_ui_cc4c.py`
- `sed -n '1,420p' app/interfaces/bots/patient/router.py`
- `sed -n '420,860p' app/interfaces/bots/patient/router.py`
- `rg -n "recommendation|products_page|back_recommendation|care\\.products|compact" app/interfaces/bots/patient/router.py`
- `sed -n '900,1045p' app/interfaces/bots/patient/router.py`
- `sed -n '1045,1115p' app/interfaces/bots/patient/router.py`
- `for f in ...; sed -n '1,140p' "$f"; done` (required docs review)
- `rg -n "class Product|ProductCardAdapter|LIST_ROW|meta_lines|ProductRuntimeViewBuilder|ProductCardSeed" app/interfaces/cards -g '*.py'`
- `sed -n '300,410p' app/interfaces/cards/adapters.py`
- `pytest -q tests/test_patient_care_ui_cc4c.py tests/test_unified_card_framework_uc1.py tests/test_care_commerce_stack11a.py`
- `rg -n "class CardBadge" app/interfaces/cards/models.py && sed -n '1,120p' app/interfaces/cards/models.py`
- `pytest -q tests/test_patient_care_ui_cc4c.py tests/test_unified_card_framework_uc1.py tests/test_care_commerce_stack11a.py`

## 11. Test Results
- First targeted run failed once due to incorrect badge field access (`CardBadge.text` vs `.label`) and was fixed.
- Final targeted run passed:
  - `tests/test_patient_care_ui_cc4c.py`
  - `tests/test_unified_card_framework_uc1.py`
  - `tests/test_care_commerce_stack11a.py`

## 12. Remaining Known Limitations
- Compact row rendering is still constrained by Telegram button label length, so the rendered compact label remains summarized/truncated.
- This PR intentionally does not redesign full product card detail, media UX depth, or reserve-again UX (deferred to later PRs per scope).

## 13. Deviations From Docs (if any)
- No intentional deviations from card-system/shop precedence docs.
- Explicit decision: preserve existing detail/reserve behavior and only replace product selection surface with object-native compact rows/cards.

## 14. Readiness Assessment for CC-4D-2 / CC-4D-3
- CC-4D-1 selection layer objective is met: recommendation and category product browsing now share a unified compact product object row/card primitive.
- Codebase is ready for subsequent CC-4D-2/CC-4D-3 work without needing to revisit this selection-layer unification.
