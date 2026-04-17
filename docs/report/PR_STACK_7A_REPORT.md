# PR Stack 7A Report — Clinical Chart Baseline

## 1. Objective
Implement a practical baseline clinical chart layer (chart anchor + encounter baseline + compact note/diagnosis/treatment/imaging/odontogram handling) for doctor operations, while preserving strict doctor-safe patient visibility and avoiding full EMR scope.

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
19. BOOKING_BASE_MANIFEST.md (not present)
20. booking-base-v1.md (not present)
21. docs/report/PR_STACK_6A_REPORT.md
22. docs/report/PR_STACK_6A1_REPORT.md

## 3. Precedence Decisions
- Kept chart truth in `clinical.*` tables; patient truth remains in `core_patient.*`; booking truth remains in `booking.*`.
- Reused Stack 6A1 doctor visibility model (booking-linked patient visibility) for chart-open and all chart-mutating doctor flows.
- Followed baseline-bootstrap discipline: clinical schema added into canonical bootstrap DDL; no migration clutter.
- Aligned data model to future 043 mapping readiness without implementing export generation.

## 4. Clinical Schema Summary
Added canonical Stack 7A clinical tables into baseline bootstrap:
- `clinical.patient_charts`
- `clinical.presenting_complaints`
- `clinical.clinical_encounters`
- `clinical.encounter_notes`
- `clinical.diagnoses`
- `clinical.treatment_plans`
- `clinical.imaging_references`
- `clinical.odontogram_snapshots`

Added practical constraints/indexes including:
- unique active chart index per `(patient_id, clinic_id)`
- encounter/note/diagnosis/plan/imaging/snapshot time-oriented indexes
- imaging ref check ensuring `media_asset_id OR external_url` is present

## 5. Chart/Encounter Model Summary
Implemented structured clinical baseline model in domain/application layers:
- chart anchor (`PatientChart`)
- minimal encounter (`ClinicalEncounter`, status open/closed)
- compact encounter notes
- diagnosis summary entries
- treatment plan baseline entries
- imaging references (media or URL)
- odontogram snapshot JSON baseline

## 6. Doctor Chart Access Rule
Doctor chart operations use a strict visibility guard:
- doctor can open/update chart only when doctor has patient visibility by booking-link rule (`doctor_id` linked to patient via at least one booking)
- no arbitrary raw patient_id chart bypass
- doctor identity remains derived through canonical actor → staff → doctor mapping

Denied access returns safe localized doctor messages without disclosing hidden patient/chart existence.

## 7. Encounter Flow Strategy
Open/create rule:
- from patient context: open active chart then open/get existing open encounter for `(chart_id, doctor_id[, booking_id])`
- from booking context: booking must belong to same doctor and patient; then reuse existing open encounter or create one
- avoids accidental duplicate encounter spam for same visit context.

Supported baseline encounter actions:
- open/get encounter
- add compact note
- update diagnosis summary
- update treatment plan summary
- attach imaging ref
- save odontogram snapshot

## 8. Imaging / Odontogram Baseline Strategy
Imaging references:
- support external URL path (`http/https`) for CT/large imaging refs
- support `media_asset_id` path for media registry integration
- reject invalid imaging input safely

Odontogram:
- stored as structured JSON snapshot per save point
- latest snapshot retrieval supported in repository/service layer
- no rich graphical editor added in this stack

## 9. Files Added
- `app/domain/clinical/models.py`
- `app/application/clinical/services.py`
- `app/infrastructure/db/clinical_repository.py`
- `tests/test_clinical_stack7a.py`
- `docs/report/PR_STACK_7A_REPORT.md`

## 10. Files Modified
- `app/domain/clinical/__init__.py`
- `app/application/clinical/__init__.py`
- `app/application/doctor/operations.py`
- `app/application/doctor/__init__.py`
- `app/interfaces/bots/doctor/router.py`
- `app/bootstrap/runtime.py`
- `app/infrastructure/db/bootstrap.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_db_bootstrap.py`

## 11. Commands Run
- `pwd; rg --files -g 'AGENTS.md'`
- `find .. -name AGENTS.md -maxdepth 4 2>/dev/null`
- doc/code discovery commands (`ls`, `find`, `rg`, `sed`)
- `pytest -q tests/test_db_bootstrap.py tests/test_doctor_operational_stack6a.py tests/test_clinical_stack7a.py`

## 12. Test Results
- `18 passed` on targeted stack tests:
  - bootstrap/schema assertions including Stack 7A tables
  - existing doctor operational safety tests (Stack 6A/6A1 behavior retained)
  - new clinical baseline flow tests (chart/encounter/diagnosis/treatment/imaging/odontogram + visibility denial)

## 13. Known Limitations / Explicit Non-Goals
- No full EMR/EHR questionnaire or specialty-specific giant forms.
- No document export engine / 043 renderer in this stack.
- No patient-facing chart access.
- No full admin chart workflows; doctor-first baseline only.
- No PACS/viewer implementation; imaging references only.
- Encounter state model intentionally minimal (`open` / `closed`).

## 14. Deviations From Docs (if any)
- None intentional.

## 15. Readiness Assessment for next stack
Stack 7A baseline is in place and coherent for progression:
- canonical `clinical` schema present
- DB-backed clinical repository/service pattern established
- doctor-safe chart access preserved
- compact doctor chart/encounter commands available
- RU/EN localized chart surface strings added

Ready for next-stack refinement (richer chart UX shaping, deeper summaries, future export mapping layer), without scope-creeping into full medical ERP.
