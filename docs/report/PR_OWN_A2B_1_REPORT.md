# PR OWN-A2B-1 Report — Owner patient base snapshot

## What changed
Added a bounded read-only owner governance snapshot for patient base visibility.

## Exact files changed
- app/application/owner/service.py
- app/application/owner/__init__.py
- app/interfaces/bots/owner/router.py
- locales/en.json
- locales/ru.json
- tests/test_owner_governance_own_a2b.py
- docs/report/PR_OWN_A2B_1_REPORT.md

## Command added
- `/owner_patients`
- optional argument: `/owner_patients <days>`

Window rules:
- default window: 30 days
- accepted window: 1..365
- invalid window: localized bounded error + usage hint

## Supported patient-base metrics (existing DB truth only)
- total patients count (`core_patient.patients`)
- new patients in selected window (`core_patient.patients.created_at`, clinic-local date window)
- patients with upcoming/live bookings (`booking.bookings`, distinct `resolved_patient_id`, status-bounded)
- patients with completed bookings in selected window (`booking.bookings.completed_at`, clinic-local date window)
- patients with active care orders/reservations (`care_commerce.care_orders` + `care_commerce.care_reservations`)
- patients with Telegram binding (`core_patient.patient_external_ids.external_system='telegram'`)
- recent new patients list (bounded to max 10 rows, display name fallback to compact patient id)

## Unavailable/unknown behavior and why
- Metric fields are rendered as `unknown` if a specific read query fails (safe partial-failure behavior).
- Entire panel returns a bounded unavailable message if snapshot read raises a higher-level error.
- No schema expansion was attempted; metrics are derived only from currently available tables/fields.

## Data minimization / privacy notes
- No full patient dump.
- No patient editing or mutation.
- No export/pagination.
- No clinical fields (notes, diagnoses, recommendations, documents) are shown.
- Recent list includes only display label (or compact id) and creation date.

## Tests added/updated
Added `tests/test_owner_governance_own_a2b.py` with focused coverage for:
- owner guard for `/owner_patients`
- default 30-day window parse
- explicit valid window parse
- invalid window bounded usage/error
- rendering of supported counts
- unknown metric rendering
- unavailable fallback rendering
- bounded recent list behavior (max 10)
- privacy safety assertions (no clinical/private content terms in output)
- non-regression sanity for existing `/owner_today`

## Environment limitations
- No environment limitation blocked targeted test execution for this PR slice.

## Explicit non-goals left for OWN-A2B-2 and later governance mutation phases
- No patient editing/mutation flows.
- No patient CRM search/export expansion.
- No patient clinical/document access.
- No staff mutation/offboarding.
- No patient/admin/doctor operational flow changes.
- No migrations.
