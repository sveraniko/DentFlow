# P0-06A3 Failure Recovery Report

## Summary
Implemented inline failure/recovery panels for the requested patient flows so users always have valid next actions (no popup-only dead-ends) in:
- care orders entry when patient resolution fails;
- care reserve action when patient resolution fails;
- recommendation products when manual target is invalid;
- recommendation products when resolved products are empty.

Also cleaned callback behavior in touched handlers (`care:orders`, `care:reserve`, `prec:products`) to avoid double callback-answer patterns on the panel success path.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/ru.json`
- `locales/en.json`
- `tests/test_p0_06a3_care_recommendation_failure_recovery.py`

## Care orders unresolved behavior
Handler: `care:orders` callback.

When patient/clinic resolution is unavailable, router now renders inline panel:
- title: "📦 Мои резервы" (RU)
- message explains safe patient resolution failure and recovery
- actions:
  - My Booking → `phome:my_booking`
  - Home → `phome:home`

No popup-only path for this valid user action.

## Care reserve unresolved behavior
Handler: `care:reserve:*` callback.

When patient resolution fails while reserving, router now renders inline panel:
- title: "🪥 Резерв недоступен" (RU)
- message explains profile binding recovery
- actions:
  - My Booking → `phome:my_booking`
  - Care catalog → `phome:care`
  - Home → `phome:home`

No popup-only path for this valid user action.

## Recommendation products manual-invalid behavior
Handler: `prec:products:{recommendation_id}` callback.

When recommendation target resolution returns `manual_target_invalid`, router now renders inline recoverable panel:
- title: "🪥 Рекомендованный товар недоступен" (RU)
- actions:
  - Back to recommendation → `prec:open:{recommendation_id}`
  - Care catalog → `phome:care`
  - Home → `phome:home`

No popup-only path.

## Recommendation products empty behavior
Handler: `prec:products:{recommendation_id}` callback.

When recommendation exists but resolved product set is empty, router now renders inline recoverable panel:
- title: "🪥 К рекомендации пока не привязаны товары" (RU)
- actions:
  - Back to recommendation → `prec:open:{recommendation_id}`
  - Care catalog → `phome:care`
  - Home → `phome:home`

## Double callback-answer cleanup
Touched handlers (`care:orders`, `care:reserve`, `prec:products`) now rely on `_send_or_edit_panel(...)` for failure UI paths, and tests assert no double-answer behavior (`len(callback.answer_payloads) <= 1`).

## Tests run
- `python -m compileall app tests` ✅
- `pytest -q tests/test_p0_06a3_care_recommendation_failure_recovery.py` ✅
- `pytest -q tests/test_p0_06a2_recommendations_entry_empty_states.py` ✅
- `pytest -q tests/test_p0_06a1_care_entry_empty_states.py` ✅
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` ✅

## Grep checks
Executed:
- `rg "patient.care.orders.patient_resolution_failed|patient.care.reserve.patient_resolution_failed|patient.care.products.manual_target_invalid|patient.care.products.empty" app/interfaces/bots/patient/router.py locales tests`
- `rg "show_alert=True" app/interfaces/bots/patient/router.py`

Findings:
- New `*.panel` keys are wired in router/locales and covered by new tests.
- Remaining care/recommendation `show_alert=True` branches in router are for invalid/stale/unauthorized paths (e.g. callback unavailable, recommendation/order not found, denied open, legacy invalid state). They are stale/invalid safety alerts rather than valid recovery entry paths.

## Carry-forward for P0-06B/C
- Legacy message-command copy keys (`patient.care.products.manual_target_invalid`, `patient.care.products.empty`) still exist for non-inline command paths and can be rationalized in later cleanup.
- Consider consolidating care/recommendation recovery-panel constructors to reduce copy and enforce one navigation pattern.

## Go / no-go for P0-06A4
**Go** — acceptance criteria for P0-06A3 are satisfied:
- valid failure paths are inline and recoverable;
- no dead-end popup-only UX in targeted paths;
- no success-path double callback-answer in touched handlers;
- A1/A2/P0-05C regression tests pass.
