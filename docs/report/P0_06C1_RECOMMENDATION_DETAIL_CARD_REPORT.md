# P0-06C1 — Recommendation detail readable card + open callback recovery report

## Summary
Implemented P0-06C1 recommendation polish focused on:
- readable localized recommendation detail card;
- status-aware detail keyboard actions;
- inline recovery for `prec:open:*` unresolved/not-found paths;
- callback-answer hygiene on open/detail path (no manual double-answer);
- regression-safe product handoff.

Result: **GO for P0-06C2**.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_p0_06c1_recommendation_detail_card.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `docs/report/P0_06C1_RECOMMENDATION_DETAIL_CARD_REPORT.md`

## Detail card before/after

### Before
- Minimal detail block from `patient.recommendations.detail.panel` with plain title/type/status/body.
- Included static action row regardless of status (`ack/accept/decline`).

### After
- Structured patient-facing card with localized title/badge/fields/body/next-step:
  - title: `patient.recommendations.detail.title`
  - status badge: `patient.recommendations.detail.status_badge.*`
  - fields: topic/type/status
  - readable body (missing value fallback + safe trim marker)
  - optional next step by status (`patient.recommendations.detail.next.*`)
- No raw/debug/internal fields are rendered in detail text.

## Status badge map
Implemented localized badge keys:
- `issued`
- `viewed`
- `acknowledged`
- `accepted`
- `declined`
- `withdrawn`
- `expired`
- `prepared`
- `draft`

## Status-aware keyboard rules
Implemented status-based action layout:
- `issued`, `viewed`: show ack + accept + decline.
- `acknowledged`: show accept + decline (no ack re-show).
- terminal statuses (`accepted`, `declined`, `withdrawn`, `expired`, `completed`): no mutation actions.
- `prepared`, `draft`: no mutation actions.
- products button shown only when recommendation target exists and status is not `withdrawn`/`expired`.
- always show back to list and home.

## `prec:open:*` unresolved/not-found behavior
- unresolved patient now renders inline `patient.recommendations.patient_resolution_failed.panel` with My booking/Home recovery.
- missing/not-owned recommendation now renders inline not-found panel (using `patient.recommendations.command.not_found.panel`) with Recommendations/My booking/Home.
- malformed callback shape still uses popup alert guard.

## Mark-viewed behavior
- Existing behavior retained: opening `issued` recommendation triggers `mark_viewed(...)` before detail render.
- Post-mark detail shows viewed badge/label and viewed action rules.

## No double callback-answer on open/detail path
- For valid `prec:open:*` success and inline recovery branches, no additional manual popup answer is sent after panel render.
- Callback answer remains only for malformed/stale guard callbacks.

## Defects found/fixed
1. Detail card readability/localization gap fixed by card template + field/status helpers.
2. Always-on mutation actions replaced with status-aware rules.
3. `prec:open:*` unresolved/not-found popup-only behavior replaced by inline recovery panels.
4. Products CTA visibility aligned with status rules (hidden for withdrawn/expired).
5. Updated historical test expectations for recommendation not-found text and products CTA emoji label.

## Grep checks (exact commands/results)

1) Old detail template active check
```bash
rg 'patient.recommendations.detail.panel|patient.recommendations.detail"' app/interfaces/bots/patient/router.py
```
Result: **no matches** ✅

2) Popup-only unresolved/not-found recommendation checks
```bash
rg "patient.recommendations.not_found.*show_alert=True|patient.recommendations.patient_resolution_failed.*show_alert=True" app/interfaces/bots/patient/router.py
```
Result: 3 matches for `patient.recommendations.not_found ... show_alert=True` remain in non-open paths (`prec:act:*` and `prec:products:*`) and are carry-forward to next polish scopes; no `patient_resolution_failed ... show_alert=True` matches. ✅

3) Action callback generation presence
```bash
rg "prec:act:ack|prec:act:accept|prec:act:decline" app/interfaces/bots/patient/router.py tests/test_p0_06c1_recommendation_detail_card.py
```
Result: expected matches in status-aware keyboard builder and C1 tests. ✅

4) Leak markers in C1 test file
```bash
rg "Actions:|Channel:|Канал:|source_channel|telegram|recommendation_id|patient_id|booking_id|doctor_id" tests/test_p0_06c1_recommendation_detail_card.py
```
Result: markers appear only in controlled fixture wiring and negative assertion list. ✅

## Tests run (exact commands/results)
- `python -m compileall app tests` ✅ pass
- `pytest -q tests/test_p0_06c1_recommendation_detail_card.py` ✅ pass (9 passed)
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` ✅ pass (3 passed)
- `pytest -q tests/test_p0_06b3b1_recommendation_command_fallbacks.py` ✅ pass (14 passed)
- `pytest -q tests/test_p0_06a2_recommendations_entry_empty_states.py` ✅ pass (4 passed)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` ✅ pass (4 passed)
- `pytest -q tests -k "care or recommendation"` ✅ pass (176 passed, 504 deselected, 2 unrelated pytest mark warnings)

## Carry-forward for P0-06C2
- Recommendation action callback success/invalid-state inline notices.
- Remove popup result on valid recommendation actions.
- No double answer after recommendation action render paths.

## GO / NO-GO for P0-06C2
**GO**.

Rationale:
- Readable localized detail card is in place.
- Status-aware keyboard behavior is implemented and tested across actionable/terminal/draft/prepared states.
- `prec:open:*` valid unresolved/not-found paths are inline recoverable.
- Product handoff is preserved.
- B4/B3B1/A2/P0-05C regressions pass in this branch.
