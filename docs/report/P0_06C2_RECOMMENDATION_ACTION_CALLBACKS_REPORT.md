# P0-06C2 — Recommendation action callbacks: inline result/invalid state/no double-answer

## Summary
Implemented P0-06C2 callback UX cleanup for recommendation actions and recommendation product handoff fallback:
- action success now renders **inline notice + updated detail card** (no popup result);
- invalid-state action now renders **inline warning + current/latest detail card** (no popup alert);
- action unresolved patient and action not-found/not-owned are now inline recovery panels;
- `prec:products:*` not-found/not-owned is now inline recovery panel;
- no manual second `callback.answer(...)` after detail render on valid action paths.

Result: **GO for P0-06C3**.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_p0_06c2_recommendation_action_callbacks.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `docs/report/P0_06C2_RECOMMENDATION_ACTION_CALLBACKS_REPORT.md`

## Action success before/after
### Before
- `prec:act:*` rendered detail and then called `callback.answer(patient.recommendations.action.ok...)`.
- Produced popup result and could create double-answer behavior.

### After
- `prec:act:*` success renders detail with inline localized notice (`patient.recommendations.action.notice.ok`) prepended above the card.
- No post-render manual popup answer.
- Callback answer handling is left to panel send/edit path.

## Action invalid-state before/after
### Before
- `ValueError` branch rendered detail and then `callback.answer(...invalid_state..., show_alert=True)`.

### After
- `ValueError` branch refetches latest recommendation.
- If latest exists and belongs to patient: render detail with inline warning notice (`patient.recommendations.action.notice.invalid_state`).
- If latest missing/not-owned: render inline not-found recovery panel.
- No popup alert on valid invalid-state UX path.

## Action unresolved/not-found behavior
- unresolved patient in `prec:act:*` -> `_render_recommendations_patient_resolution_failed_panel(...)` (My booking/Home).
- recommendation missing/not-owned in `prec:act:*` -> `_render_recommendation_not_found_panel(...)` (Recommendations/My booking/Home).
- malformed callback shape and unknown action continue using unavailable alert guard (stale/invalid callback class).

## Products not-found behavior
- `prec:products:*` missing/not-owned recommendation now uses `_render_recommendation_not_found_panel(...)`.
- manual target invalid / empty products / successful product picker behaviors preserved.

## Notice keys added/reused
Added in both locales:
- `patient.recommendations.action.notice.ok`
- `patient.recommendations.action.notice.invalid_state`

## Double callback-answer cleanup
- Removed manual success popup answer after detail render for `prec:act:*`.
- Removed manual invalid-state popup answer after detail render for `prec:act:*`.
- Valid success/invalid-state/not-found/unresolved action paths now render inline panels without explicit second callback popup.

## Remaining `show_alert=True` classification
Remaining alert usage in recommendation callback area is limited to malformed/stale callback safety guards:
- malformed `prec:open:*` payloads;
- malformed `prec:act:*` payloads;
- malformed `prec:products:*` payloads;
- unknown `prec:act:*` action tokens.

These are invalid callback-shape/staleness guards, not normal UX paths.

## Defects found/fixed
1. Action success popup replaced by inline notice to avoid popup UX and double-answer risk.
2. Invalid-state action popup replaced by inline warning with current/latest detail recovery.
3. Action unresolved and not-found/not-owned popup-only behavior replaced by inline recoverable panels.
4. Products callback not-found popup-only behavior replaced by inline recoverable panel.

## Grep checks (exact commands/results)
1) 
```bash
rg "patient.recommendations.not_found.*show_alert=True|patient.recommendations.patient_resolution_failed.*show_alert=True" app/interfaces/bots/patient/router.py
```
Result: **no matches** ✅

2)
```bash
rg "patient.recommendations.action.ok|patient.recommendations.action.invalid_state" app/interfaces/bots/patient/router.py
```
Result: no direct action popup usage remains for callback success/invalid-state; callback path uses inline notice keys. ✅

3)
```bash
rg "await _render_recommendation_detail_panel\(|await callback.answer\(" app/interfaces/bots/patient/router.py
```
Manual check: no unconditional callback-answer after detail render in action success/invalid-state paths. ✅

4)
```bash
rg "prec:act:ack|prec:act:accept|prec:act:decline|prec:products:" app/interfaces/bots/patient/router.py tests/test_p0_06c2_recommendation_action_callbacks.py
```
Result: callback generation/handlers and dedicated C2 coverage present. ✅

## Tests run (exact commands/results)
- `python -m compileall app tests`
- `pytest -q tests/test_p0_06c2_recommendation_action_callbacks.py`
- `pytest -q tests/test_p0_06c1_recommendation_detail_card.py`
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py`
- `pytest -q tests/test_p0_06b3b1_recommendation_command_fallbacks.py`
- `pytest -q tests/test_p0_06a2_recommendations_entry_empty_states.py`
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py`
- `pytest -q tests -k "care or recommendation"`

Results:
- `python -m compileall app tests` ✅ pass
- `pytest -q tests/test_p0_06c2_recommendation_action_callbacks.py` ✅ pass (10 passed)
- `pytest -q tests/test_p0_06c1_recommendation_detail_card.py` ✅ pass (9 passed)
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` ✅ pass (3 passed)
- `pytest -q tests/test_p0_06b3b1_recommendation_command_fallbacks.py` ✅ pass (14 passed)
- `pytest -q tests/test_p0_06a2_recommendations_entry_empty_states.py` ✅ pass (4 passed)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` ✅ pass (4 passed)
- `pytest -q tests -k "care or recommendation"` ✅ pass (186 passed, 504 deselected, 2 unrelated pytest mark warnings)

## Carry-forward for P0-06C3
- recommendation list/history visual polish;
- list status filtering;
- latest/history card readability tuning.

## GO / NO-GO for P0-06C3
**GO**.

Rationale:
- action callbacks now match inline panel UX patterns introduced in C1;
- success/invalid-state/not-found/unresolved paths are recoverable without popup-only blockers;
- callback-answer hygiene improved (no valid-path double answers);
- core recommendation/care regression suites remain green.
