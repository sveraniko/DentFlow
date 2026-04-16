# PR Stack 0 Report — Repository Foundation and Runtime Skeleton

## 1. Objective
Establish a clean, runnable DentFlow foundation covering repository structure, typed config loading, role-surface runtime skeletons, RU/EN localization bootstrap, DB baseline bootstrap path, worker skeleton, and smoke scaffolding.

## 2. Docs Read
- README.md
- docs/18_development_rules_and_baseline.md
- docs/10_architecture.md
- docs/12_repo_structure_and_code_map.md
- docs/15_ui_ux_and_product_rules.md
- docs/17_localization_and_i18n.md
- docs/22_access_and_identity_model.md
- docs/23_policy_and_configuration_model.md
- docs/30_data_model.md
- docs/70_bot_flows.md
- docs/80_integrations_and_infra.md
- docs/90_pr_plan.md
- docs/95_testing_and_launch.md

## 3. Precedence Decisions
1. Used the precedence order requested in the task prompt, even where README presents a slightly different ordering.
2. Followed Stack 0 scope from docs/90_pr_plan.md and did not implement Layer 1+ business functionality.
3. Applied baseline DB discipline from docs/18_development_rules_and_baseline.md: schema bootstrap script, no migration chain generation.

## 4. Scope Implemented
- Python package skeleton under `app/` aligned to code-map structure.
- Typed grouped settings with explicit env prefixes.
- Runtime registry with separated role routers (patient/admin/doctor/owner).
- i18n service with RU/EN locale files and fallback behavior.
- DB bootstrap script creating logical schemas and health-checkable DB path.
- Worker bootstrap runtime and task registry placeholder.
- Access-role abstraction stub and policy model stub.
- Smoke tests for config, runtime, i18n, worker bootstrap, DB bootstrap.

## 5. Files Added
- `pyproject.toml`, `.env.example`, `Makefile`
- `app/main.py`, `app/worker.py`
- `app/bootstrap/logging.py`, `app/bootstrap/runtime.py`
- `app/config/settings.py`
- `app/common/i18n.py`, `app/common/panels.py`
- `app/application/access.py`
- `app/domain/access_identity/roles.py`, `app/domain/policy_config/models.py`
- `app/interfaces/bots/common.py`
- `app/interfaces/bots/patient/router.py`
- `app/interfaces/bots/admin/router.py`
- `app/interfaces/bots/doctor/router.py`
- `app/interfaces/bots/owner/router.py`
- `app/infrastructure/db/engine.py`, `app/infrastructure/db/bootstrap.py`
- `app/infrastructure/workers/tasks.py`
- `scripts/db_bootstrap.py`
- `locales/ru.json`, `locales/en.json`
- `tests/conftest.py`, `tests/test_config.py`, `tests/test_i18n.py`, `tests/test_runtime.py`, `tests/test_worker.py`, `tests/test_db_bootstrap.py`
- package marker `__init__.py` files for created package directories

## 6. Files Modified
- `README.md` (Stack 0 bootstrap command section)

## 7. Repo Structure Summary
Implemented canonical top-level skeleton:
- `app/` (bootstrap/config/common/interfaces/application/domain/infrastructure/projections/integrations/ai)
- `locales/`
- `scripts/`
- `tests/`
- `docs/report/`
- `migrations/`, `seeds/` (present as baseline placeholders)

## 8. Technical Choices Made
- **Language/runtime**: Python 3.12+.
- **Telegram framework**: aiogram 3.x.
- **Settings**: pydantic-settings with typed grouped config sections.
- **DB layer**: SQLAlchemy async engine configured for asyncpg DSN.
- **Logging**: stdlib logging with optional JSON formatter.
- **Dependency tool**: single `pyproject.toml` setup (no parallel package managers introduced).

## 9. DB Baseline / Bootstrap Strategy
- Implemented schema bootstrap utility (`scripts/db_bootstrap.py`) calling async bootstrap service.
- Schemas created with `CREATE SCHEMA IF NOT EXISTS` to support clean rebuild behavior.
- Included canonical schemas from data model docs plus `platform` schema for internal infrastructure bookkeeping extension.
- No migration chain generation introduced.

## 10. Runtime Entry Points
- App bootstrap entry: `python -m app.main`
- Worker bootstrap entry: `python -m app.worker`
- DB bootstrap entry: `python scripts/db_bootstrap.py`
- Makefile wrappers: `make run-app`, `make run-worker`, `make db-bootstrap`

## 11. Localization Setup
- Centralized i18n loader/service in `app/common/i18n.py`.
- Locale resources in `locales/ru.json` and `locales/en.json`.
- Handler text routed through translation keys for role-home skeleton text.
- Fallback strategy: requested locale -> default locale -> key name.

## 12. Worker Skeleton Setup
- Worker entrypoint in `app/worker.py`.
- Task registration pattern via `TaskRegistry` in `app/infrastructure/workers/tasks.py`.
- Placeholder heartbeat task and loop wiring for future async jobs.

## 13. Commands Run
- `find .. -name AGENTS.md -print`
- `rg --files`
- multiple `sed -n` document review commands for authoritative docs
- file creation/update commands via shell redirection
- `pytest -q`

## 14. Test Results
- All Stack 0 smoke tests pass locally with `pytest -q`.
- Covered: config load, i18n resolution, role router registration, worker bootstrap, DB bootstrap call path.

## 15. Known Limitations / Explicit Non-Goals
Not implemented in this stack by design:
- real booking flows/state logic
- reminder business behavior
- search functionality
- analytics/owner metrics logic
- care-commerce logic
- external integrations
- document generation
- AI business workflows
- full auth and policy persistence

## 16. Deviations From Docs (if any)
- No material architecture deviation identified for Stack 0.
- Added internal `platform` DB schema as a neutral extension point for system-level operational metadata; domain schemas remain unchanged.

## 17. Risks / Follow-ups for PR Stack 1
1. Replace access stub with explicit persisted identity/role binding model.
2. Introduce policy/config persistence and resolution precedence implementation.
3. Add clinic/branch/doctor/service reference baseline models.
4. Extend runtime startup with role-auth guards and actor context resolution.
5. Add integration tests using a real Postgres service in CI for DB bootstrap verification.
