# PR PAT-A1-2A Report — Inline-first `/start` patient home surface

## What changed

- Replaced plain text `/start` response with a bounded inline-first home panel helper: `_render_patient_home_panel(...)`.
- Added patient-home callback namespace and handlers:
  - `phome:book`
  - `phome:my_booking`
  - `phome:recommendations`
  - `phome:care`
- Extracted shared entry helpers to avoid duplication between slash commands and home callbacks:
  - `_enter_new_booking(...)`
  - `_enter_existing_booking_lookup(...)`
  - `_enter_recommendations_list(...)`
  - `_enter_care_catalog(...)`
- Refactored `/book`, `/my_booking`, `/recommendations`, `/care` handlers to call these shared helpers.
- Kept booking entry path unchanged in behavior: home `phome:book` uses the same `/book` session setup + resume rendering path, preserving PAT-A1-1 review/confirm behavior downstream.

## Exact files changed

- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_patient_first_booking_review_pat_a1_1.py`
- `docs/report/PR_PAT_A1_2A_REPORT.md`

## Optional action visibility / guards

- Home panel action visibility is adaptive:
  - Always visible: Book appointment, My booking.
  - Recommendations button shown only when `recommendation_service` is wired.
  - Care / hygiene button shown only when `care_commerce_service` is wired.
- Callback safety guard added:
  - If optional callback is fired while service is unavailable, user receives bounded localized fallback (`patient.home.action.unavailable`) and runtime does not crash.

## Tests added/updated

Updated `tests/test_patient_first_booking_review_pat_a1_1.py` with focused patient-home checks:
- `test_start_renders_inline_patient_home_panel`
- `test_home_book_callback_reuses_booking_entry_helper`

Also preserved existing PAT-A1-1 review/confirm regression tests in the same file.

## Environment / execution notes

- No environment blocker prevented running the targeted patient-router test slice.

## Explicit non-goals intentionally left for follow-up PRs

### PAT-A1-2B (intentionally not done here)
- broader callback parity/hardening matrix for all home actions and edge cases;
- deeper home-surface behavioral test expansion beyond minimal acceptance proof.

### PAT-A1-3 (intentionally not done here)
- booking success output humanization (doctor/service/branch label rendering update);
- broader patient success-copy redesign.

### Still out of scope for this PR
- booking internals redesign;
- reminder behavior redesign;
- recommendation detail redesign;
- care product/catalog redesign;
- first-run language picker;
- migrations.
