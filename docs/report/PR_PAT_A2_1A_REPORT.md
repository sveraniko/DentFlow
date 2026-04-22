# PR PAT-A2-1A Report — Trusted returning-patient quick-book foundation for `/book`

## What changed

- Added a bounded returning-patient booking-entry helper in booking flow:
  - `BookingPatientFlowService.start_or_resume_returning_patient_booking(...)`
  - returns a structured `ReturningPatientStartResult` with `trusted_shortcut_applied`.
- New helper behavior is intentionally narrow:
  1. resume existing active `service_first` session unchanged if present;
  2. otherwise start new `service_first` session;
  3. attach trusted patient + phone snapshot only when both trusted values are present and valid;
  4. on any invalid or failed hydration step, safely fall back to regular new session behavior.
- `/book` entry now attempts trusted returning-patient quick entry after reschedule interception and before normal resume rendering.
- Flow-mode hygiene was tightened:
  - introduced neutral in-flow mode usage: `new_booking_flow`;
  - `new_booking_contact` is now set only when contact input is actively requested;
  - free contact messages outside `new_booking_contact` are ignored (not interpreted as booking contact input).
- Added tiny bounded primary-phone read seam in the DB recommendation repository:
  - `find_primary_phone_by_patient(clinic_id, patient_id) -> str | None`
  - reads active phone contact for trusted patient in clinic scope.

## Exact files changed

- `app/application/booking/telegram_flow.py`
- `app/interfaces/bots/patient/router.py`
- `app/infrastructure/db/recommendation_repository.py`
- `tests/test_booking_patient_flow_stack3c1.py`
- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`
- `tests/test_patient_first_booking_review_pat_a1_1.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `tests/test_patient_reschedule_start_pat_a4_1.py`
- `tests/test_booking_patient_review_confirm_pat_a1_1a.py`
- `tests/test_patient_booking_copy_pat_a1_3.py`

## How trusted quick-entry is decided

Router decision path for `/book`:

1. keep active reschedule interception first;
2. attempt trusted unique patient-id resolution via existing safe router seam;
3. attempt trusted primary phone lookup for that trusted patient id via bounded repository seam;
4. only when both are safe and available, pass both values to returning-patient start helper;
5. if either trust or phone snapshot is unavailable/unsafe/invalid, pass no trusted shortcut and continue normal path.

No technical failure reason is exposed to patient-facing UI.

## How primary phone snapshot is resolved

- Added `find_primary_phone_by_patient(...)` in `DbRecommendationRepository`.
- It reads active `phone` contact rows in clinic+patient scope and picks primary-most-recent record (`is_primary DESC`, then update/create recency).
- Returns `None` if unavailable; no heuristics are used.

## How flow-mode hygiene was adjusted

- `new_booking_flow` is now the neutral mode for in-progress service-first booking.
- `new_booking_contact` is set only in `contact_collection` panel rendering.
- `_handle_contact_submission(...)` accepts new-booking contact only when mode is exactly `new_booking_contact`.
- Contact input in `new_booking_flow` is ignored, preventing accidental interpretation outside contact prompt mode.

## Tests added/updated

### Added/updated for PAT-A2-1A target

- `tests/test_booking_patient_flow_stack3c1.py`
  - added tests for `start_or_resume_returning_patient_booking(...)`:
    - trusted patient + phone hydrates session;
    - trusted patient without phone falls back to normal session.
- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`
  - added `/book` trusted quick-entry test:
    - trusted patient + primary phone leads to review panel path and skips contact prompt;
    - trusted patient without phone falls back to contact prompt.
  - retained contact-outside-mode safety coverage.

### Small compatibility updates

- Updated booking-flow stubs in existing patient-router test files to include `start_or_resume_returning_patient_booking(...)` shim so legacy tests keep using current router entry behavior.

## Environment / execution notes

- Targeted test execution succeeded for focused suites.
- No environment limitation blocked these test runs.

## Explicit non-goals intentionally left for follow-up

### For PAT-A2-1B

- broader edge-case and hardening matrix expansion beyond this minimal trust-based quick-entry slice;
- deeper failure-mode/UI copy hardening around trust and phone seams.

### For PAT-A2-2

- continuity suggestions (recent service/doctor/branch);
- repeat/rebook shortcuts / one-tap repeat;
- broader booking orchestration redesign.

### Still out of scope

- reminders redesign;
- admin/doctor/owner flow changes;
- migrations.
