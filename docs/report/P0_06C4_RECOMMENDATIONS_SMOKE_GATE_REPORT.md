# P0-06C4 Recommendations Consolidated Smoke Gate Report

## Summary
- Added a consolidated recommendations smoke gate test suite that exercises entry/list/detail/actions/products/command-fallback callback flows end-to-end without introducing product behavior changes.
- Re-ran C1/C2/C3/B4/A2 + cross-cut subsets to validate no regression on prior contracts.
- Result: **GO** for next phase.

## Files changed
- `tests/test_p0_06c4_recommendations_smoke_gate.py`
- `docs/report/P0_06C4_RECOMMENDATIONS_SMOKE_GATE_REPORT.md`

## Smoke matrix

| Area | Coverage | Result |
|---|---|---|
| Entry | module unavailable panel, unresolved patient recovery, empty list readable state, My Booking/Home presence, no generic unavailable in active path | PASS |
| List filters | active/history/all filters, default active/history selection, terminal visibility in history, all includes mixed states, no raw/debug ids | PASS |
| List pagination | `RECOMMENDATION_LIST_PAGE_SIZE=5`, page split, next/prev, clamp on overlarge page, malformed safe alert | PASS |
| Detail open | `prec:open:{id}` from list, C1 readable detail, unresolved/not-found recovery inline, not popup-only valid path | PASS |
| Status-aware keyboard | issued/viewed actions present, acknowledged hides ack, terminal/draft/prepared hide mutation actions, Back/Home always present | PASS |
| Actions | ack/accept/decline inline success + updated detail, invalid-state warning + detail, unresolved/not-found inline recovery, unknown action safe alert | PASS |
| Products handoff | `prec:products:{id}` presence, success picker open, manual-invalid/empty structured recovery, unresolved/not-found recovery, expected nav buttons | PASS |
| Command fallbacks | smoke integration for `/recommendation_open`, `/recommendation_action`, `/recommendation_products` plus full B3B1 run | PASS |
| Callback namespace | collected callback_data from smoke keyboards; validated only allowed prefixes + runtime `c2|` | PASS |
| Double callback-answer | asserted `len(answer_payloads) <= 1` across valid callback render paths | PASS |
| Raw/debug/internal leakage | guarded list/detail/action/products against raw/internal tokens and technical datetime markers | PASS |

## Grep checks with exact commands/results

1) Old rough list keys in active renderer
```bash
rg "patient.recommendations.latest.label|patient.recommendations.history.item|patient.recommendations.open_history.button" app/interfaces/bots/patient/router.py
```
Result: **no matches** (exit code 1).

2) `prec:list:` handler + smoke test presence
```bash
rg "prec:list:" app/interfaces/bots/patient/router.py tests/test_p0_06c4_recommendations_smoke_gate.py
```
Result: matched callback construction/handler in router and smoke callbacks in C4 test.

3) popup-only not-found/patient-resolution patterns
```bash
rg "patient.recommendations.not_found.*show_alert=True|patient.recommendations.patient_resolution_failed.*show_alert=True" app/interfaces/bots/patient/router.py
```
Result: **no matches** (exit code 1).

4) render paths vs callback.answer call sites (manual inspection support)
```bash
rg "await _render_recommendations_panel\(|await _render_recommendation_detail_panel\(|await callback.answer\(" app/interfaces/bots/patient/router.py
```
Result: recommendation render calls present; `callback.answer` exists for unavailable/malformed/stale paths; no unconditional post-render answer observed in recommendation valid-flow handlers.

5) Leakage tokens in C4 smoke file
```bash
rg "Actions:|Channel:|Канал:|source_channel|telegram|recommendation_id|patient_id|booking_id|doctor_id" tests/test_p0_06c4_recommendations_smoke_gate.py
```
Result: tokens appear in forbidden assertion list and fixture field setup only.

6) Technical datetime markers in C4 smoke file
```bash
rg "UTC|MSK|%Z|2026-04-" tests/test_p0_06c4_recommendations_smoke_gate.py
```
Result: markers appear in forbidden assertion list only.

## Tests run with exact commands/results

- `python -m compileall app tests` → PASS
- `pytest -q tests/test_p0_06c4_recommendations_smoke_gate.py` → PASS (`9 passed`)
- `pytest -q tests/test_p0_06c3_recommendation_list_history.py` → PASS (`10 passed`)
- `pytest -q tests/test_p0_06c2_recommendation_action_callbacks.py` → PASS (`10 passed`)
- `pytest -q tests/test_p0_06c1_recommendation_detail_card.py` → PASS (`9 passed`)
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` → PASS (`3 passed`)
- `pytest -q tests/test_p0_06b3b1_recommendation_command_fallbacks.py` → PASS (`14 passed`)
- `pytest -q tests/test_p0_06a2_recommendations_entry_empty_states.py` → PASS (`4 passed`)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` → PASS (`4 passed`)
- `pytest -q tests -k "care or recommendation"` → PASS (`204 passed, 504 deselected`; 2 unrelated `PytestUnknownMarkWarning` warnings)
- `pytest -q tests -k "patient and booking"` → PASS (`105 passed, 603 deselected`; same 2 warnings)

## Defects found/fixed
- No product/runtime defects in recommendation contour discovered by C4 smoke.
- No fixes required in router/domain/card renderer for this scope.

## Defects carried forward
- None in recommendations contour from this gate.
- Existing global pytest warnings about unknown `pytest.mark.asyncio` remain unrelated to C4.

## Remaining show_alert classification
- Recommendation-valid paths (`phome:recommendations`, `prec:list:*` valid, `prec:open:*` valid, `prec:act:ack/accept/decline`, `prec:products:*` valid) are covered by inline panel render and guarded against double-answer.
- Remaining popup alerts are classified as malformed/stale/unavailable safety behavior.

## GO / NO-GO recommendation
**GO** for next step.

Rationale:
- New consolidated C4 smoke gate is in place.
- Prior C1/C2/C3/B4/A2 contracts remain green.
- Recommendation flow remains end-to-end covered with namespace, double-answer, and leakage guards.
