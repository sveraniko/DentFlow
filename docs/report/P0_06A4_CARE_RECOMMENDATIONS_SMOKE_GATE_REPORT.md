# P0-06A4 Care/Recommendations Consolidated Smoke Gate + Seed Readiness Report

## Summary
Implemented a consolidated smoke gate that validates care + recommendations entry/failure navigation, callback namespace safety, and double callback-answer guardrails in one place.

Scope in this PR is intentionally tests + reporting. No DB schema changes, no router split, no CardShellRenderer rewrite, and no seed-data insertion.

## Files changed
- `tests/test_p0_06a4_care_recommendations_smoke_gate.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `docs/report/P0_06A4_CARE_RECOMMENDATIONS_SMOKE_GATE_REPORT.md`

## Smoke matrix

### 1) Care entry
- ✅ module unavailable specific panel (`phome:care` when care service absent).
- ✅ catalog empty readable panel (care service present, categories empty).
- ✅ category empty readable panel (open category with zero products).
- ✅ recovery navigation includes Home/My Booking where expected.

### 2) Care failure recovery
- ✅ care orders unresolved -> inline recovery panel with `phome:my_booking` and `phome:home`.
- ✅ care reserve unresolved -> inline recovery panel with `phome:my_booking`, `phome:care`, `phome:home`.
- ✅ no popup-only valid path in tested unresolved flows.
- ✅ no double callback-answer in tested valid render paths.

### 3) Recommendations entry
- ✅ module unavailable specific panel.
- ✅ unresolved patient inline recovery panel.
- ✅ empty state readable panel.
- ✅ recommendation detail includes Back/Home.

### 4) Recommendation products failure recovery
- ✅ manual target invalid inline panel.
- ✅ empty products inline panel.
- ✅ navigation includes Back recommendation / Care catalog / Home.

## Callback namespace check
Collected callback_data values from all panels reached by the consolidated smoke gate and validated prefixes.

Allowed prefixes used:
- `phome:home`
- `phome:my_booking`
- `phome:care`
- `phome:recommendations`
- `care:`
- `careo:`
- `prec:`
- `rec:`
- runtime encoded callbacks (`c{n}|...`) produced by card runtime.

Result: ✅ all collected callback_data fit the allowed namespace policy (no broad wildcard whitelist added).

## Double callback-answer check
For valid render paths, smoke asserts `len(callback.answer_payloads) <= 1` and panel render presence:
- `phome:care`
- care category empty
- `care:orders` unresolved
- `care:reserve:*` unresolved
- `phome:recommendations`
- recommendation detail open
- recommendation products empty/manual-invalid

Result: ✅ no double-answer regressions in these paths.

## Seed/content readiness findings

### Care/catalog readiness
- Care service is wired in tests via `home._build_router(with_care=True)` and stubbed `_CareServiceStub`.
- When care module is absent: care entry renders a specific unavailable panel with recovery navigation.
- When care catalog has zero categories: care entry renders catalog-empty panel.
- When category has zero products: care category-empty panel is shown with Back/Home.

### Recommendations readiness
- When recommendation service is absent: recommendation entry renders specific unavailable panel.
- When patient resolution fails: recommendation entry and related callbacks render/return recovery copy.
- When no recommendations exist: recommendation empty panel is shown.
- When recommendation product target is invalid or resolved empty: inline recovery panels are shown with Back/Care/Home.

### Seed/demo data status in this PR
- No actual demo seed data was added in this PR.
- No live DB inspection was performed in this PR.

### Seed/demo expectation docs
- `docs/92_seed_data_and_demo_fixtures.md`
- `docs/60_care_commerce.md`
- `docs/shop/00_shop_readme.md` (care catalog package overview and sync-related detail index)

## Grep checks
Executed exactly:
- `rg "patient.home.action.unavailable" app/interfaces/bots/patient/router.py`
- `rg "patient.care.unavailable|patient.care.catalog.empty|patient.care.catalog.category.empty|patient.care.orders.patient_resolution_failed|patient.care.reserve.patient_resolution_failed" app/interfaces/bots/patient/router.py locales tests`
- `rg "patient.recommendations.unavailable|patient.recommendations.patient_resolution_failed|patient.recommendations.empty" app/interfaces/bots/patient/router.py locales tests`
- `rg "patient.care.products.manual_target_invalid|patient.care.products.empty" app/interfaces/bots/patient/router.py locales tests`
- `rg "show_alert=True" app/interfaces/bots/patient/router.py`

Findings:
- `patient.home.action.unavailable` is not used in `patient/router.py` for these active care/recommendation entry surfaces.
- New/relevant panel keys are wired in router + locales and covered by tests.
- Legacy non-panel message keys (`patient.care.products.manual_target_invalid`, `patient.care.products.empty`, etc.) are still present for command/text fallbacks.

### Remaining `show_alert=True` branches classification
- **Stale/invalid callback:** booking callback stale/session-missing branches; common card stale; reminder stale/invalid.
- **Valid user action (guarded denial):** recommendation/care callback unavailable/not-found/invalid-state safety alerts; access-denied/open-denied branches.
- **Carry-forward:** legacy alert-first behavior in command/callback fallbacks outside this smoke gate scope (booking/reminder-heavy branches).

## Defects found/fixed
1. Found by optional regression sweep (`pytest -q tests -k "care or recommendation"`):
   - `test_care_catalog_unavailable_empty_state_has_home_action` expected outdated copy/button set.
   - `test_recommendation_products_callback_reuses_resolution_and_falls_back_safely` expected old popup answer instead of inline panel text.
2. Fixed by updating stale expectations in `tests/test_patient_home_surface_pat_a1_2.py` to current A1/A3 behavior.

## Existing gates
Required legacy gates were run and pass:
- A1 (`tests/test_p0_06a1_care_entry_empty_states.py`) ✅
- A2 (`tests/test_p0_06a2_recommendations_entry_empty_states.py`) ✅
- A3 (`tests/test_p0_06a3_care_recommendation_failure_recovery.py`) ✅
- P0-05C ✅
- P0-04C ✅
- P0-03D ✅

## Tests run with exact commands/results
- `python -m compileall app tests` -> PASS
- `pytest -q tests/test_p0_06a4_care_recommendations_smoke_gate.py` -> PASS (`1 passed`)
- `pytest -q tests/test_p0_06a3_care_recommendation_failure_recovery.py` -> PASS (`4 passed`)
- `pytest -q tests/test_p0_06a2_recommendations_entry_empty_states.py` -> PASS (`4 passed`)
- `pytest -q tests/test_p0_06a1_care_entry_empty_states.py` -> PASS (`3 passed`)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` -> PASS (`4 passed`)
- `pytest -q tests/test_p0_04c_review_edit_success_smoke_gate.py` -> PASS (`3 passed`)
- `pytest -q tests/test_p0_03d_patient_booking_smoke_gate.py` -> PASS (`6 passed`)
- `pytest -q tests -k "patient and booking"` -> PASS (`105 passed, 509 deselected`)
- `pytest -q tests -k "care or recommendation"` -> initially FAIL (`2 failed`), after stale-test expectation fixes -> PASS (`112 passed, 502 deselected`)

## Carry-forward for P0-06B
- Product list/card polish.
- Reserve/order result polish.
- Optional cleanup of legacy non-panel fallback copy paths.

## Carry-forward for P0-06C
- Recommendation detail/action polish (copy/action UX refinement beyond current Back/Home + fail-recovery baseline).

## Carry-forward for live pilot seed gate
Still needed before live pilot seed gate:
- minimum demo care services + category/product coverage;
- recommendation fixtures linked to actual patient/visit flows;
- care order/reservation lifecycle fixtures (created/ready/fulfilled/expired);
- cross-flow data continuity for booking -> recommendation -> care reserve.

## Go/no-go recommendation for P0-06B
**Go for P0-06B**.

Rationale:
- consolidated care/recommendation smoke exists;
- A1/A2/A3 + required prior gates pass;
- valid entry/failure paths are navigable and no double-answer regressions were found in targeted valid paths;
- seed/content readiness is documented honestly with explicit remaining pilot-fixture gaps.
