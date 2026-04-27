# P0-04B — Patient booking review edit actions report

## Summary
Implemented functional review edit actions for service, doctor, time, and phone in the patient booking flow. Edit callbacks now route to real picker/contact stages, release stale holds for service/doctor/time edits, preserve selected slot for phone edit, and return to polished review after re-selection when contact/patient are already present.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `app/application/booking/telegram_flow.py`
- `locales/ru.json`
- `locales/en.json`
- `tests/test_patient_first_booking_review_pat_a1_1.py`
- `tests/test_booking_patient_review_confirm_pat_a1_1a.py`
- `tests/test_p0_03d_patient_booking_smoke_gate.py`

## New review keyboard layout
1. `✅ Подтвердить запись` / `✅ Confirm booking` → `book:confirm:{session_id}`
2. `✏️ Изменить услугу` / `✏️ Edit service` → `book:review:edit:service:{session_id}`
3. `✏️ Изменить врача` / `✏️ Edit doctor` → `book:review:edit:doctor:{session_id}`
4. `✏️ Изменить время` / `✏️ Edit time` → `book:review:edit:time:{session_id}`
5. `✏️ Изменить телефон` / `✏️ Edit phone` → `book:review:edit:phone:{session_id}`
6. `⬅️ Назад` / `⬅️ Back` → `book:review:back:{session_id}`
7. `🏠 Главное меню` / `🏠 Main menu` → `phome:home`

## New callback map
Added handler namespace:
- `book:review:edit:{field}:{session_id}`
- Allowed fields: `service`, `doctor`, `time`, `phone`

Validation and guard behavior:
- Requires `from_user`
- Requires primary clinic
- Uses `validate_active_session_callback(...)`
- Validates session ownership and non-terminal status
- Stale callback → alert
- Post-validation flow/setup failures → readable panel + Home

## Edit service behavior
- Releases selected hold/slot via flow service
- Resets slot view state (`page/date/window/suppressed`)
- Sets mode to `review_edit_service`
- Clears quick booking prefill + reschedule context
- Renders service picker
- On service select in `review_edit_service`:
  - Clears doctor preference
  - Sets mode to `review_edit_doctor`
  - Renders doctor picker

## Edit doctor behavior
- Releases selected hold/slot
- Resets slot view state
- Sets mode to `review_edit_doctor`
- Renders doctor picker
- Doctor selection continues to slot panel

## Edit time behavior
- Releases selected hold/slot
- Resets slot view state
- Sets mode to `review_edit_time`
- Renders slot picker directly

## Edit phone behavior
- Does **not** release hold
- Does **not** clear selected slot
- Sets mode to `review_edit_phone`
- Renders contact prompt with reply keyboard (share/back/home)
- On phone submission:
  - Updates contact phone
  - Resolves patient
  - Marks review ready
  - Removes reply keyboard
  - Renders polished review panel

## Hold release behavior
Added `BookingPatientFlowService.release_selected_slot_for_reselect(...)`:
- Returns invalid state if session missing
- Returns success without orchestration call if no hold/slot selected
- Otherwise calls `release_or_expire_hold_for_session(..., action="released")`

## Slot selection after review-edit behavior
Updated slot selection success path:
- If mode is one of `review_edit_service|review_edit_doctor|review_edit_time`
- and session already has `contact_phone_snapshot` + `resolved_patient_id`
- then marks review-ready and returns to polished review panel
- skips contact prompt in that case
- otherwise falls back to normal contact prompt path

## Contact keyboard behavior
- `on_contact_text(...)` accepts `review_edit_phone`
- `on_contact_navigation(...)` Home removes reply keyboard for review-edit phone mode
- `on_contact_navigation(...)` Back from review-edit phone:
  - removes reply keyboard
  - restores safe non-contact mode (`new_booking_flow`)
  - returns to review panel (not slot panel)

## Tests run with exact commands/results
- `python -m compileall app tests` ✅ pass
- `pytest -q tests/test_p0_03d_patient_booking_smoke_gate.py` ✅ pass (6 passed)
- `pytest -q tests/test_booking_patient_review_confirm_pat_a1_1a.py` ✅ pass (1 passed)
- `pytest -q tests/test_patient_first_booking_review_pat_a1_1.py tests/test_patient_home_surface_pat_a1_2.py tests/test_patient_existing_booking_shortcut_pat_a3_2.py` ✅ pass (89 passed)
- `pytest -q tests/test_patient_reschedule_start_pat_a4_1.py` ✅ pass (16 passed)
- `pytest -q tests -k "patient and booking"` ✅ pass (105 passed, 479 deselected)

## Grep checks
- `rg "book:review:edit:" app/interfaces/bots/patient tests` ✅ callbacks present in router + tests
- `rg "patient.booking.review.edit" locales app/interfaces/bots/patient tests` ✅ locale keys and usages present
- `rg "review_edit_service|review_edit_doctor|review_edit_time|review_edit_phone" app/interfaces/bots/patient tests` ✅ modes handled explicitly
- `rg "callback_data=f\"book:review:edit" app/interfaces/bots/patient/router.py` ✅ review keyboard callback definitions present


## P0-04B matrix (post-check)

### Review
- edit service button: **yes**
- edit doctor button: **yes**
- edit time button: **yes**
- edit phone button: **yes**

### Edit service
- old hold released: **yes**
- slot cleared: **yes**
- service picker shown: **yes**
- after service -> doctor picker: **yes**

### Edit doctor
- old hold released: **yes**
- slot cleared: **yes**
- doctor picker shown: **yes**
- after doctor -> slot picker: **yes**

### Edit time
- old hold released: **yes**
- slot cleared: **yes**
- slot picker shown: **yes**
- after slot -> review if contact exists: **yes**

### Edit phone
- hold not released: **yes**
- contact keyboard shown: **yes**
- Back returns review: **yes**
- Home removes keyboard: **yes**
- phone submit returns review: **yes**

### Regression
- normal booking still works: **yes**
- P0-03D smoke passes: **yes**
- patient and booking subset: **105 passed**

## Carry-forward for P0-04C smoke gate and reschedule review datetime polish
- Keep callback namespace allowlist synchronized with any new booking callback prefixes.
- Add explicit smoke coverage for `book:review:edit:*` stale-callback and release-failure branches.
- Validate no regressions in reschedule review datetime formatting while iterating on shared review panel formatting helpers.
