# PR PAT-A8-1A Report — Canonical patient current reserve/order surface

## What changed
- Added callback-driven patient orders entry via `care:orders` and `care:catalog` callbacks.
- Kept `/care_orders` and `/care_order_repeat` command paths fully intact for backward compatibility.
- Updated care categories surface (`/care`, `phome:care`) to include a compact CTA button to open the canonical patient orders surface.
- Canonicalized patient care orders panel to show:
  - current/live reserve/order block first;
  - history block below;
  - compact open/repeat actions preserved per order;
  - empty-state with bounded CTA back to care catalog.
- Added a bounded status classification helper for current/live vs history aligned with existing care-order terminal statuses.

## Exact files changed
- `app/interfaces/bots/patient/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `tests/test_patient_care_ui_cc4f.py`
- `docs/report/PR_PAT_A8_1A_REPORT.md`

## Current/live vs history semantics
- Implemented in router with:
  - terminal statuses: `fulfilled`, `canceled`, `expired`;
  - current/live statuses: all non-terminal statuses.
- The canonical surface sorts patient orders by `updated_at` descending.
- It displays current/live block first (latest live order at top), and history block below (terminal/past orders).

## Callback-driven entry added
- New callback `care:orders` -> resolves patient identity and renders the same canonical surface used by `/care_orders`.
- New callback `care:catalog` -> bounded return path to care catalog from orders empty-state and orders surface.
- Added `My reserves / orders` CTA on the primary care entry surface (`/care` and `phome:care` categories panel).

## Tests added/updated
- `tests/test_patient_home_surface_pat_a1_2.py`
  - verifies care entry includes `care:orders` CTA;
  - verifies `/care_orders` command and `care:orders` callback land on the same canonical surface;
  - verifies orders empty-state includes callback CTA back to care catalog.
- `tests/test_patient_care_ui_cc4f.py`
  - verifies live/history splitting semantics prioritize live statuses before terminal history.

## Environment / execution limits
- If full suite execution is constrained, this PR relies on targeted test runs for changed patient-care surfaces.

## Explicit non-goals left for PAT-A8-1B / PAT-A8-2
- No proactive pickup-ready notifications.
- No payment or checkout redesign.
- No recommendation engine redesign.
- No care-commerce state-machine redesign.
- No admin/doctor/owner flow changes.
- No post-reserve handoff beyond this bounded canonical orders surface.
- No migrations.
