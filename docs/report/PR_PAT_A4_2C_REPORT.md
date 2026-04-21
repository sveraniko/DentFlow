# PR PAT-A4-2C Report — Reschedule flow hardening, resume parity, and targeted regressions

## What changed
- Hardened active reschedule context resume across **all patient entry seams** (`/book`, `/my_booking`, `phome:my_booking`) by introducing a shared bounded helper that:
  - resumes active reschedule safely,
  - restores to the correct stage (reschedule-start vs reschedule-review when slot already selected),
  - and normalizes stale state without crashes.
- Updated entry logic so active reschedule is not silently overwritten by ordinary booking/existing-lookup flows.
- Added stale-context hygiene: stale/missing/terminal reschedule session now clears reschedule mode/session/source-booking state and emits bounded fallback copy.
- Preserved and validated post-success cleanup semantics: on successful `rsch:confirm:*`, reschedule-specific flow state is reset (`reschedule_booking_id` cleared and mode normalized to `existing_booking_control`).
- Added focused PAT-A4-2C regression tests for parity and bounded stale handling.

## Exact files changed
- `app/interfaces/bots/patient/router.py`
- `tests/test_patient_reschedule_start_pat_a4_1.py`
- `docs/report/PR_PAT_A4_2C_REPORT.md`

## Active-reschedule parity cases hardened
1. `/book` with active reschedule context:
   - resumes active context instead of launching/overwriting new-booking session.
2. `/my_booking` with active reschedule context:
   - now behaves consistently and resumes reschedule context rather than collapsing into ordinary existing-booking lookup.
3. `phome:my_booking` parity:
   - follows same `_enter_existing_booking_lookup(...)` behavior and now has active reschedule resume parity with `/my_booking`.
4. Resume stage parity:
   - if selected slot already exists in active reschedule session, resume opens review panel;
   - otherwise resume opens canonical reschedule-start panel.

## Reschedule state cleanup behavior
- On stale/invalid active reschedule context during entry/resume:
  - state is normalized by clearing `booking_mode` reschedule value, `booking_session_id`, and `reschedule_booking_id`;
  - bounded fallback panel is shown;
  - runtime does not crash.
- On successful reschedule completion:
  - flow transitions to canonical existing-booking mode/session;
  - `reschedule_booking_id` is cleared.

## Tests added/updated
Updated `tests/test_patient_reschedule_start_pat_a4_1.py` with focused coverage for:
1. active reschedule session resumes correctly from `/book` (including review-stage resume when slot already selected),
2. active reschedule session is respected by `/my_booking`,
3. `phome:my_booking` parity with `/my_booking` under active reschedule,
4. successful reschedule completion normalization/cleanup,
5. stale reschedule context from `/my_booking` remains bounded and normalized,
6. contact input outside contact-prompt mode remains bounded (existing test retained),
7. reminder-originated and `/my_booking`-originated reschedule both reach equivalent completed semantics,
8. no migrations introduced (guard test retained, renamed for 2C scope).

## Environment / execution notes
- Focused pytest execution for the changed PAT-A4 reschedule regression file was run in this environment.
- Full-suite run was not required for this bounded hardening PR.

## Closure statements
- **PAT-A4-2 is now considered closed** for the patient-facing bounded scope defined by A4-2A, A4-2B, and A4-2C.
- **PAT-004 can now be considered functionally closed from the patient-facing reschedule UX perspective**, within the explicitly bounded scope (no reminder engine redesign, no doctor/branch/service broadening, no admin-flow redesign).
