# PR Stack 7A1 Report — Clinical History Integrity + Chart Summary Completeness + Timezone Presentation

## 1. Objective
Harden Stack 7A clinical baseline with explicit versioned-current semantics for diagnosis and treatment plans, chart-wide note aggregation for summary accuracy, and clinic/branch-aware local timestamp presentation for doctor-facing operational/clinical outputs.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/10_architecture.md
4. docs/12_repo_structure_and_code_map.md
5. docs/20_domain_model.md
6. docs/30_data_model.md
7. docs/15_ui_ux_and_product_rules.md
8. docs/17_localization_and_i18n.md
9. docs/22_access_and_identity_model.md
10. docs/23_policy_and_configuration_model.md
11. docs/25_state_machines.md
12. docs/65_document_templates_and_043_mapping.md
13. docs/70_bot_flows.md
14. docs/72_admin_doctor_owner_ui_contracts.md
15. docs/80_integrations_and_infra.md
16. docs/85_security_and_privacy.md
17. docs/90_pr_plan.md
18. docs/95_testing_and_launch.md
19. docs/report/PR_STACK_7A_REPORT.md
20. BOOKING_BASE_MANIFEST.md (not present)
21. booking-base-v1.md (not present)

## 3. Precedence Decisions
- Kept baseline-only schema discipline by editing bootstrap DDL in-place (no migration chain).
- Preserved UTC storage semantics in domain/services/repository (presentation-only timezone localization).
- Used explicit current-row semantics for summary instead of implicit "latest row wins" ordering.
- Maintained doctor visibility guardrails (booking-linked doctor access remains unchanged).

## 4. Chosen History Strategy
- Diagnosis and treatment plans now use **append-only version history with explicit current marker**.
- Setting a new current diagnosis/plan supersedes prior current row:
  - prior current row is retained, marked `is_current=false`, `status='superseded'`, and timestamped.
  - new row is inserted with incremented `version_no`, `is_current=true`, and supersedes pointer.
- Summary resolution now uses explicit current selectors, not max timestamp inference.

## 5. Diagnosis Versioning Notes
- Added diagnosis fields:
  - `version_no`
  - `is_current`
  - `supersedes_diagnosis_id`
  - `superseded_at`
- Added unique partial index `uq_diagnoses_current_primary_per_chart` to enforce one current primary diagnosis per chart.
- `set_diagnosis()` now supersedes previous current primary diagnosis before inserting the next version.

## 6. Treatment Plan Versioning Notes
- Added treatment plan fields:
  - `version_no`
  - `is_current`
  - `supersedes_treatment_plan_id`
  - `superseded_at`
- Added unique partial index `uq_treatment_plans_current_per_chart` to enforce one current treatment plan per chart.
- `set_treatment_plan()` now supersedes prior current plan and appends a new current version.

## 7. Chart-Wide Note Aggregation Strategy
- Added repository method for chart-wide note listing via encounter join.
- Chart summary now computes:
  - `note_count` from all notes across all chart encounters.
  - `latest_note` from full chart note history (not just open encounter path).
- Summary timestamps now include chart-wide latest note signals.

## 8. Timezone Presentation Strategy
- Introduced centralized `DoctorTimezoneFormatter` utility.
- Resolution order:
  1. branch timezone (if booking has branch and branch timezone exists)
  2. clinic timezone
  3. app default timezone (`AppConfig.default_timezone`)
- Applied local-time labels to touched doctor-facing surfaces:
  - queue time labels
  - booking detail labels
  - patient upcoming booking snippet
  - chart summary updated-at label
- Storage remains UTC; no persistence conversion added.

## 9. Files Added
- `app/application/timezone.py`
- `docs/report/PR_STACK_7A1_REPORT.md`

## 10. Files Modified
- `app/domain/clinical/models.py`
- `app/application/clinical/services.py`
- `app/infrastructure/db/clinical_repository.py`
- `app/infrastructure/db/bootstrap.py`
- `app/application/doctor/operations.py`
- `app/config/settings.py`
- `tests/test_clinical_stack7a.py`
- `tests/test_db_bootstrap.py`

## 11. Commands Run
- `sed -n '1,220p' README.md`
- `sed -n '1,260p' docs/18_development_rules_and_baseline.md`
- `sed -n '1,260p' docs/10_architecture.md`
- `sed -n '1,260p' docs/30_data_model.md`
- `sed -n '1,260p' docs/20_domain_model.md`
- `sed -n '1,260p' docs/15_ui_ux_and_product_rules.md`
- `sed -n '1,260p' docs/17_localization_and_i18n.md`
- `for f in ...; sed -n '1,40p' "$f"; done` for the remaining required docs
- `pytest -q tests/test_clinical_stack7a.py tests/test_db_bootstrap.py`

## 12. Test Results
- `11 passed in 1.95s`
- Coverage focus in this stack:
  - diagnosis versioning and current-row supersession
  - treatment-plan versioning and current-row supersession
  - chart-wide note aggregation (including closed encounter note history)
  - timezone presentation fallback order (branch -> clinic -> app default)
  - doctor access regression guard remains denied for unrelated patients

## 13. Known Limitations / Explicit Non-Goals
- No 043 export generation or document rendering added.
- No full clinical workflow expansion beyond targeted hardening.
- No patient-facing chart access introduced.
- No broader admin/owner clinical analytics introduced.

## 14. Deviations From Docs (if any)
- None identified for Stack 7A1 scope.

## 15. Readiness Assessment for PR Stack 8A
- Chart summary semantics are now explicit and safer for future export/mapping layers.
- History/version structure is now suitable for richer chart UX evolution.
- Doctor-facing time labels now avoid raw UTC leakage and are context-aware.
- Stack is ready for targeted Stack 8A work without carrying forward ambiguous current-row semantics.
