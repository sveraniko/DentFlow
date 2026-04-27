# P0-06C3 — Recommendation list/history polish

## Summary
Implemented a polished recommendations list/history surface for patient entry points and list callbacks:
- replaced rough latest/history surface with structured, localized list panel;
- added `active` / `history` / `all` filters with consistent callbacks;
- added page-based list navigation and page clamp behavior;
- ensured terminal recommendations are fetched for list/history when supported;
- kept detail card and recommendation action callback behavior from C1/C2 intact;
- added focused C3 tests and verified required regressions.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `tests/test_p0_06c3_recommendation_list_history.py`
- `docs/report/P0_06C3_RECOMMENDATION_LIST_HISTORY_REPORT.md`

## List before/after
### Before
- rough “latest + history[:5]” text;
- no explicit active/history/all filters;
- no page callbacks for list browsing;
- history exposure depended on default row set.

### After
- structured list with title, active/history counters, section, page;
- readable row block with status badge, type, status, patient-facing date;
- filter row (`prec:list:{filter}:0`) always visible;
- pagination row (`prev/next`) appears when needed;
- row open buttons mapped to `prec:open:{recommendation_id}` without exposing ids in button text.

## Active/history/all filter behavior
- `active`: `issued`, `viewed`, `acknowledged`
- `history`: `accepted`, `declined`, `withdrawn`, `expired`
- `all`: all statuses (including `draft`/`prepared`)

Default selection:
- active if active rows exist;
- else history if terminal rows exist;
- else all.

## Pagination behavior
- Added `RECOMMENDATION_LIST_PAGE_SIZE = 5`.
- List rows are sliced per current page.
- Callback format: `prec:list:{filter}:{page}`.
- Page index is clamped to valid range.
- malformed callback shape/filter/page uses unavailable alert guard.

## Sorting behavior
- Rows are sorted descending by:
  1) `updated_at`
  2) `issued_at`
  3) `created_at`
- Sorting is applied before filter + pagination.

## Empty filter states
- Added localized filter-empty messages:
  - `patient.recommendations.list.filter_empty.active`
  - `patient.recommendations.list.filter_empty.history`
  - `patient.recommendations.list.filter_empty.all`
- Filter buttons + My Booking + Home stay visible even when selected filter page has no rows.

## Callback map
- `phome:recommendations` → polished list entry
- `/recommendations` → polished list entry
- `prec:list:{filter}:{page}` → polished list render for selected filter/page
- `prec:open:*`, `prec:act:*`, `prec:products:*` behavior preserved

## No double-answer check
- Valid list render paths (`phome:recommendations`, valid `prec:list:*`) render via panel send/edit without extra manual callback answer.
- malformed `prec:list:*` retains explicit unavailable alert guard.

## Defects found/fixed
1. Legacy tests expected old “Latest recommendation” phrasing; updated baseline list-surface assertion in existing test.
2. Stub recommendation service now accepts `include_terminal` and emulates terminal exclusion when false, allowing C3 behavior validation.

## Grep checks (exact commands/results)
1)
```bash
rg "patient.recommendations.latest.label|patient.recommendations.history.item|patient.recommendations.open_history.button" app/interfaces/bots/patient/router.py
```
Result: no matches ✅

2)
```bash
rg "prec:list:" app/interfaces/bots/patient/router.py tests/test_p0_06c3_recommendation_list_history.py
```
Result: handler + callback generation + dedicated tests present ✅

3)
```bash
rg "recommendation_id|patient_id|booking_id|doctor_id|source_channel|telegram|Actions:|Channel:" tests/test_p0_06c3_recommendation_list_history.py
```
Result: fixture setup + negative assertions only ✅

4)
```bash
rg "UTC|MSK|%Z|2026-04-" tests/test_p0_06c3_recommendation_list_history.py
```
Result: negative assertions only ✅

5)
```bash
rg "await _render_recommendations_panel\(|await callback.answer\(" app/interfaces/bots/patient/router.py
```
Manual check: no unconditional `callback.answer(...)` immediately after valid list render paths; alerts remain for malformed/stale guards ✅

## Tests run (exact commands/results)
- `python -m compileall app tests` ✅ pass
- `pytest -q tests/test_p0_06c3_recommendation_list_history.py` ✅ pass (9 passed)
- `pytest -q tests/test_p0_06c2_recommendation_action_callbacks.py` ✅ pass (10 passed)
- `pytest -q tests/test_p0_06c1_recommendation_detail_card.py` ✅ pass (9 passed)
- `pytest -q tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py` ✅ pass (3 passed)
- `pytest -q tests/test_p0_06a2_recommendations_entry_empty_states.py` ✅ pass (4 passed)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` ✅ pass (4 passed)
- `pytest -q tests -k "care or recommendation"` ❌ initially failed (1 legacy test assertion for old list text), then fixed and re-run ✅ pass (195 passed, 504 deselected, 2 warnings)

## Carry-forward for P0-06C4
- add consolidated recommendation smoke gate that includes:
  - list filters + pagination,
  - detail open path,
  - action callback inline notices,
  - product handoff recovery paths.

## GO / NO-GO for P0-06C4
**GO**.

Rationale:
- list surface now readable/localized and patient-safe;
- terminal history visibility, filters, and pagination are in place;
- callback behavior for C1/C2 paths remains stable under regression suite.
