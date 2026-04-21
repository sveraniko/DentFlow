# PR PAT-A4-2B Report — Atomic patient reschedule completion from selected slot

## What changed
- Implemented a dedicated patient reschedule confirm callback path (`rsch:confirm:<session_id>`) that performs bounded callback/session validation and executes real completion logic instead of placeholder behavior.
- Added `BookingPatientFlowService.complete_patient_reschedule(...)` as a bounded high-level helper for patient reschedule completion from active reschedule session context.
- Added orchestration-level atomic helper `BookingOrchestrationService.complete_booking_reschedule_from_session(...)` to commit reschedule using session-selected slot/hold in one transaction.
- Updated patient success handoff to canonical existing-booking panel after successful reschedule completion.
- Added compact localized feedback keys for reschedule completion success and bounded failure states.

## Exact files changed
- `app/interfaces/bots/patient/router.py`
- `app/application/booking/telegram_flow.py`
- `app/application/booking/orchestration.py`
- `tests/test_patient_reschedule_start_pat_a4_1.py`
- `tests/test_booking_orchestration.py`
- `locales/en.json`
- `locales/ru.json`
- `docs/report/PR_PAT_A4_2B_REPORT.md`

## How atomic reschedule completion is modeled
`complete_booking_reschedule_from_session(...)` is transaction-scoped and validates all required session/booking/hold/slot invariants before mutation:
1. Loads and validates active reschedule session (`route_type == reschedule_booking_control`), selected slot/hold presence, and resolved patient.
2. Loads source booking and validates it is eligible (`reschedule_requested`) and belongs to same clinic/patient as session.
3. Validates selected hold exists, belongs to session, is active, and matches selected slot.
4. Validates selected slot is still `open` and has no live booking conflict.
5. Atomically updates booking to selected slot/times/doctor/branch; transitions status back to `confirmed` from `reschedule_requested`; updates timestamp.
6. Consumes selected hold.
7. Appends booking history and `booking.rescheduled` outbox event.
8. Rebuilds reminder plan for updated booking.

Old slot release is implicit via booking slot pointer change in the same transaction (no out-of-band old-slot release logic).

## How hold consumption and booking update are validated
- Flow layer validates callback freshness/ownership, source booking context presence, session scope, and same patient/service/doctor/branch invariants.
- Orchestration layer re-validates booking/session/hold/slot invariants under lock and performs all state mutation atomically.
- Failure outcomes (`slot_unavailable`, `conflict`, other invalid-state) are returned as bounded outcomes for safe UI handling.

## Success handoff and bounded failure behavior
- On success: patient flow state is reset to canonical existing-booking mode and user is rendered into canonical existing-booking panel with updated booking data.
- On slot unavailable/conflict: patient stays in reschedule flow; receives bounded localized alert and is returned to slot selection panel.
- On invalid/missing source context: patient receives bounded localized fallback; no raw technical errors are exposed.

## Tests added/updated
- `tests/test_patient_reschedule_start_pat_a4_1.py`
  - Added happy-path confirm callback test proving canonical handoff after completion.
  - Added slot-unavailable bounded failure test proving safe return to slot selection.
- `tests/test_booking_orchestration.py`
  - Added atomic orchestration test proving booking slot/time update, status return to `confirmed`, hold consumption, and reschedule history/outbox event emission.

## Environment / execution note
- Focused test subsets for changed paths were executed successfully in this environment.
- Full-suite execution was intentionally not required for this bounded PR.

## Explicit non-goals intentionally left for PAT-A4-2C
- No resume/entry hardening beyond bounded confirm callback needs.
- No reminder engine redesign.
- No doctor/branch/service scope broadening.
- No `/my_booking` redesign.
- No admin/doctor/owner flow changes.
- No migrations.
