# P0_05B — My Booking action panels polish report

## Summary
Implemented panel-level UX polish around patient **My Booking** actions for cancel, waitlist, and reschedule flows, including runtime + legacy callback consistency and cleaner recovery navigation.

## Files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_p0_05b_my_booking_action_panels.py`
- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`
- `tests/test_patient_reschedule_start_pat_a4_1.py`
- `tests/test_patient_reminder_handoff_pat_a3_1a.py`

## Cancel prompt before/after
- **Before**: generic confirm prompt (`patient.booking.cancel.confirm`) with yes/no and no Home or summary.
- **After**:
  - structured, readable cancel panel with booking summary (service/doctor/date/time) when resolvable;
  - explicit CTA buttons: cancel confirm, back to booking, home;
  - safe fallback prompt with Home when booking summary is unavailable.

## Cancel abort behavior
- **Before**: popup-only abort (`show_alert=True`) on valid path.
- **After**: valid abort now returns to clean My Booking panel with header “Cancellation canceled. Your booking was not changed.” and normal controls.

## Cancel confirm behavior
- Runtime and legacy confirm paths now both use the shared existing-booking panel rendering helper and re-render clean My Booking with status-aware keyboard (home-only for canceled).

## Waitlist success/failure behavior
- **Success (runtime + legacy)**:
  - structured waitlist success title/body;
  - if booking resolves: include current My Booking card + controls;
  - if not: readable fallback panel with `My Booking` and `Home` navigation.
- **Failure**: stale/invalid continues to alert on invalid-state branch.

## Reschedule start before/after
- **Before**: minimal start panel with single CTA.
- **After**: structured panel with title/body/note and navigation buttons:
  - Select new time
  - My Booking
  - Home
- Runtime and legacy paths aligned.

## Reschedule unavailable behavior
- Unavailable start now renders readable fallback text with explicit recovery keyboard (`My Booking`, `Home`) instead of text-only dead-end.

## Runtime vs legacy callback consistency
Validated and covered by tests for:
- cancel prompt/abort/confirm;
- waitlist success/failure;
- reschedule start;
- reschedule complete success remains clean My Booking.

## Tests run (exact commands/results)
- `python -m compileall app tests` ✅ pass
- `pytest -q tests/test_p0_05b_my_booking_action_panels.py` ✅ pass (6 passed)
- `pytest -q tests/test_p0_05a_my_booking_readable_card.py` ✅ pass (5 passed)
- `pytest -q tests/test_p0_04c_review_edit_success_smoke_gate.py` ✅ pass (3 passed)
- `pytest -q tests/test_p0_03d_patient_booking_smoke_gate.py` ✅ pass (6 passed)
- `pytest -q tests/test_patient_existing_booking_shortcut_pat_a3_2.py` ✅ pass (19 passed)
- `pytest -q tests/test_patient_reschedule_start_pat_a4_1.py` ✅ pass (16 passed)
- `pytest -q tests/test_patient_reminder_handoff_pat_a3_1a.py` ✅ pass (13 passed)
- `pytest -q tests/test_patient_first_booking_review_pat_a1_1.py tests/test_patient_home_surface_pat_a1_2.py` ✅ pass (70 passed)
- `pytest -q tests -k "patient and booking"` ✅ pass (105 passed, 493 deselected)

## Grep checks (exact commands/results)
- `rg "patient.booking.cancel.confirm\"|common.yes|common.no" app/interfaces/bots/patient/router.py tests/test_p0_05b_my_booking_action_panels.py`
  - result: `common.yes/common.no` still present in reminder-cancel confirmation prompt only; not used by active My Booking cancel prompt.
- `rg "patient.booking.waitlist.created\"" app/interfaces/bots/patient/router.py`
  - result: no active flat key usage in router.
- `rg "patient.booking.reschedule.start.header|patient.booking.reschedule.start.body" app/interfaces/bots/patient/router.py`
  - result: active rendering uses v2 keys (`title`, `body_v2`, `note`).
- `rg "Actions:|Канал:|Channel:|telegram|booking_id|slot_id|patient_id|doctor_id|service_id|branch_id|UTC|MSK|2026-04-" tests/test_p0_05b_my_booking_action_panels.py`
  - result: primarily negative assertion tokens plus fixture setup identifiers.
- `rg "mybk:waitlist|mybk:cancel_prompt|mybk:cancel_abort|mybk:cancel_confirm|mybk:reschedule" app/interfaces/bots/patient/router.py tests/test_p0_05b_my_booking_action_panels.py`
  - result: legacy handlers retained and explicitly tested.

## Defects found/fixed
- Valid cancel abort path used popup-only UX.
- Legacy cancel confirm path could render without refreshed status-aware controls.
- Waitlist success path could be text-only and navigationally weak.
- Reschedule start and unavailable panels were not sufficiently recoverable.
- Reminder handoff panel consistency adjusted to share clean booking panel helper while preserving fresh-send behavior.

## Carry-forward for P0-05C smoke gate
- Keep monitoring reminder + booking runtime panel binding behavior in stub/test doubles that don’t subclass `CallbackQuery`.
- Consider adding a dedicated guard test for stale callback routing parity between runtime and legacy callbacks under session mismatch.

## Go / no-go recommendation for P0-05C
**Go** — targeted P0-05B behavior implemented, legacy/runtime parity preserved, and required smoke suites passing.
