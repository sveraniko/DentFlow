# PR Stack 11A1 Report — Care Template Localization + Reservation Flow Integrity

## 1. Objective
Deliver a narrow fix pass for Stack 11A baseline integrity by:
- removing hardcoded aftercare recommendation text from doctor operations code and resolving it through localization keys,
- integrating reservation semantics into actual patient/admin care reserve-pickup flow,
- keeping recommendation and care-order semantics distinct,
- strengthening tests around these specific gaps.

## 2. Docs Read
Read in requested order:
1. `README.md`
2. `docs/18_development_rules_and_baseline.md`
3. `docs/10_architecture.md`
4. `docs/12_repo_structure_and_code_map.md`
5. `docs/60_care_commerce.md`
6. `docs/17_localization_and_i18n.md`
7. `docs/20_domain_model.md`
8. `docs/25_state_machines.md`
9. `docs/30_data_model.md`
10. `docs/35_event_catalog.md`
11. `docs/70_bot_flows.md`
12. `docs/80_integrations_and_infra.md`
13. `docs/85_security_and_privacy.md`
14. `docs/90_pr_plan.md`
15. `docs/report/PR_STACK_10A_REPORT.md`
16. `docs/report/PR_STACK_11A_REPORT.md`

## 3. Scope Implemented
Implemented only targeted integrity fixes:
- replaced doctor aftercare trigger hardcoded text with locale-key resolution,
- introduced reservation-aware admin order actions (`ready`, `issue`, `cancel`) with concrete reservation side effects,
- aligned patient order creation with pickup branch baseline so reservation creation is feasible in real flow,
- added tests covering RU/EN localized aftercare resolution and integrated reservation lifecycle behavior in flow.

## 4. Aftercare Localization Strategy
Chosen approach: **localization keys via existing i18n service** (compact, no CMS).

Details:
- Removed `_AFTERCARE_TEMPLATES` hardcoded EN/RU dictionary from doctor operations code.
- Added keys:
  - `recommendation.aftercare.booking_complete.title`
  - `recommendation.aftercare.booking_complete.body`
- `_create_completion_aftercare` now resolves clinic locale and uses `I18nService.t(...)` for title/body.
- Added/updated tests to assert RU and EN aftercare content resolve through localization path.

## 5. Reservation Flow Integration Strategy
Chosen baseline rule:
- **Admin action `ready` (ready_for_pickup) creates missing active reservations for order items**.
- **Admin action `issue` consumes active reservations**.
- **Admin action `cancel` releases active reservations**.

Implementation notes:
- Added orchestration method `apply_admin_order_action(...)` in care-commerce service.
- Reservation lifecycle remains separate from order lifecycle:
  - orders transition by order status machine,
  - reservations transition independently (`created` → `consumed`/`released`).
- Added pickup-branch requirement for `ready` path (`pickup_branch_required` validation).
- Updated patient order creation to set default pickup branch from clinic reference baseline so reserve/pickup flow is practically usable.

## 6. Files Added
- `docs/report/PR_STACK_11A1_REPORT.md`

## 7. Files Modified
- `app/application/doctor/operations.py`
- `app/bootstrap/runtime.py`
- `app/interfaces/bots/doctor/router.py`
- `app/application/care_commerce/service.py`
- `app/interfaces/bots/patient/router.py`
- `app/interfaces/bots/admin/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_care_commerce_stack11a.py`

## 8. Commands Run
- `pytest -q tests/test_care_commerce_stack11a.py tests/test_recommendation_stack10a.py`
- `python -m compileall -q app`
- `rg -n "_AFTERCARE_TEMPLATES|Aftercare guidance|Рекомендации после приема|Please follow your dentist aftercare instructions|Пожалуйста, следуйте рекомендациям врача после приема" app/application/doctor/operations.py locales/en.json locales/ru.json`

## 9. Test Results
- Targeted recommendation + care-commerce tests: pass (`11 passed`).
- Python compile check: pass.
- Verification grep confirms aftercare literals are in locale files, not in doctor operations code.

## 10. Remaining Known Limitations
- No inventory ledger / stock movement accounting (intentionally out of scope).
- No supplier/procurement or delivery logistics (intentionally out of scope).
- Patient flow uses clinic-default pickup branch heuristic; branch selection UX can be improved later.
- Reservation quantity checks against real stock are not implemented in this baseline.

## 11. Deviations From Docs (if any)
- No intentional canonical model deviation.
- For practical baseline integrity, pickup branch is auto-filled from first clinic branch in patient command flow to make reserve/pickup semantics operational without introducing new UI subsystem.

## 12. Readiness Assessment for Next Stack
This stack is now materially stronger for next work:
- aftercare trigger text is localization-backed and not hardcoded in doctor operations,
- reservation lifecycle is integrated into real admin reserve/pickup behavior,
- tests demonstrate reservation is not just isolated service theory,
- care-commerce remains bounded (no subsystem sprawl).
