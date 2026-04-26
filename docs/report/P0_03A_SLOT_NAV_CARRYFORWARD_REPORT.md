# P0-03A — Slot/navigation carry-forward cleanup report

## Summary
- Fixed service picker Back self-loop: Back now routes to patient home (`phome:home`) instead of re-rendering services.
- Added reply-keyboard cleanup when leaving contact/doctor-code text navigation paths.
- Removed duplicate callback answers on success paths in P0-02B callback handlers.
- Added slot view state foundation fields with backward-compatible load/save defaults and reset helper.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `docs/report/P0_03A_SLOT_NAV_CARRYFORWARD_REPORT.md`

## Carry-forward issues fixed
1. **Service picker Back self-loop**
   - Service picker Back button callback now uses `phome:home`.
   - `book:back:services:{session_id}` handler now returns to patient home panel.
2. **Reply keyboard cleanup from contact stage**
   - Added `_remove_patient_reply_keyboard(message)` using `ReplyKeyboardRemove`.
   - Home and Back text navigation from `new_booking_contact` now removes keyboard before rendering inline panels.
   - Back text navigation from `new_booking_doctor_code` also removes stale keyboard before rendering doctor picker.
3. **Double callback answer risk**
   - Removed explicit trailing `callback.answer()` calls from:
     - `booking_back_to_services`
     - `booking_back_to_doctors`
     - `booking_doctor_code_prompt`
   - Success paths now rely on `_send_or_edit_panel(...)` callback answering.
   - Alert/error branches with `show_alert=True` were preserved.
4. **Slot state foundation**
   - Added `_PatientFlowState` fields:
     - `slot_page: int = 0`
     - `slot_date_from: str = ""`
     - `slot_time_window: str = "all"`
   - Extended `_load_flow_state(...)` and `_save_flow_state(...)` accordingly.
   - Added `_reset_slot_view_state(flow)` and invoked on:
     - new booking entry,
     - service change,
     - doctor preference change,
     - doctor code successful resolution,
     - quick-book prefill paths that change service/doctor.

## Callback map after cleanup
- Service picker Back: `phome:home`
- Service picker Home: `phome:home`
- Doctor picker Back: `book:back:doctors:{session_id}`
- Doctor-code prompt Back: `book:back:doctors:{session_id}`

## ReplyKeyboardRemove behavior
- Implemented lightweight cleanup send/delete flow:
  - send short `↩️` message with `ReplyKeyboardRemove()`
  - best-effort delete
  - ignore cleanup errors (no crash)

## Slot state fields added
- Added defaults and persistence keys:
  - `slot_page`
  - `slot_date_from`
  - `slot_time_window`
- Verified compatibility with payloads that omit these keys.

## Tests run with exact commands/results
- `python -m compileall app tests` — PASS
- `pytest -q tests/test_patient_home_surface_pat_a1_2.py tests/test_patient_first_booking_review_pat_a1_1.py tests/test_patient_existing_booking_shortcut_pat_a3_2.py` — PASS

## Grep checks
- `rg "book:back:services" app/interfaces/bots/patient/router.py tests`
- Result: `book:back:services` remains as callback handler route; service picker Back rendering no longer uses it.

## Carry-forward for P0-03B
- Slot state fields are now present and resettable without changing slot UI behavior.
- P0-03B can safely add localized slot pagination/date/time-window controls using these persisted state fields.
