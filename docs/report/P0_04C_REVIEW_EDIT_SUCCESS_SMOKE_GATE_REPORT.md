# P0-04C — Review/edit/success smoke gate + reschedule datetime polish report

## Summary
- Added patient-facing datetime formatting in reschedule review panel and removed technical `%Y-%m-%d %H:%M %Z` rendering from the active reschedule review path.
- Added recovery navigation to reschedule review panel (`Back` to slot panel + `Home`) while keeping confirm action unchanged.
- Added dedicated smoke-gate test file for P0-04C covering review layout, contact→review, review back, review edit actions, success/failure finalize branches, RU reschedule datetime readability, and callback namespace checks.
- Kept P0-03D smoke gate passing.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `tests/test_p0_04c_review_edit_success_smoke_gate.py`
- `docs/report/P0_04C_REVIEW_EDIT_SUCCESS_SMOKE_GATE_REPORT.md`

## Reschedule review datetime before/after
- Before: `strftime("%Y-%m-%d %H:%M %Z")` for both current and new times in `_render_reschedule_review_panel(...)`.
- After: localized patient-facing line format via `_format_patient_datetime_line(...)`, using timezone-resolved datetimes + existing locale-safe patient date/time helpers.
- RU smoke rendering now verifies human form like `28 апреля 2026 · 14:00` and excludes technical tokens.

## Review panel smoke results
- Verified review panel includes title + service/doctor/date/time/branch/phone blocks.
- Verified callback set includes:
  - `book:confirm:{session_id}`
  - `book:review:edit:service:{session_id}`
  - `book:review:edit:doctor:{session_id}`
  - `book:review:edit:time:{session_id}`
  - `book:review:edit:phone:{session_id}`
  - `book:review:back:{session_id}`
  - `phome:home`
- Verified review panel excludes: `UTC`, `MSK`, `%Z`, `pending_confirmation`, raw `branch:/service:/doctor:`, `Actions:`.

## Contact-to-review smoke results
- New booking contact submission removes `ReplyKeyboardMarkup` (`ReplyKeyboardRemove` is emitted).
- Review panel is rendered with `InlineKeyboardMarkup`.
- Contact keyboard is not left visible after transition.

## Review Back smoke results
- `book:review:back:{session_id}` validates and routes to contact prompt.
- Contact prompt uses `ReplyKeyboardMarkup`.
- No double callback answer (single payload path).

## Edit service/doctor/time/phone smoke results
- **Edit service**: releases selected hold; clears slot/hold; resets slot paging/date/window/suppressed; sets `booking_mode=review_edit_service`; selecting service in this mode moves to `review_edit_doctor`.
- **Edit doctor**: releases selected hold; clears slot/hold; sets `booking_mode=review_edit_doctor`; doctor edit path stays in doctor selection mode.
- **Edit time**: releases selected hold; clears slot/hold; sets `booking_mode=review_edit_time`; slot selection with existing contact+resolved patient returns directly to review (`mark_review_ready` path), no contact reply keyboard.
- **Edit phone**: does not release hold; keeps selected slot; sets `booking_mode=review_edit_phone`; renders contact reply keyboard; phone submit updates/returns to review and removes reply keyboard; Back/Home from edit phone remove reply keyboard and route to review/home respectively.

## Confirm success smoke results
- `book:confirm:{session_id}` success renders polished success panel with service/doctor/date/time/branch/status.
- Status is localized patient-readable text.
- Success actions are `phome:my_booking` and `phome:home`.
- Success panel excludes `pending_confirmation`, `telegram`, `Actions:`, `branch: -`, `UTC`, `MSK`.

## Finalize failure smoke results
- `SlotUnavailableOutcome` and `ConflictOutcome` render readable failure panel with recovery (`book:slots:back:{session_id}`) and `Home`, without popup alert for valid callback path.
- `InvalidStateOutcome` renders readable failure panel with `Home` and no crash.

## Reschedule review smoke results
- Triggered reschedule review via slot selection in `reschedule_booking_control` flow.
- RU text contains human date/time (`28 апреля 2026`, `14:00`) and excludes `UTC`, `MSK`, `%Z`, ISO `2026-04-`, `Tue`, `Apr`.
- Reschedule review actions include confirm and Home, plus Back to slots (`book:slots:back:{session_id}`).

## Callback namespace check
- Verified P0-03D callback allowlist still includes:
  - `book:review:back:`
  - `book:review:edit:`
- Verified produced callbacks in P0-04C smoke start with expected prefixes only.

## Tests run with exact commands/results
- `python -m compileall app tests` ✅ pass
- `pytest -q tests/test_p0_04c_review_edit_success_smoke_gate.py` ✅ pass (3 passed)
- `pytest -q tests/test_p0_03d_patient_booking_smoke_gate.py` ✅ pass (6 passed)
- `pytest -q tests/test_booking_patient_review_confirm_pat_a1_1a.py` ✅ pass (1 passed)
- `pytest -q tests/test_patient_first_booking_review_pat_a1_1.py tests/test_patient_home_surface_pat_a1_2.py tests/test_patient_existing_booking_shortcut_pat_a3_2.py` ✅ pass (89 passed)
- `pytest -q tests/test_patient_reschedule_start_pat_a4_1.py` ✅ pass (16 passed)
- `pytest -q tests -k "patient and booking"` ✅ pass (105 passed, 482 deselected, 2 existing pytest mark warnings unrelated to P0-04C)

## Grep checks with exact commands/results
- `rg "%Y-%m-%d %H:%M %Z|strftime\(\"%Y-%m-%d %H:%M %Z\"" app/interfaces/bots/patient/router.py`
  - Result: no matches (`rg` exit 1) ✅
- `rg "UTC|MSK|Tue|Apr" app/interfaces/bots/patient/router.py tests/test_p0_04c_review_edit_success_smoke_gate.py`
  - Result: matches in constants/helper internals and negative assertions/comments only; no patient-facing reschedule review formatting leakage ✅
- `rg "pending_confirmation|branch: -|Actions:" app/interfaces/bots/patient/router.py tests/test_p0_04c_review_edit_success_smoke_gate.py`
  - Result: expected internal status branching + negative assertions only ✅
- `rg "book:review:edit:" app/interfaces/bots/patient tests`
  - Result: explicit router/test handling present ✅
- `rg "review_edit_service|review_edit_doctor|review_edit_time|review_edit_phone" app/interfaces/bots/patient tests`
  - Result: explicit router/test mode handling present ✅

## Defects found/fixed
1. **Reschedule review used technical datetime format** in patient-facing text (`%Y-%m-%d %H:%M %Z`) — fixed to localized patient-facing date/time line.
2. **Reschedule review panel lacked guaranteed recovery navigation** — now includes Home and Back-to-slots actions.
3. **No dedicated full-section smoke-gate test for P0-04A/B integration** — added P0-04C smoke-gate coverage file.

## Carry-forward for P0-05 My Booking card
- Keep callback namespace discipline (avoid broad callback wildcards).
- Preserve patient-facing date/time helper usage for any new booking panel copy.
- Continue verifying reply-keyboard cleanup when switching between contact and inline action panels.
- Maintain explicit finalize outcome coverage (success + each failure branch) in smoke tests.

## Go / No-Go recommendation for P0-05
- **Recommendation: GO**.
- Rationale: P0-04C acceptance targets are satisfied (new smoke gate exists and passes, reschedule review datetime polished, recovery nav present, P0-03D unchanged and passing, broad `patient and booking` subset passing with only known unrelated warnings).
