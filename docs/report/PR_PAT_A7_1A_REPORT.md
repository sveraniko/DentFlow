# PR_PAT_A7_1A Report

## What changed
- Implemented a canonical patient recommendations/aftercare surface in `patient/router.py` via `_render_recommendations_panel(...)`.
- Both `/recommendations` and `phome:recommendations` now route through the same canonical panel helper.
- Added latest-vs-history rendering semantics with patient-friendly copy and no raw recommendation IDs in main panel text.
- Added callback-driven recommendation open flow (`prec:open:<recommendation_id>`) to replace raw ID command navigation as primary UX.
- Added callback-driven recommendation lifecycle actions (`prec:act:<action>:<recommendation_id>`) for acknowledge/accept/decline.
- Recommendation detail now uses human-readable type and status labels, with localized labels.
- Added optional callback action to enter recommendation-linked products (`prec:products:<recommendation_id>`) when care-commerce is available.
- Kept backward-compatible command routes (`/recommendation_open`, `/recommendation_action`, `/recommendation_products`) in place.

## Exact files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `docs/report/PR_PAT_A7_1A_REPORT.md`

## Latest/history semantics
- Input list uses existing repository ordering (`created_at DESC`) from `RecommendationService.list_for_patient(...)`.
- Canonical panel chooses the first non-terminal recommendation as latest/active when available.
- Terminal statuses treated as historical for this purpose: `accepted`, `declined`, `withdrawn`, `expired`.
- If all rows are terminal, the first row (latest by existing order) is still shown as latest, and remaining rows are shown as history.

## Callback-driven open/action flow
- Open detail callback:
  - `prec:open:<recommendation_id>`
  - resolves patient ownership as existing command flows do;
  - marks `issued` recommendation as `viewed` (same semantics preserved);
  - renders canonical detail panel with action buttons.
- Lifecycle action callback:
  - `prec:act:<action>:<recommendation_id>` where action is `ack`, `accept`, `decline`;
  - preserves existing lifecycle transition rules via `RecommendationService`;
  - on success, re-renders detail panel coherently with updated status.
- Optional care entry callback:
  - `prec:products:<recommendation_id>`
  - keeps recommendation→care-product bridge available where target exists.

## Tests added/updated
- Updated `tests/test_patient_home_surface_pat_a1_2.py` with focused patient-flow coverage:
  1. canonical `/recommendations` panel renders latest first and avoids raw command hints in text,
  2. `prec:open:*` opens detail and marks issued recommendation viewed,
  3. `prec:act:*` updates lifecycle and re-renders coherent detail panel.

## Environment / execution notes
- Targeted pytest subset for touched surfaces was executed.
- No migrations were created.

## Explicit non-goals left for PAT-A7-1B and PAT-A7-2
- No proactive push delivery implementation.
- No patient-facing document/PDF/export delivery.
- No recommendation engine redesign.
- No care-commerce subsystem redesign.
- No admin/doctor/owner flow redesign.
