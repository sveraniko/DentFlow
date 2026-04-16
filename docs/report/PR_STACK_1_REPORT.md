# PR Stack 1 Report — Access, Policy, and Clinic Reference

## 1. Objective
Implement the first canonical persisted DentFlow foundation for Clinic Reference, Access and Identity, and Policy/Configuration contexts on top of Stack 0.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/12_repo_structure_and_code_map.md
4. docs/10_architecture.md
5. docs/22_access_and_identity_model.md
6. docs/23_policy_and_configuration_model.md
7. docs/20_domain_model.md
8. docs/30_data_model.md
9. docs/15_ui_ux_and_product_rules.md
10. docs/17_localization_and_i18n.md
11. docs/70_bot_flows.md
12. docs/72_admin_doctor_owner_ui_contracts.md
13. docs/80_integrations_and_infra.md
14. docs/85_security_and_privacy.md
15. docs/90_pr_plan.md
16. docs/report/PR_STACK_0_REPORT.md
17. booking_docs/00_booking_readme.md

## 3. Precedence Decisions
1. Kept single-clinic-by-default modeling with canonical `clinic_id` and optional `branch_id` (no multi-tenant federation work).
2. Normalized runtime role naming to canonical docs role code `admin` (replacing earlier `clinic_admin` enum surface).
3. Kept Stack 1 scope strictly focused on reference/access/policy foundations; no patient registry or booking logic implemented.
4. Followed baseline-discipline by extending bootstrap SQL in place (no migration chain introduced).

## 4. Scope Implemented
- Added canonical domain entities for clinic reference, access identity, and policy config contexts.
- Extended DB bootstrap with Stack 1 canonical tables in `core_reference`, `access_identity`, and `policy_config` schemas.
- Implemented in-memory repository/service layer for reference retrieval, access resolution, and policy resolution with precedence.
- Added Telegram actor binding and role-check decision model used by runtime guards.
- Integrated role guards for admin/doctor/owner surfaces with localized deny responses.
- Added minimal admin read surfaces (`/clinic`, `/branches`, `/doctors`, `/services`).
- Added reproducible JSON-based Stack 1 seed fixture and seed script.
- Added tests for table bootstrap SQL, reference load/retrieval, access resolution and denial, policy precedence, and seed loading.

## 5. Files Added
- `app/domain/clinic_reference/models.py`
- `app/domain/access_identity/models.py`
- `app/application/clinic_reference.py`
- `app/application/policy.py`
- `app/bootstrap/seed.py`
- `scripts/seed_stack1.py`
- `seeds/stack1_seed.json`
- `tests/test_stack1_foundation.py`
- `docs/report/PR_STACK_1_REPORT.md`

## 6. Files Modified
- `README.md`
- `Makefile`
- `app/bootstrap/runtime.py`
- `app/application/access.py`
- `app/domain/access_identity/roles.py`
- `app/domain/policy_config/models.py`
- `app/infrastructure/db/bootstrap.py`
- `app/interfaces/bots/common.py`
- `app/interfaces/bots/admin/router.py`
- `app/interfaces/bots/doctor/router.py`
- `app/interfaces/bots/owner/router.py`
- `app/interfaces/bots/patient/router.py`
- `scripts/db_bootstrap.py`
- `locales/ru.json`
- `locales/en.json`
- `tests/test_db_bootstrap.py`
- `tests/test_i18n.py`

## 7. Stack 1 Table / Schema Summary
Added Stack 1 table DDL creation in baseline bootstrap:

### `core_reference`
- `clinics`
- `branches`
- `doctors`
- `services`
- `doctor_access_codes`

### `access_identity`
- `actor_identities`
- `telegram_bindings`
- `staff_members`
- `clinic_role_assignments`
- `doctor_profiles`
- `owner_profiles`
- `service_principals`

### `policy_config`
- `policy_sets`
- `policy_values`
- `feature_flags`

## 8. Clinic Reference Model Summary
Implemented canonical entities and retrieval service for:
- Clinic
- Branch
- Doctor
- Service
- DoctorAccessCode

Support included:
- stable IDs from seeded data
- clinic-scoped retrieval
- branch-aware doctor filtering
- lightweight uniqueness intent represented at DDL level (`clinic+code`, `clinic+display_name` where relevant)

## 9. Access and Identity Model Summary
Implemented canonical entities and repository/service flow for:
- ActorIdentity
- TelegramBinding
- StaffMember
- ClinicRoleAssignment
- ServicePrincipal (entity modeled, table created)
- DoctorProfile/OwnerProfile (entities modeled, tables created)

Runtime access resolution now:
- resolves actor context from Telegram user id
- checks active binding + active actor + staff membership
- aggregates active role assignments
- returns structured allow/deny decision with deny reason key

## 10. Policy / Configuration Model Summary
Implemented:
- PolicySet
- PolicyValue
- FeatureFlag
- default policy-key map including required Stack 1 keys
- precedence-aware resolver: entity override -> branch -> clinic -> product default

Supported key families include clinic, booking/reminder-related, care, export, and owner AI flags.

## 11. Runtime Guard Integration
Integrated guard abstraction into role surfaces:
- Patient surface remains open.
- Admin surface requires `admin` role.
- Doctor surface requires `doctor` role.
- Owner surface requires `owner` role.

Unauthorized access returns localized deny messages via i18n catalog.

## 12. Seed / Bootstrap Strategy
Implemented JSON-fixture based reproducible Stack 1 seed:
- `seeds/stack1_seed.json` contains default clinic, branch, doctor/service references, access bindings, role assignments, policy sets/values, and feature flag.
- `app/bootstrap/seed.py` loads fixture into repositories.
- `scripts/seed_stack1.py` runs deterministic local seed loading and prints loaded counts.

## 13. Commands Run
- `pwd; rg --files -g 'AGENTS.md'`
- `find .. -maxdepth 3 -name AGENTS.md`
- multiple `sed -n` reads for authoritative docs and existing code files
- `pytest -q`
- `python scripts/seed_stack1.py`
- `python scripts/seed_stack1.py && pytest -q`

## 14. Test Results
- `pytest -q` passes (5 passed, 4 skipped).
- Stack 1 seed script executes successfully and prints expected loaded counts.

## 15. Known Limitations / Explicit Non-Goals
Not implemented in Stack 1 by design:
- patient registry tables/services
- booking/session/slot logic
- reminders execution engine
- search implementation
- analytics projections/business logic
- document generation/export execution
- Google Sheets sync adapters
- AI business features

Current repositories are in-memory application repositories used to validate model behavior and runtime guard wiring; DB table-level persistence is established at bootstrap layer for Stack 1 contexts.

## 16. Deviations From Docs (if any)
1. Access role implementation normalized to `admin` role code (docs-aligned) rather than prior scaffold enum value `clinic_admin`.
2. PrivilegedActionPolicy table/entity was intentionally not implemented in this stack (kept optional per task scope).

## 17. Risks / Follow-ups for PR Stack 2
1. Introduce concrete SQL repositories over Stack 1 tables (currently in-memory repositories back runtime skeleton).
2. Add integration tests against a real Postgres instance to validate DDL execution and persistence round-trips.
3. Wire policy resolver into broader runtime behaviors once booking/patient contexts are implemented.
4. Expand access context to include explicit revoke/deactivation command paths and audit flows.
5. Ensure Stack 2 patient and booking contexts consume the established clinic/access/policy canonical IDs and precedence rules consistently.
