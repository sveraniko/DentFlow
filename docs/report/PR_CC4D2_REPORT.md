# PR_CC4D2_REPORT

## 1. Objective
Implement CC-4D-2 so reserve-again/repeat becomes a real patient-facing object action from care order surfaces, with runtime revalidation of branch and availability truth before creating a new order/reservation.

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
13. docs/shop/64_care_patient_catalog_and_flow.md  
14. docs/shop/66_care_stock_and_pickup_semantics.md  
15. docs/report/PR_CC4A_REPORT.md  
16. docs/report/PR_CC4B_REPORT.md  
17. docs/report/PR_CC4C_REPORT.md  
18. docs/report/PR_CC4D1_REPORT.md

## 3. Scope Implemented
- Added a dedicated repeat-order application service path (`repeat_order_as_new`) that revalidates product status, branch validity, branch availability state, and free quantity before creation.
- Updated patient care order surface to expose object-first actions via shared card callback contract (`CARE_ORDER` + `CARE_ORDER_LIST`) with explicit **Open** and **Reserve again** actions.
- Added safe stale-branch handling: when prior branch fails current truth checks, patient is prompted with valid branch alternatives.
- Kept command-style `/care_order_repeat` as compatibility fallback and explicitly non-primary path.

## 4. Reserve-Again UX Strategy
- ` /care_orders` now renders per-order object actions with two buttons:
  - Open order object
  - Reserve again
- Open action shows what is being repeated (product, qty, branch, availability note) and offers reserve-again action from that object context.
- Reserve-again action resolves into explicit confirmation/failure messages; no silent mutation.

## 5. Revalidation Strategy
Repeat path now revalidates current runtime truth before creating a new order:
- Source order exists and belongs to current patient/clinic.
- Source order still has item context.
- Product still exists and is `active` (orderable).
- Requested/source branch is validated against allowed clinic branch scope.
- Branch product availability row is present and `active`.
- Free quantity is enough for repeat quantity.
- If stale/invalid/unavailable branch is detected, service returns valid alternative branches for safe patient selection.

## 6. New Order/Reservation Strategy
- Repeat uses creation semantics only:
  - Creates new care order.
  - Transitions new order to `confirmed`.
  - Creates new reservation for selected valid branch.
- Old order remains untouched as historical truth (no mutation/recycle).
- Recommendation linkage is intentionally not copied to preserve recommendation-vs-order truth distinction.

## 7. Files Added
- `docs/report/PR_CC4D2_REPORT.md`

## 8. Files Modified
- `app/application/care_commerce/service.py`
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_care_commerce_stack11a.py`
- `tests/test_patient_care_ui_cc4c.py`

## 9. Commands Run
- `rg --files`
- `sed -n ...` (required docs and source inspections)
- `rg -n "care_order_repeat|repeat|CARE_ORDER|reserve" app tests locales`
- `pytest -q tests/test_care_commerce_stack11a.py tests/test_patient_care_ui_cc4c.py`

## 10. Test Results
- `tests/test_care_commerce_stack11a.py` passed.
- `tests/test_patient_care_ui_cc4c.py` passed.

## 11. Remaining Known Limitations
- Care-order object card still uses a compact text object panel + callback actions; a full dedicated `CareOrderCardAdapter` was not introduced in this PR to avoid scope widening.
- Repeat path currently repeats the first source order item only (consistent with previous baseline behavior).

## 12. Deviations From Docs (if any)
- No intentional architecture or UX-contract deviations.
- Kept command repeat path as backward-compatibility fallback only.

## 13. Readiness Assessment for next PR
- CC-4D-2 objective is met for reserve-again object action and runtime truth revalidation.
- Next PR can focus on expanding care-order object depth (e.g., multi-item repeat UX) without revisiting the core repeat integrity and callback contract.
