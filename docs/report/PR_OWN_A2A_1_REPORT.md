# PR OWN-A2A-1 Report — Owner staff roster and access overview shell

## What changed
Added a bounded read-only owner governance visibility surface for staff/access overview, including Telegram binding visibility and role/access status where existing DB truth supports it.

## Exact files changed
- app/application/owner/service.py
- app/application/owner/__init__.py
- app/interfaces/bots/owner/router.py
- locales/en.json
- locales/ru.json
- tests/test_owner_governance_own_a2a.py
- docs/report/PR_OWN_A2A_1_REPORT.md

## Command added
- `/owner_staff`

Optional argument:
- `/owner_staff <limit>`

Bounds:
- default limit: 30
- max limit: 100
- invalid limit: localized bounded error + usage hint

## Staff/access fields currently supported
From existing DB truth (no migrations), each row attempts to provide:
- actor_id
- display_name (staff display_name/full_name/actor display_name fallback chain)
- role_code
- role_label (owner/admin/doctor localized label source string on service row)
- staff_kind (`owner`/`admin`/`doctor`/`unknown`)
- doctor_id (if doctor profile linkage exists)
- telegram_binding_state (`yes`/`no`/`unknown`)
- active_state (`active`/`inactive`/`unknown`)
- branch_id + branch_label (if assignment/staff primary branch present)
- created_at (from existing actor/staff timestamps)
- last_seen_at (from primary Telegram binding)

## Fields unavailable/unknown and why
- Some staff can resolve to `unknown` role/staff kind if no active role assignment exists for the clinic.
- Telegram binding can resolve to `unknown` for inactive primary binding rows.
- Branch can be missing if neither role assignment branch nor staff primary branch is present.
- Display name falls back to compact actor id when no human-readable label exists.
- No extra inferred/offline HR fields are introduced because this PR intentionally reuses only existing access/reference truth.

## Tests added/updated
Added focused test file:
- `tests/test_owner_governance_own_a2a.py`

Coverage includes:
- `/owner_staff` owner guard behavior
- default limit parse (=30)
- explicit valid limit parse
- invalid limit bounded usage/error behavior
- row rendering with role + Telegram binding state
- missing label fallback to compact actor id
- empty state rendering
- unavailable/error bounded behavior
- non-regression sanity for existing `/owner_today`

## Environment limitations
No environment limitation prevented running the targeted owner governance tests for this PR.

## Explicit non-goals left for OWN-A2A-2 and OWN-A2B
- No staff mutation flows.
- No staff offboarding.
- No role editing or role architecture redesign.
- No patient-base owner governance panel yet.
- No clinic reference governance expansion beyond this bounded staff/access shell.
- No owner AI summaries/Q&A.
- No revenue analytics.
- No migrations.
