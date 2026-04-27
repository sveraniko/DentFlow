# P0-03C Slot Conflict Inline Notice Report

## Summary
Implemented patient slot-conflict UX hardening for booking and reschedule slot completion flows:
- replaced popup conflict/unavailable alerts with inline notice rendering inside the slot panel;
- prevented stale failed slot re-selection by adding transient per-flow slot suppression;
- clamped slot page index after filtering/suppression so valid earlier pages are shown;
- handled `InvalidStateOutcome` from slot selection without leaking into contact stage;
- preserved successful slot-selection/contact behavior.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_patient_first_booking_review_pat_a1_1.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `tests/test_patient_reschedule_start_pat_a4_1.py`

## Conflict UX before / after

### Before
- `select_slot(...)` used callback popups (`show_alert=True`) for `SlotUnavailableOutcome`/`ConflictOutcome`.
- `reschedule_confirm(...)` used callback popups for slot unavailable/conflict outcomes.
- slot list refresh could still include failed slot in same flow.
- page index could remain out-of-range and produce false empty panels.

### After
- conflict/unavailable outcomes render inline notice above slot panel body.
- popup alerts removed from these conflict branches.
- failed slot id is transiently suppressed in flow state and filtered from render.
- slot page is clamped to the highest valid page after filtering/suppression.

## New locale keys
Added to both RU/EN:
- `patient.booking.slot.notice.unavailable`
- `patient.booking.slot.notice.conflict`

## Suppressed slot state behavior
Added `slot_suppressed_ids` to patient flow state (serialized in runtime payload):
- bounded to last 20 ids;
- appended on slot conflict/unavailable selection failure;
- filtered out in `_render_slot_panel(...)`;
- reset when context changes via slot view reset and date/time-window filter changes.

## Page clamp behavior
`_render_slot_panel(...)` now computes safe page based on filtered count and `SLOT_PAGE_SIZE`:
- if current page is above last page and filtered slots are present, page is clamped and persisted;
- if filtered list is empty, empty filtered state is shown.

## Select-slot outcome map
- **Success (`OrchestrationSuccess`)** → unchanged: new booking goes to contact stage (`new_booking_contact`), reschedule route goes to reschedule review.
- **`SlotUnavailableOutcome`** → suppress selected slot + rerender slot panel with inline unavailable notice.
- **`ConflictOutcome`** → suppress selected slot + rerender slot panel with inline unavailable notice.
- **`InvalidStateOutcome`** → rerender slot panel with inline unavailable notice; no transition to contact stage.

## Reschedule conflict behavior
In `reschedule_confirm(...)`:
- `SlotUnavailableOutcome` and `ConflictOutcome` now rerender slot panel with inline notice;
- no popup alert is used in these branches;
- success handoff to canonical booking panel remains unchanged.

## P0-03C matrix

| Scenario | Popup `show_alert` | Inline notice | Slot suppressed | Contact keyboard shown | Contact stage entered | Session recovery | Page corrected after suppression | False empty state avoided | Slot panel refreshed | Contact reply keyboard still shown |
|---|---|---|---|---|---|---|---|---|---|---|
| New booking slot unavailable | no | yes | yes | no | — | — | — | — | — | — |
| New booking slot conflict | no | yes | yes | no | — | — | — | — | — | — |
| InvalidStateOutcome | no | yes | — | no | no | yes | — | — | — | — |
| Page clamp | no | — | yes | — | — | — | yes | yes | — | — |
| Reschedule confirm conflict | no | yes | — | — | — | — | — | — | yes | — |
| Success path | — | — | — | — | — | — | — | — | — | yes |

Legend: `—` means "not applicable for this scenario".

## Tests run
1. `python -m compileall app tests` — **pass**
2. `pytest -q tests/test_p0_03a_nav_callback_contract.py` — **pass** (6 passed)
3. `pytest -q tests/test_patient_home_surface_pat_a1_2.py tests/test_patient_first_booking_review_pat_a1_1.py tests/test_patient_existing_booking_shortcut_pat_a3_2.py` — **pass** (81 passed)
4. `pytest -q tests/test_patient_reschedule_start_pat_a4_1.py` — **pass** (16 passed)
5. `pytest -q tests -k "slot and patient"` — **pass** (19 passed, deselections; warnings unrelated to this task)

## Grep checks
1. `rg "patient.booking.slot.unavailable.*show_alert=True|reschedule.complete.slot_unavailable.*show_alert=True|reschedule.complete.conflict.*show_alert=True" app/interfaces/bots/patient/router.py`
2. `rg "await callback.answer\(i18n.t\("patient.booking.slot.unavailable"" app/interfaces/bots/patient/router.py`

Result: no matches for popup alerts in slot unavailable/conflict branches.

## Carry-forward for P0-03D / P0-04
- Consider extending suppression to server-reported hold ids if/when exposed from orchestration outcomes.
- Consider dedicated `patient.booking.slot.notice.invalid_state` locale key if UX copy needs separation.
- Monitor if provider-side slot race windows require additional session freshness telemetry.
