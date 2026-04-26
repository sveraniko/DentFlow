# PR PILOT-A1C Report — Live-start blocker consolidation and packaging hardening

## Scope
This PR formalizes live-start fixes from first Telegram polling startup and closes immediate launch-readiness gaps before canned scenario smoke.

## Live-start blockers formalized
1. Nested `pydantic-settings` classes read `.env` (`env_file` + `env_file_encoding`) for launch-time consistency.
2. Runtime dispatcher wiring is guarded so `make_patient_router()` is called only with supported kwargs.
3. Generic seed helper behavior is locked:
   - JSONB values are serialized safely.
   - `None` non-PK columns are omitted so DB defaults apply.
4. Patient seed/persistence hardening is covered:
   - `birth_date` string coercion to `datetime.date`.
   - `contact_time_window` JSON serialization.
   - `persist_flag(..., event_name=...)` in stack2 flow.
5. Packaging fix for editable/install builds:
   - `pyproject.toml` includes wheel package declaration for `app`.
6. Security launch note added:
   - `.env` must not be committed or included in shared archives; rotate Telegram tokens if leaked.

## Exact files changed
- `pyproject.toml`
- `tests/test_pilot_a1c_hardening.py`
- `docs/PILOT_LAUNCH_RUNBOOK.md`
- `README.md`
- `docs/report/PR_PILOT_A1C_REPORT.md`

## Packaging fix
Added:

```toml
[tool.hatch.build.targets.wheel]
packages = ["app"]
```

## Settings/env fix
- Verified nested settings loading behavior via focused tests using `.env` file and env override semantics (without printing secrets).

## Seed fix coverage
Focused tests added for:
- JSONB dict/list serialization in generic seed helper.
- Omission of `None` defaultable columns from INSERT.
- `persist_patient` date coercion.
- `persist_preferences` JSON serialization.
- `seed_stack2_patients` passing `event_name` to `persist_flag`.

## Runtime wiring guard
Focused dispatcher build test asserts patient router call signature remains compatible and catches unsupported kwargs.

## Security note
Runbook and README now include practical warning:
- never commit `.env`
- never include `.env` in shared archives/reports
- rotate Telegram tokens if `.env` was exposed

## Tests added/updated
- Added `tests/test_pilot_a1c_hardening.py`.

## Environment limitations
- No environment blockers prevented execution of the focused A1C tests.

## Next step
Proceed to **PILOT-A2 canned role scenarios**.
