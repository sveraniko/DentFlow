# PR PAT-A1-3B Report — Patient booking copy hardening, fallback discipline, and targeted regressions

## What changed after PAT-A1-3A

This PR is a bounded hardening pass on patient booking review/success copy quality introduced in PAT-A1-3A.

- Hardened patient-facing fallback discipline in router presentation logic:
  - introduced shared `_resolve_reference_label(...)` for doctor/branch fallback consistency;
  - introduced `_resolve_status_label(...)` to ensure success status remains localized/patient-friendly and falls back to readable wording if a localization key is missing.
- Aligned review and success panel naming discipline:
  - both now use the same reference fallback strategy for doctor/branch labels (display name -> raw id -> localized missing marker);
  - service fallback order remains shared and unchanged from PAT-A1-3A;
  - datetime strategy remains local-timezone oriented with safe UTC fallback.
- Kept scope narrow:
  - no redesign of booking flow, no `/start` changes, no reminder architecture changes, no admin/doctor/owner changes.

## Exact files changed

- `app/interfaces/bots/patient/router.py`
- `tests/test_patient_booking_copy_pat_a1_3.py` (new)
- `docs/report/PR_PAT_A1_3B_REPORT.md` (new)

## Fallback cases hardened

Covered in code and tests:

1. service localization missing -> falls back to service code, never leaks `title_key`.
2. service reference row missing -> falls back to service id only as last resort.
3. doctor reference row missing -> falls back to doctor id (bounded, human-readable enough).
4. branch reference row missing -> falls back to branch id (bounded, human-readable enough).
5. slot lookup missing during review -> datetime safely renders localized missing marker (`-`).
6. invalid timezone -> safely falls back to UTC rendering, no crash.

## Reminder copy alignment

- `app/application/communication/delivery.py` was re-checked.
- Reminder copy was **intentionally left unchanged** in this PR:
  - existing reminder context already follows humanized labels and safe timezone fallback.
  - no bounded inconsistency was strong enough to justify touching reminder templates in PAT-A1-3B scope.

## Tests added/updated

### Added
- `tests/test_patient_booking_copy_pat_a1_3.py`
  - review uses localized/human service label when available;
  - success uses human labels and localized status in normal path;
  - review fallback is safe when slot/reference rows are missing;
  - invalid timezone falls back to UTC safely;
  - `title_key` does not leak into review/success text when localization is missing.

### Regression suites executed
- `tests/test_patient_booking_copy_pat_a1_3.py`
- `tests/test_patient_first_booking_review_pat_a1_1.py`
- `tests/test_patient_home_surface_pat_a1_2.py`

## Environment / execution notes

- No environment blocker prevented running the targeted test slice for this PR.

## Migrations

- No migrations introduced.

## Closure statements

- **PAT-A1-3 is now considered closed** (PAT-A1-3A + PAT-A1-3B).
- **PAT-001 can now be considered functionally closed from the patient-facing booking UX perspective**, for the bounded first-booking review/success hardening scope defined by the PAT-A1 stack.
