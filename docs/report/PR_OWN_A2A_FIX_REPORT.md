# PR OWN-A2A-FIX Report — Fix owner service metrics label SQL and close OWN-A2A

## What bug was fixed
- Fixed a runtime-breaking SQL bug in `OwnerAnalyticsService.get_service_metrics(...)` where the query attempted to read `core_reference.services.name`, a column that does not exist.
- The service metrics query now safely reads from existing schema columns only (`title_key`, `code`) and no longer references `name`.

## Exact files changed
- `app/application/owner/service.py`
- `app/interfaces/bots/owner/router.py`
- `tests/test_owner_analytics_stack9a.py`
- `docs/report/PR_OWN_A2A_FIX_REPORT.md`

## How service labels now resolve
`/owner_services` label resolution is now bounded and safe:
1. If `service_title_key` exists and resolves to a localized text (translation value differs from the key), use localized text.
2. Else if `service_code` exists, use service code.
3. Else fall back to compact `service_id`.

Additionally, the service metrics read model carries safe fields from existing schema:
- `service_title_key`
- `service_code`

A compatibility fallback `service_label` remains populated from safe existing fields.

## Tests added/updated
Updated `tests/test_owner_analytics_stack9a.py` with focused coverage for:
- service metrics SQL no longer references `cs.name`;
- service metrics SQL now uses `cs.title_key` and `cs.code`;
- localized `title_key` rendering for service metrics rows;
- fallback to `service_code` when translation is missing;
- fallback to compact service id when no label/code exists;
- owner command non-regression continuity for existing metrics surfaces;
- schema safety check confirming `core_reference.services` has `title_key`/`code` and no `name` field.

## Environment / execution limits
- No environment limitation blocked running the targeted owner analytics tests.

## OWN-A2A closure statement
- With this corrective fix, OWN-A2A runtime label issue is resolved in bounded scope.
- **OWN-A2A is considered closed if acceptance criteria pass**:
  - `/owner_services` no longer depends on nonexistent `core_reference.services.name`;
  - service labels resolve via localized title key / code / compact id fallback;
  - other owner metrics commands remain non-regressed;
  - no migrations were introduced.
