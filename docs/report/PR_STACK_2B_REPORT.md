# PR Stack 2B Report — Patient Registry Runtime Reality

## 1. Objective
Deliver the final Stack 2 hardening pass so Patient Registry is a reliable runtime dependency for Booking Core, with DB-truth-safe seed/loading/upsert behavior and no booking-scope expansion.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/12_repo_structure_and_code_map.md
4. docs/10_architecture.md
5. docs/20_domain_model.md
6. docs/30_data_model.md
7. docs/40_search_model.md
8. docs/85_security_and_privacy.md
9. docs/90_pr_plan.md
10. docs/report/PR_STACK_0_REPORT.md
11. docs/report/PR_STACK_1_REPORT.md
12. docs/report/PR_STACK_2_REPORT.md
13. docs/report/PR_STACK_2A_REPORT.md

## 3. Scope Implemented
- Fixed Stack 2 seed reliability for patient flags and medical summaries when fixture timestamps are missing.
- Added DB-backed Patient Registry hydration via `DbPatientRegistryRepository.load(...)` for patients, contacts, preferences, flags, photos, summaries, and external IDs.
- Updated patient sub-entity upsert SQL conflict targets to match patient identity semantics.
- Strengthened exact-contact semantics with a DB uniqueness strategy aligned to normalized exact matching.
- Added behavioral tests for seed defaults, DB load/hydration, and DB-truth upsert conflict paths.

## 4. Seed Reliability Fixes
- Introduced deterministic `DEFAULT_SEED_TIMESTAMP = 2024-01-01T00:00:00Z` in seed path.
- `seed_stack2_patients` now defaults `patient_flags.set_at` when omitted, preventing NOT NULL violations.
- `seed_stack2_patients` now defaults `patient_medical_summaries.created_at` and `last_updated_at` when omitted.
- Seed path remains explicit/synthetic-only and deterministic; no runtime auto-seeding was introduced.

## 5. Patient Registry Read/Load Strategy
Chosen strategy: **A — DB loader hydration into in-memory runtime repository**.

- Implemented `DbPatientRegistryRepository.load(db_config)` with explicit column lists and explicit row→domain mapping.
- Loader supports all required patient-registry entities:
  - patients
  - contacts
  - preferences
  - flags
  - photos
  - medical summaries
  - external IDs
- Loader intentionally avoids `SELECT *` and ignores audit-only columns by not selecting them.

## 6. Upsert / Uniqueness Strategy Decisions
### `patient_preferences`
- DB uniqueness already expresses one preference per patient (`UNIQUE(patient_id)`).
- Upsert now conflicts on `patient_id` (not only synthetic row id).

### `patient_medical_summaries`
- DB uniqueness already expresses one summary per patient (`UNIQUE(patient_id)`).
- Upsert now conflicts on `patient_id`.
- On update, `created_at` is preserved from existing row (`created_at=core_patient.patient_medical_summaries.created_at`).

### `patient_external_ids`
- Baseline uniqueness changed to `UNIQUE(patient_id, external_system)` for identity-stable patient/system mapping.
- Retained `UNIQUE(external_system, external_id)` for deterministic reverse resolution.
- Upsert now conflicts on `(patient_id, external_system)` so updating external ID for same patient/system works in fresh-process DB-truth scenarios.

### Exact contact semantics (`patient_contacts`)
- Added `UNIQUE(patient_id, contact_type, normalized_value)`.
- Contact persistence now conflicts on `(patient_id, contact_type, normalized_value)` so repeated exact upserts after process restart do not create duplicates.
- Exact resolution remains normalized and DB-query-capable through `find_patient_by_exact_contact(...)`.

## 7. Files Added
- `tests/test_patient_db_load_and_seed.py`
- `docs/report/PR_STACK_2B_REPORT.md`

## 8. Files Modified
- `app/infrastructure/db/bootstrap.py`
- `app/infrastructure/db/patient_repository.py`
- `tests/test_db_bootstrap.py`

## 9. Commands Run
- `find .. -name AGENTS.md -print`
- multiple `sed -n` reads for required docs and relevant code files
- `rg -n` targeted code navigation
- `pytest -q tests/test_patient_db_load_and_seed.py tests/test_patient_db_persistence.py`

## 10. Test Results
- `pytest -q tests/test_patient_db_load_and_seed.py tests/test_patient_db_persistence.py` → **pass** (4 passed).

## 11. Remaining Known Limitations
- Environment-level async pytest plugin support (`pytest-asyncio`) is still absent in this container, so tests depending on `@pytest.mark.asyncio` fail if run directly without plugin setup.
- This PR intentionally does not add booking/session/slot logic (out of scope).

## 12. Deviations From Docs (if any)
- No intentional domain-boundary deviations.
- Baseline constraints were strengthened in place (consistent with baseline-discipline rules).

## 13. Readiness Assessment for Booking Stack 3A
- Patient Registry now has a coherent DB-backed load path for runtime hydration.
- Seed path no longer depends on missing fixture timestamps for medical summaries and no longer risks `set_at` NOT NULL failures for flags.
- Upsert behavior for singleton-like patient sub-entities is conflict-safe by patient identity semantics.
- Exact normalized contact semantics are DB-truth-compatible and less duplicate-prone across fresh-process restarts.
- Based on covered tests, Stack 2B is materially more reliable as a Booking Core dependency runway.
