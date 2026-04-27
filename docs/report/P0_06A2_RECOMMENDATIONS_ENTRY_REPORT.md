# P0-06A2 Recommendations entry empty states recovery report

## Summary
Implemented recommendation-entry-specific empty/unavailable/failure recovery panels, improved recommendation detail navigation, and removed success-path double callback answers for recommendation entry/detail callbacks.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_p0_06a2_recommendations_entry_empty_states.py`

## Recommendations unavailable before/after
- **Before:** recommendation entry used a generic home unavailable copy for module-unavailable state.
- **After:** recommendation entry now renders `patient.recommendations.unavailable.panel` with explicit recommendation-module copy and actionable navigation buttons (My booking, Home).

## Patient resolution failure behavior
- **Before:** patient-resolution failure used a generic short text path and could be surfaced as alert-only in callback flows.
- **After:** recommendation entry renders `patient.recommendations.patient_resolution_failed.panel` as an inline panel with actionable buttons (My booking, Home).

## Empty state behavior
- **Before:** empty recommendation list used the previous `patient.recommendations.empty` copy.
- **After:** recommendation entry now uses `patient.recommendations.empty.panel` copy with focused after-visit wording and the same actionable buttons (My booking, Home).

## Detail navigation behavior
- Recommendation detail panel retains existing detail content and action buttons.
- Added explicit navigation buttons:
  - Back to recommendations list (`phome:recommendations`)
  - Home (`phome:home`)

## Double callback-answer cleanup
- Removed redundant `callback.answer()` on success paths for:
  - `patient_home_recommendations`
  - `recommendation_open_callback`
- These paths now rely on `_send_or_edit_panel(...)` acknowledgement behavior, avoiding unconditional double answers.

## Tests run
- `python -m compileall app tests`
- `pytest -q tests/test_p0_06a2_recommendations_entry_empty_states.py`
- `pytest -q tests/test_p0_06a1_care_entry_empty_states.py`
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py`
- `pytest -q tests/test_p0_05b_my_booking_action_panels.py`

## Grep checks
- `rg "patient.home.action.unavailable" app/interfaces/bots/patient/router.py`
  - Result: no matches (not used for active recommendation entry unavailable path).
- `rg "patient.recommendations.patient_resolution_failed|patient.recommendations.unavailable|patient.recommendations.empty" app/interfaces/bots/patient/router.py locales tests`
  - Result: recommendation panel keys and references present in router/locales.
- `rg "await _enter_recommendations_list\(callback|await _render_recommendation_detail_panel" app/interfaces/bots/patient/router.py`
  - Result: recommendation entry/detail render call sites verified; no unconditional success `callback.answer()` retained in the touched entry/detail handlers.

## Carry-forward for P0-06A3
- Recommendation products empty/manual-invalid handling should be completed in P0-06A3:
  - recommendation products empty/manual-invalid

## Go/no-go for P0-06A3
- **Go**: entry-level recommendation unavailable/empty/unresolved states are now readable and navigable; detail has Back/Home; targeted regression tests pass.
