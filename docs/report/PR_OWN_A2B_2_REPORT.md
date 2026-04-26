# PR OWN-A2B-2 Report — Owner clinic reference overview

## What changed
Added a bounded owner-facing read-only clinic reference overview panel so owner can inspect branches, services, and doctors in one compact governance snapshot.

## Exact files changed
- app/application/owner/service.py
- app/application/owner/__init__.py
- app/interfaces/bots/owner/router.py
- locales/en.json
- locales/ru.json
- tests/test_owner_governance_own_a2b.py
- docs/73_governance_and_reference_ops.md
- docs/71_role_scenarios_and_acceptance.md
- docs/report/PR_OWN_A2B_2_REPORT.md

## Command added
- `/owner_references`
- optional argument: `/owner_references <limit>`

Bounds:
- default limit: 20 (per section)
- max limit: 50 (per section)
- invalid limit: localized bounded error + usage hint

## Read model and supported fields
New owner read model method in owner analytics service:
- `get_clinic_reference_overview(clinic_id: str, limit: int = 20)`

Supported fields from existing reference tables only (no migrations):

Branches (`core_reference.branches`):
- `branch_id`
- `display_name`
- `status`
- `timezone`

Services (`core_reference.services`):
- `service_id`
- `code`
- `title_key`
- `duration_minutes`
- `status`

Doctors (`core_reference.doctors` + cheap branch join):
- `doctor_id`
- `display_name`
- `specialty` (mapped from `specialty_code`)
- `status`
- `branch_id`
- `branch_display_name` (if join resolves)

## Unavailable/unknown behavior and why
- Missing/NULL fields are rendered as localized `unknown` in router output.
- Service label localization is best-effort:
  1) translated `title_key` if translation exists,
  2) else `code`,
  3) else compact `service_id`.
- If reference read fails, command returns bounded localized unavailable message.
- No reference editing/mutation actions are added in this PR by design.

## Tests added/updated
Updated `tests/test_owner_governance_own_a2b.py` to cover:
- owner guard on `/owner_references`
- default limit parse (20)
- explicit valid limit parse
- invalid limit bounded usage/error
- separate branches/services/doctors sections rendering
- service `title_key` localization and fallback safety (code/id)
- empty section rendering
- unavailable fallback rendering
- non-regression sanity for existing `/owner_today` and `/owner_patients`
- no editing/mutation command surface added in this slice

## Docs truth updates
- `docs/73_governance_and_reference_ops.md`: GOV-010 evidence/status text now includes bounded owner governance snapshots (`/owner_staff`, `/owner_patients`, `/owner_references`).
- `docs/71_role_scenarios_and_acceptance.md`: owner section notes bounded governance read snapshots now available (read-only only).

## Environment / execution limits
- No environment limitation blocked targeted test execution in this PR slice.

## OWN-A2B closure statement
- OWN-A2B includes:
  - OWN-A2B-1 patient base snapshot
  - OWN-A2B-2 clinic reference overview
- **OWN-A2B is now considered closed in bounded scope** (staff/access + patient base + clinic references visibility are present as read-only owner governance surfaces, with no mutation/editing and no migrations).
