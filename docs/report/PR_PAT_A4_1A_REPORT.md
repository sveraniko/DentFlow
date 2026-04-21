# PR PAT-A4-1A Report

## What changed
- Introduced a canonical patient **reschedule-start panel** with compact copy and a single CTA (`rsch:start:<session_id>`), replacing the old accepted-reschedule behavior that returned to the normal booking panel.
- Added explicit patient flow mode hygiene for active reschedule: `booking_mode = "reschedule_booking_control"` is now persisted and used for resume routing.
- Added a new bounded booking-flow helper `start_patient_reschedule_session(...)` that creates a **fresh reschedule-dedicated session** and pre-fills it from the current booking.
- Updated both `/my_booking` reschedule and reminder `reschedule` accepted paths to converge to the same canonical reschedule-start handoff.
- Added safe localized fallback messaging when reschedule initiation is accepted but dedicated reschedule context cannot be created.
- Added a non-dead placeholder handler for the new CTA (`rsch:start:*`) so the button always leads to a bounded response (to be expanded in PAT-A4-2).

## Exact files changed
- `app/interfaces/bots/patient/router.py`
- `app/application/booking/telegram_flow.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_booking_patient_flow_stack3c1.py`
- `tests/test_patient_reminder_handoff_pat_a3_1a.py`
- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`
- `docs/report/PR_PAT_A4_1A_REPORT.md`

## Dedicated reschedule session creation and prefill
`BookingPatientFlowService.start_patient_reschedule_session(...)` now:
1. Loads booking by `booking_id`.
2. Verifies clinic match (`booking.clinic_id == clinic_id`).
3. Starts a **new** booking session with route type `reschedule_booking_control`.
4. Sets `branch_id` at session creation from current booking.
5. Attaches `resolved_patient_id` from current booking.
6. Prefills `service_id` from current booking.
7. Prefills `doctor_preference_type = "specific"`.
8. Prefills `doctor_id` from current booking.

This keeps scope intentionally bounded to same doctor/service/branch.

## `/my_booking` and reminder convergence
- `/my_booking` reschedule callback path still uses `request_reschedule(...)` transactional semantics first.
- Reminder `reschedule` accepted path still uses `request_booking_reschedule_in_transaction(...)` semantics first.
- After accepted outcome, both paths now call the same bounded start helper and render the same canonical reschedule-start panel.
- Non-reschedule reminder accepted actions (`confirm`, `cancel`, `ack`) keep the existing canonical booking-panel handoff unchanged.

## Tests added/updated
- `tests/test_booking_patient_flow_stack3c1.py`
  - Added coverage that `start_patient_reschedule_session(...)` creates fresh `reschedule_booking_control` session with required prefilled fields.
- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`
  - Added focused `/my_booking` reschedule callback test proving accepted path lands in reschedule-start panel and sets `reschedule_booking_control` mode.
- `tests/test_patient_reminder_handoff_pat_a3_1a.py`
  - Updated accepted reminder matrix assertions so `reschedule` now lands in canonical reschedule-start panel while other actions still land in canonical booking panel.

## Environment / execution
- Focused changed-area tests were run in this environment.
- No environment blocker prevented running the scoped tests listed in this PR.

## Explicit non-goals intentionally left for PAT-A4-1B and PAT-A4-2
- No final slot reselection completion.
- No atomic old-slot release/new-slot finalize completion wiring.
- No booking state machine redesign.
- No reminder engine redesign.
- No doctor/branch/service change broadening beyond same-doctor/service/branch prefills.
- No admin/doctor/owner flow changes.
- No migrations.
