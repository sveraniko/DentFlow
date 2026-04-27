# P0-05A — My Booking readable card report

## Summary
Implemented a dedicated patient-facing My Booking renderer in `patient/router.py` without rewriting `CardShellRenderer`.
The My Booking panel now renders a clean localized card with readable status/reminder/next-step lines and patient-facing date/time formatting.
Controls now include Home navigation and hide mutation actions for terminal/non-actionable booking statuses.
Confirm/cancel/reminder handoff paths now re-render with the same clean panel and status-aware controls.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_p0_05a_my_booking_readable_card.py`
- `tests/test_patient_reminder_handoff_pat_a3_1a.py`

## My Booking before/after
- Before: panel text reused flattened card shell text (`CardShellRenderer.to_panel(shell).text`) that leaked technical/internal metadata.
- After: direct patient-facing panel with structure:
  - title
  - status badge
  - service/doctor/date/time/branch
  - reminders
  - optional next-step
- Removed internals/debug-like leakage from My Booking output (no actions/channel/source/channel mode/internal ids).

## Status label map
Implemented `patient.booking.my.status.*` keys and mapping in router helper:
- `pending_confirmation` → ⏳ + localized pending confirmation text
- `confirmed` → ✅ + localized confirmed text
- `reschedule_requested` → 🔁 + localized reschedule text
- `canceled` → ❌ + localized canceled text
- `checked_in` → ✅ + localized checked in text
- `in_service` → 🦷 + localized in service text
- `completed` → ✅ + localized completed text
- `no_show` → ❌ + localized no-show text
- fallback via `patient.booking.my.status.fallback`

## Reminder line behavior
- For `canceled/completed/no_show`: `patient.booking.my.reminders.not_needed`
- Otherwise: `patient.booking.my.reminders.default`

## Controls keyboard behavior by status
- `pending_confirmation`:
  - Confirm
  - Reschedule
  - Earlier slot
  - Cancel
  - Home (`phome:home`)
- `confirmed`:
  - Reschedule
  - Earlier slot
  - Cancel
  - Home
- `reschedule_requested`:
  - Reschedule
  - Cancel
  - Home
- `canceled/completed/no_show/checked_in/in_service`:
  - Home only

## Action-result re-render behavior
- Confirm (existing booking runtime callback):
  - Re-renders clean My Booking text
  - Re-attaches status-aware controls keyboard
- Cancel (existing booking runtime callback):
  - Re-renders clean My Booking text
  - Re-attaches status-aware controls keyboard (Home-only for canceled)
- Reminder handoff:
  - Uses clean My Booking renderer + status-aware controls (covered in tests)

## Defects found/fixed
- Confirm/cancel runtime action success paths were re-rendering text without updated keyboard.
  - Fixed by rebuilding and passing keyboard in both success branches.
- Reminder handoff test expected exact `"Confirm"` label and failed after button copy update.
  - Fixed test to assert label prefix (`startswith("Confirm")`).

## Grep checks
### Command
`rg "CardShellRenderer.to_panel\(shell\)\.text" app/interfaces/bots/patient/router.py`

### Result
Two remaining matches exist in router, but none are used by the active patient My Booking renderer.

---

### Command
`rg "Actions:|Канал:|Channel:|source_channel|booking_mode|branch: -" app/interfaces/bots/patient/router.py tests/test_p0_05a_my_booking_readable_card.py`

### Result
- `tests/test_p0_05a_my_booking_readable_card.py`: expected negative assertions only.
- `router.py`: tokens like `booking_mode` exist as flow state internals, not panel output text.
- No active My Booking output includes forbidden card internals.

---

### Command
`rg "patient.booking.my" locales/ru.json locales/en.json app/interfaces/bots/patient/router.py tests/test_p0_05a_my_booking_readable_card.py`

### Result
Locale keys exist in both locales and are consumed in router/tests.

---

### Command
`rg "%Y-%m-%d %H:%M %Z|card.datetime_label" app/interfaces/bots/patient/router.py`

### Result
No matches.

## Tests run (exact commands/results)
- `python -m compileall app tests` → PASS
- `pytest -q tests/test_p0_05a_my_booking_readable_card.py` → PASS (5 passed)
- `pytest -q tests/test_p0_04c_review_edit_success_smoke_gate.py` → PASS (3 passed)
- `pytest -q tests/test_p0_03d_patient_booking_smoke_gate.py` → PASS (6 passed)
- `pytest -q tests/test_patient_existing_booking_shortcut_pat_a3_2.py` → PASS (19 passed)
- `pytest -q tests/test_patient_reschedule_start_pat_a4_1.py` → PASS (16 passed)
- `pytest -q tests/test_patient_first_booking_review_pat_a1_1.py tests/test_patient_home_surface_pat_a1_2.py` → PASS (70 passed)
- `pytest -q tests -k "patient and booking"` → PASS (105 passed, 487 deselected, 2 warnings)

## P0-05A matrix (requested)

### My Booking card
- readable title/status: **yes**
- service/doctor/date/time/branch/reminders: **yes**
- no Actions/Channel/telegram/internal ids: **yes**
- no UTC/MSK/ISO datetime: **yes**

### Keyboard
- pending: confirm/reschedule/earlier/cancel/home: **yes**
- confirmed: reschedule/earlier/cancel/home: **yes**
- canceled/completed/no_show: home only: **yes**

### Action results
- confirm re-renders clean card: **yes**
- cancel re-renders clean card: **yes**
- no stale mutation buttons after cancel: **yes**

### Regression
- P0-04C smoke: **pass** (`3 passed`)
- P0-03D smoke: **pass** (`6 passed`)
- patient and booking: **105 passed**

## Carry-forward for P0-05B
- Cancel prompt polish (copy/hierarchy consistency).
- Waitlist result polish if any flat text remains.
- Reschedule start/result polish if any raw text remains.

## Go / No-go recommendation for P0-05B
**Go**.
P0-05A acceptance criteria are met: readable localized My Booking card, no leaked internals, patient-facing datetime formatting, Home action added, status-aware action visibility, clean confirm/cancel rerender, and smoke suites remain green.
