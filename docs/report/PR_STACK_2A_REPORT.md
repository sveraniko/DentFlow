# PR Stack 2A Report — Foundation Persistence Hardening

## 1. Objective
Harden Stack 1/2 persistence and runtime hydration so seeded DB data loads safely, fix known Patient Registry correctness bugs, and add stronger behavioral tests that catch real runtime/data failures before Stack 3.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/12_repo_structure_and_code_map.md
4. docs/10_architecture.md
5. docs/20_domain_model.md
6. docs/22_access_and_identity_model.md
7. docs/23_policy_and_configuration_model.md
8. docs/30_data_model.md
9. docs/85_security_and_privacy.md
10. docs/90_pr_plan.md
11. docs/report/PR_STACK_0_REPORT.md
12. docs/report/PR_STACK_1_REPORT.md
13. docs/report/PR_STACK_2_REPORT.md

## 3. Scope Implemented
- Reworked Stack 1 DB loader hydration to explicit row→domain mapping with explicit enum conversion and no raw `SELECT *` dataclass splatting.
- Fixed Patient Registry correctness issues for:
  - photo primary selection consistency,
  - external ID upsert overwrite order,
  - medical summary `last_updated_at` refresh and `created_at` preservation.
- Added DB-backed persistence methods for patient preferences, flags, photos, medical summaries, and external IDs in the DB repository/service layer.
- Added deterministic retrieval helpers for preferences, active flags, primary photo, medical summary, and external IDs.
- Replaced shallow source-inspection runtime wiring test with behavior-based repository loader invocation test and added explicit hydration behavior test coverage.

## 4. Runtime Loader Fixes
- `DbClinicReferenceRepository.load` now uses explicit column lists and explicit mapping into domain dataclasses.
- `DbAccessRepository.load` now maps only domain fields and converts all enum-bearing fields safely.
- `DbPolicyRepository.load` now maps policy entities explicitly and converts policy status enum.
- Loaders now ignore storage-only audit columns by construction (they are not selected/mapped).

## 5. Patient Registry Fixes
- Fixed primary-photo race/order bug by persisting photo in repository before `set_primary_photo`, then enforcing one-primary semantics across patient photos.
- Fixed external ID upsert merge-order bug so the new `external_id` value is preserved when existing row exists.
- Fixed medical summary upsert merge order so `last_updated_at` always refreshes on each upsert while `created_at` remains stable for existing summary rows.

## 6. DB-backed Persistence Additions
Added repository persistence methods and DB service methods for:
- preferences (`persist_preferences`, `upsert_preferences_db`),
- flags (`persist_flag`, `add_flag_db`, `deactivate_flag_db`),
- photos (`persist_photo`, `add_photo_db`, `set_primary_photo_db`),
- medical summaries (`persist_medical_summary`, `upsert_medical_summary_db`),
- external IDs (`persist_external_id`, `upsert_external_id_db`).

These methods write to canonical `core_patient` tables and do not introduce shadow tables/JSON blob storage for business entities.

## 7. Files Added
- `tests/test_stack1_loader_hydration.py`
- `tests/test_patient_db_persistence.py`
- `docs/report/PR_STACK_2A_REPORT.md`

## 8. Files Modified
- `app/infrastructure/db/repositories.py`
- `app/application/patient/registry.py`
- `app/infrastructure/db/patient_repository.py`
- `tests/test_patient_registry.py`
- `tests/test_runtime_wiring.py`

## 9. Commands Run
- `sed -n` reads for all required authoritative docs and prior reports
- `rg -n` targeted code inspection for loader/patient paths
- `pytest -q`
- `pytest -q tests/test_patient_registry.py tests/test_stack1_loader_hydration.py tests/test_patient_db_persistence.py tests/test_runtime_wiring.py`

## 10. Test Results
- Full suite command `pytest -q` currently fails in this environment due missing async pytest plugin support (`pytest.mark.asyncio` not recognized in baseline env), impacting both existing tests and new async-marked tests outside this PR.
- Targeted changed-scope behavioral tests pass:
  - `tests/test_patient_registry.py`
  - `tests/test_stack1_loader_hydration.py`
  - `tests/test_patient_db_persistence.py`
  - `tests/test_runtime_wiring.py`

## 11. Remaining Known Limitations
- Environment currently lacks async pytest plugin support for running full async-marked test suite end-to-end in one command.
- This PR intentionally does not add Stack 3 booking/session/slot logic or any forbidden out-of-scope features.

## 12. Deviations From Docs (if any)
- None intentional. Changes stay within documented Stack 1/2 ownership boundaries and canonical `core_patient`/Stack 1 context tables.

## 13. Readiness Assessment for PR Stack 3
- Stack 1 runtime loaders are now safer against seeded DB row shapes with audit columns.
- Patient Registry correctness regressions called out in this hardening request are now behaviorally covered by tests.
- DB-backed persistence path for patient sub-entities is now coherent enough to support Stack 3 integration work without relying on partial/in-memory-only behavior.
- Remaining blocker for broader CI confidence is environment-level async test plugin setup, not model/persistence design scope.
