# PR PAT-A3-2B Report

## What changed after PAT-A3-2A
- Hardened the trusted `/my_booking` shortcut so trusted direct-open now safely falls back to contact prompt when trust lookup is unavailable, repository calls fail, or helper outcome is unsupported.
- Kept identity safety conservative: direct-open only proceeds for a single trusted patient id and only for `exact_match` / `no_match` outcomes.
- Preserved command/callback parity by keeping both `/my_booking` and `phome:my_booking` on the same `_enter_existing_booking_lookup(...)` + shortcut helper path.
- Preserved existing-booking mode discipline (`existing_booking_control`) and verified that contact payloads outside `existing_lookup_contact` are bounded/ignored.

## Exact files changed
- `app/interfaces/bots/patient/router.py`
- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`
- `docs/report/PR_PAT_A3_2B_REPORT.md`

## Trust/fallback matrix coverage now in tests
- unique trusted patient id -> exact live booking (direct-open)
- unique trusted patient id -> no live booking (direct no-match)
- no trusted patient id -> contact prompt fallback
- multiple candidate patient ids -> contact prompt fallback
- repository absent / lookup unavailable -> contact prompt fallback
- helper invalid/unexpected outcome -> contact prompt fallback
- contact input while in existing-booking control mode -> bounded (ignored, not treated as new-booking contact)

## Reminder handoff compatibility
- No runtime compatibility adjustment was required for PAT-A3-1 handoff logic.
- PAT-A3-1 accepted reminder handoff remains canonical and mode-safe (`existing_booking_control`) with regression verification included in the targeted test run.

## Tests added/updated
- Added focused regression file:
  - `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`
- Re-ran relevant regressions:
  - `tests/test_patient_reminder_handoff_pat_a3_1a.py`
  - `tests/test_booking_patient_flow_stack3c1.py`
  - `tests/test_patient_home_surface_pat_a1_2.py`

## Environment / execution notes
- Targeted tests executed successfully in this environment.
- No environment blocker prevented executing the scoped PAT-A3-2B suite.

## Closure statements
- **PAT-A3-2 is now considered closed** for the bounded hardening scope defined by PAT-A3-2A + PAT-A3-2B.
- **PAT-003 is now functionally closed from patient-facing confirmation UX perspective** for the audited `/my_booking` shortcut + reminder-handoff safety seam.
