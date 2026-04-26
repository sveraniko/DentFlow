# PR DOC-A3B Report — Booking completion coherence after doctor encounter completion

## What changed after DOC-A3A
- Added a bounded doctor-level completion method that closes the encounter first, then applies booking completion coherence for booking-linked context.
- Updated `denc:complete_confirm:*` to use encounter+booking coherence when `booking_id` is present, while preserving encounter-only completion when booking context is absent.
- Added compact, doctor-facing localized copy for: full encounter+booking completion, encounter-only completion with unchanged booking, and bounded booking-completion-unavailable outcome.

## Exact files changed
- `app/application/doctor/operations.py`
- `app/interfaces/bots/doctor/router.py`
- `tests/test_doctor_operational_stack6a.py`
- `tests/test_booking_linked_opens_12b1.py`
- `locales/en.json`
- `locales/ru.json`
- `docs/report/PR_DOC_A3B_REPORT.md`

## Encounter + booking completion coherence model
- New high-level operation: `DoctorOperationsService.complete_encounter_with_booking_coherence(...)`.
- Flow:
  1. Validate encounter access/ownership for doctor.
  2. Complete encounter via existing clinical close flow.
  3. If booking context exists and booking belongs to doctor, evaluate booking status and complete only via existing booking orchestration (`complete_booking`).
  4. Return structured result flags:
     - `encounter_completed`
     - `booking_completed`
     - `booking_already_terminal`
     - `booking_completion_not_applicable`
     - `failure_reason` (bounded internal code)
- Router uses these flags to provide bounded doctor-facing feedback without exposing raw technical errors.

## Booking states completed vs skipped
- Completes booking only from `in_service` (conservative bounded behavior).
- Skips force mutation for terminal statuses: `completed`, `canceled`, `no_show`.
- Skips for non-completable live/incompatible statuses (e.g., `confirmed`, `checked_in`, `reschedule_requested`, etc.) and reports bounded unavailability.

## Partial completion reporting
- Encounter can complete independently of booking mutation.
- When booking completion is not applied, UI shows compact bounded message and still returns continuity panel (booking panel if available, else encounter panel).

## Tests added/updated
- Updated router tests for booking-linked completion coherence outcomes:
  - booking-linked in-service completion completes booking and reflects completed status.
  - terminal/canceled booking remains unchanged with bounded message.
  - encounter-only completion path still works without booking id.
  - invalid/non-completable booking path remains bounded.
- Added doctor operations test for coherence method:
  - in-service booking completes.
  - canceled booking is treated as terminal and not mutated.
- Existing terminal encounter CTA-hiding behavior remains covered.

## Environment/test execution notes
- Focused tests were run for updated files only.
- No environment blockers observed for these targeted tests.

## Explicit non-goals left for DOC-A3C
- No broad booking state machine redesign.
- No clinical domain redesign beyond bounded completion coherence.
- No admin/owner flow changes.
- No patient aftercare redesign.
- No migrations.
