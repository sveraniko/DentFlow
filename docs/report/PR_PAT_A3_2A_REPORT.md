# PR PAT-A3-2A Report

## What changed
- Added a safe direct `/my_booking` shortcut path: when Telegram user -> patient resolution is uniquely trusted, router now opens existing-booking control directly without contact prompt.
- Added bounded flow helper `resolve_existing_booking_for_known_patient(...)` in `BookingPatientFlowService` to start a fresh `existing_booking_control` session, bind resolved patient, and resolve live bookings.
- Kept conservative fallback: if trusted identity is missing/unsafe or helper returns non-supported outcome, flow falls back to existing contact prompt.
- Normalized existing-booking flow mode hygiene:
  - `existing_lookup_contact` = waiting for contact input only.
  - `existing_booking_control` = active existing-booking control session (panel/handoff state).
- Updated contact submission handling so neutral existing-booking mode is not reinterpreted as new-booking contact.
- Aligned reminder handoff mode to neutral existing-booking mode for consistency with PAT-A3-1 behavior.

## Exact files changed
- `app/interfaces/bots/patient/router.py`
- `app/application/booking/telegram_flow.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `tests/test_booking_patient_flow_stack3c1.py`
- `tests/test_patient_reminder_handoff_pat_a3_1a.py`
- `docs/report/PR_PAT_A3_2A_REPORT.md`

## Trusted patient shortcut decision
- Router uses existing `_resolve_patient_id_for_user(actor_id)` semantics.
- Shortcut activates only when a uniquely trusted patient id is returned by repository rules.
- If trust is absent/unsafe (no unique id, unsupported repository lookup path, etc.), router uses existing contact-prompt path unchanged.

## New booking-flow helper
- Added `resolve_existing_booking_for_known_patient(...)`.
- Behavior:
  1. starts a **new** `existing_booking_control` session,
  2. attaches resolved patient id to the session,
  3. lists bookings for that patient,
  4. applies the same live booking statuses as contact-based lookup,
  5. returns `BookingControlResolutionResult` (`exact_match` / `no_match` / `invalid_state`).

## Existing-booking flow-mode normalization
- Existing-booking result rendering now persists `booking_mode = "existing_booking_control"`.
- Reminder handoff now binds `booking_mode = "existing_booking_control"` (replacing prior workaround mode).
- `_handle_contact_submission(...)` behavior is now explicit:
  - `existing_lookup_contact` -> resolve existing booking by contact,
  - `new_booking_contact` -> existing new-booking contact handling,
  - `existing_booking_control` -> ignore contact text/share for booking creation path.

## Tests added/updated
- Added trusted shortcut and no-trust fallback coverage:
  - `tests/test_patient_home_surface_pat_a1_2.py`
- Added flow-helper coverage for known patient existing-booking resolution:
  - `tests/test_booking_patient_flow_stack3c1.py`
- Updated reminder handoff regression assertion for normalized mode:
  - `tests/test_patient_reminder_handoff_pat_a3_1a.py`

## Environment / execution
- Targeted tests for changed areas ran successfully in this environment.

## Explicit non-goals left for PAT-A3-2B and PAT-A3-3
- No reminder engine redesign.
- No booking state machine redesign.
- No identity architecture redesign.
- No admin/doctor/owner flow changes.
- No migration creation.
- No broad hardening matrix beyond bounded PAT-A3-2A shortcut + hygiene scope.
