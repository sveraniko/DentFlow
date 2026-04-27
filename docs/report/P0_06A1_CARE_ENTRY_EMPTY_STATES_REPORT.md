# P0_06A1 — Care entry empty states recovery report

## Summary
Implemented care-entry-only empty-state recovery for patient surfaces:
- care module unavailable now shows a care-specific panel with navigation to My Booking and Home;
- empty care catalog now shows a readable care-specific panel with My Booking and Home;
- empty category now shows a readable panel with Back to categories and Home;
- removed callback double-answer on success paths for `patient_home_care` and `care_catalog_callback`.

Scope intentionally excludes recommendations/products/orders/reserve/order creation/router split/DB/schema/CardShellRenderer.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_p0_06a1_care_entry_empty_states.py`

## Care module unavailable (before/after)
### Before
- Entering care with `care_commerce_service is None` used generic `patient.home.action.unavailable`.
- No care-specific guidance.

### After
- Entry now renders `patient.care.unavailable.panel`.
- Keyboard:
  - `📅 My booking` -> `phome:my_booking`
  - `🏠 Main menu` -> `phome:home`

## Care catalog empty (before/after)
### Before
- Empty categories used generic-ish catalog unavailable copy and only home nav.

### After
- Empty categories render `patient.care.catalog.empty.panel` with care-specific readable copy.
- Keyboard:
  - `📅 My booking` -> `phome:my_booking`
  - `🏠 Main menu` -> `phome:home`

## Care category empty (before/after)
### Before
- Empty category used a short generic line and only back action.

### After
- Empty category renders `patient.care.catalog.category.empty.panel`.
- Keyboard:
  - `⬅️ Back to categories` -> existing runtime callback (`back_categories`)
  - `🏠 Main menu` -> `phome:home`

## Callback double-answer cleanup
- Removed trailing `await callback.answer()` in:
  - `patient_home_care`
  - `care_catalog_callback`
- Success paths now rely on helper render flow (no extra success popup answer).
- Validation/stale alert branches remain unchanged.

## Tests run (exact commands/results)
- `python -m compileall app tests` — PASS
- `pytest -q tests/test_p0_06a1_care_entry_empty_states.py` — PASS (`3 passed`)
- `pytest -q tests/test_p0_05c_my_booking_smoke_gate.py` — PASS (`4 passed`)
- `pytest -q tests/test_p0_05b_my_booking_action_panels.py` — PASS (`6 passed`)
- `pytest -q tests/test_p0_05a_my_booking_readable_card.py` — PASS (`5 passed`)

## Grep checks
1) `rg "patient.home.action.unavailable" app/interfaces/bots/patient/router.py`
- Result: one remaining usage at line 2550, outside active care entry unavailable path.

2) `rg "patient.care.catalog.empty|patient.care.unavailable|patient.care.catalog.category.empty" app/interfaces/bots/patient/router.py locales tests`
- Result: new keys present in locales and used in router.

3) `rg "await _enter_care_catalog\(callback|await _render_care" app/interfaces/bots/patient/router.py`
- Reviewed: no unconditional `await callback.answer()` immediately after `await _enter_care_catalog(callback, ...)` in touched entry handlers.

## Carry-forward for P0-06A3
- care orders unresolved patient behavior: not addressed in this PR.
- care reserve unresolved patient behavior: not addressed in this PR.

## Go / no-go for P0-06A2
Go.
- Entry-level care empty states are now readable and navigable.
- Required smoke gates remain green.
