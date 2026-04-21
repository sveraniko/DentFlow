# PR PAT-A1-2B Report — Patient home hardening, callback parity, and focused regressions

## What changed after PAT-A1-2A

This PR is a bounded hardening pass on the inline `/start` patient home surface introduced in PAT-A1-2A.

- Added focused regression tests that prove slash-command and `phome:*` callback entry parity for:
  - `/book` ↔ `phome:book`
  - `/my_booking` ↔ `phome:my_booking`
  - `/recommendations` ↔ `phome:recommendations` (when recommendation service is available)
  - `/care` ↔ `phome:care` (when care service is available)
- Added focused tests for optional-action safety:
  - `/start` home panel hides optional buttons when optional services are unavailable.
  - stale/manual optional callback for an unavailable action fails safely with bounded localized fallback and no crash.
- Confirmed PAT-A1-1 review/confirm regression safety by executing the existing targeted PAT-A1-1 and booking flow suites alongside the new home-surface suite.

No runtime redesign was introduced in this PR, and no migration work was added.

## Exact files changed

- `tests/test_patient_home_surface_pat_a1_2.py` (new)
- `docs/report/PR_PAT_A1_2B_REPORT.md` (new)

## Tests added/updated

### Added
- `tests/test_patient_home_surface_pat_a1_2.py`
  - `test_start_renders_inline_home_panel_with_localized_actions`
  - `test_book_and_home_book_callback_have_equivalent_entry_state`
  - `test_my_booking_and_home_callback_have_equivalent_entry_state`
  - `test_recommendations_command_and_home_callback_share_entry_when_available`
  - `test_care_command_and_home_callback_share_entry_when_available`
  - `test_home_hides_optional_actions_when_services_unavailable`
  - `test_stale_optional_callback_is_safe_when_service_unavailable`

### Executed regression suites
- `tests/test_patient_first_booking_review_pat_a1_1.py`
- `tests/test_booking_patient_flow_stack3c1.py`

## Environment / execution notes

- No environment blockers prevented running the targeted test slice for this PR.

## Migrations

- No migrations introduced.

## Closure statement

- **PAT-A1-2 is now considered closed** (A1-2A + A1-2B): inline-first `/start` home exists, callback/command parity is covered by focused tests, optional actions are gated and safely handled when unavailable, and PAT-A1-1 review/confirm behavior remains regression-safe.

## Explicit non-goals left for PAT-A1-3

- Booking success-message humanization and richer patient-facing success copy.
- Any language picker logic.
- Any redesign of recommendation/care product experiences beyond bounded safety/parity.
- Any migration/schema changes.
