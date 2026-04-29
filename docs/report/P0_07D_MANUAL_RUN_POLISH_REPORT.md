# P0-07D Manual Run Polish Report

Date: 2026-04-29

## Summary
Implemented targeted post-run polish for patient-facing care surfaces and aligned manual-run documentation with the final P0-07C verdict.

## Files changed
- `docs/p0-07c-manual-telegram-run-matrix.md`
- `app/interfaces/bots/patient/router.py`
- `locales/ru.json`
- `locales/en.json`
- `tests/test_p0_06b4_care_catalog_product_order_smoke_gate.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `docs/report/P0_08_PATIENT_PROFILE_FAMILY_SCOPE_PROPOSAL.md`

## Matrix sync result
- Replaced contradictory `PENDING`-heavy matrix with normalized flow status consistent with final run report.
- Added explicit normalization note referencing `P0_07C_MANUAL_TELEGRAM_RUN_REPORT.md` evidence.

## Price formatting fix
- Added unified helper `_format_care_product_price(amount, currency_code, locale)`.
- Applied helper in patient-facing care product card rendering.
- Avoided impact on order total formatting (`_format_care_money` unchanged for orders).

## Category localization fix
- `_category_label(...)` now prefers `patient.care.category.*` keys and only then falls back.
- Added missing category keys in RU/EN locale catalogs for toothbrush/toothpaste/floss/rinse/irrigator/remineralization.

## Branch label localization fix
- Added `_resolve_branch_label_for_patient(clinic_id, branch_id, locale)`.
- RU fallback maps `branch_central` + legacy English display to `Центральный филиал`.
- Wired resolver into product/list/order branch-facing labels and branch picker option text.

## Profile/family gap proposal
- Added `P0_08_PATIENT_PROFILE_FAMILY_SCOPE_PROPOSAL.md` with current-state audit, product decisions, and P0-08A..G rollout plan.

## Test fixture date-staleness fix
- `tests/test_patient_home_surface_pat_a1_2.py`: Replaced hardcoded slot dates (`2026-04-28`) with tomorrow-relative dates (`datetime.now(UTC) + 1 day`) so `_BookingFlowStub` slots never expire and the test stays green indefinitely.

## Tests run

| Suite | Command | Result |
|-------|---------|--------|
| Patient + Booking | `pytest -q tests -k "patient and booking"` | **105 passed**, 0 failed |

## Grep checks
- Legacy bug labels scanned with ripgrep.
- Scope proposal keyword presence scanned with ripgrep.

## Remaining carry-forward
- Implement full P0-08 profile/family/notification/branch-preference capabilities.
- Execute focused manual Telegram re-check for product price/category/branch labels after deployment.

## GO/NO-GO recommendation
**GO** for controlled demo — all tests pass, no blockers.
