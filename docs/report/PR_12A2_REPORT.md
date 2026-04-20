# PR 12A-2 Report: Structured 043 Data Assembly

## 1. Objective
Implement a deterministic, structured 043-style export payload assembly layer on top of the 12A-1 template/document registry foundation, while keeping runtime truth canonical and projection-only.

## 2. Docs Read
1. `README.md`
2. `docs/18_development_rules_and_baseline.md`
3. `docs/10_architecture.md`
4. `docs/12_repo_structure_and_code_map.md`
5. `docs/30_data_model.md`
6. `docs/65_document_templates_and_043_mapping.md`
7. `docs/20_domain_model.md`
8. `docs/25_state_machines.md`
9. `docs/15_ui_ux_and_product_rules.md`
10. `docs/17_localization_and_i18n.md`
11. `docs/22_access_and_identity_model.md`
12. `docs/23_policy_and_configuration_model.md`
13. `docs/70_bot_flows.md`
14. `docs/72_admin_doctor_owner_ui_contracts.md`
15. `docs/80_integrations_and_infra.md`
16. `docs/85_security_and_privacy.md`
17. `docs/90_pr_plan.md`
18. `docs/95_testing_and_launch.md`
19. `docs/report/PR_12A1_REPORT.md`
20. `docs/report/PR_STACK_7A_REPORT.md`
21. `docs/report/PR_STACK_7A1_REPORT.md`
22. `docs/report/FULL_PROJECT_STATE_AUDIT.md`

## 3. Precedence Decisions
1. 043 export stays a projection layer; no canonical patient/booking/clinical truth was copied into document tables.
2. Current diagnosis and current treatment plan were assembled via explicit current getters, not “latest row wins”.
3. Sparse charts produce explicit nullable sections + warnings instead of errors.
4. Default-template ambiguity was hardened at DB bootstrap level with partial unique indexes and active-version service checks.

## 4. Structured Payload Model Summary
Added explicit typed export DTOs under `app/application/export/models.py`:
- patient identity/contact section,
- booking context section,
- chart anchor/context section,
- diagnosis section,
- treatment plan section,
- complaint/notes summary,
- imaging summary,
- odontogram snapshot summary,
- export metadata and warnings,
- request/result envelopes for app-level orchestration.

## 5. Patient/Booking/Clinical Assembly Strategy
Implemented `Structured043ExportAssembler`:
- patient identity from patient registry + preferences + external IDs + primary contact hint,
- booking context from booking repository and human-readable labels via clinic reference service,
- local booking date/time labels via `DoctorTimezoneFormatter`,
- chart context from clinical chart + optional encounter,
- diagnosis/treatment from current-row clinical accessors,
- notes/imaging/odontogram summarized in bounded sections.

## 6. Current-Semantics Handling Notes
The assembler uses:
- `get_current_primary_diagnosis(chart_id=...)`
- `get_current_treatment_plan(chart_id=...)`
for diagnosis/plan export, explicitly respecting stack 7A/7A1 semantics.

## 7. Sparse-Data Handling Notes
Assembler now tolerates missing data and still returns payload:
- missing diagnosis,
- missing treatment plan,
- missing imaging,
- missing encounter,
- missing booking context.

Missing pieces are represented as nullable structured fields and warning flags (`current_diagnosis_missing`, etc.).

## 8. Template Ambiguity Fix Notes
Two bounded protections were added:
1. DB bootstrap now declares partial unique indexes for templates:
   - clinic-scoped uniqueness where `clinic_id IS NOT NULL`
   - default-scoped uniqueness where `clinic_id IS NULL`
2. Template registry service rejects duplicate active template version registration for the same scope/type/locale.

This resolves the PostgreSQL NULL-uniqueness ambiguity for default templates.

## 9. Application Seam Notes
Added real app-level seam via `DocumentExportApplicationService`:
1. resolve template,
2. create generated-document row,
3. transition to `generating`,
4. assemble structured 043 payload,
5. mark failed on assembly exception.

Runtime wiring now instantiates:
- template registry service,
- generated document registry service,
- structured 043 assembler,
- app-level export service.

## 10. Files Added
- `app/application/export/models.py`
- `app/application/export/assembly.py`
- `tests/test_export_043_assembly_12a2.py`
- `docs/report/PR_12A2_REPORT.md`

## 11. Files Modified
- `app/application/export/__init__.py`
- `app/application/export/services.py`
- `app/bootstrap/runtime.py`
- `app/infrastructure/db/bootstrap.py`
- `tests/test_db_bootstrap.py`

## 12. Commands Run
- `find .. -maxdepth 3 -name AGENTS.md`
- `rg -n "current diagnosis|current treatment|043|document template|generated document|default template|latest row" docs app tests`
- `pytest -q tests/test_export_043_assembly_12a2.py tests/test_document_export_foundation_12a1.py tests/test_db_bootstrap.py tests/test_runtime_wiring.py`
- `python -m compileall app tests/test_export_043_assembly_12a2.py`

## 13. Test Results
- `pytest -q tests/test_export_043_assembly_12a2.py tests/test_document_export_foundation_12a1.py tests/test_db_bootstrap.py tests/test_runtime_wiring.py` -> 22 passed
- `python -m compileall app tests/test_export_043_assembly_12a2.py` -> completed successfully

## 14. Known Limitations / Explicit Non-Goals
Not implemented in 12A-2:
- final renderer (PDF/HTML/DOCX output generation),
- doctor/admin generation UI actions,
- patient document portal,
- template CMS/editor,
- AI document generation.

`DocumentExportApplicationService` intentionally stops at structured payload assembly + generation lifecycle start/fail seam.

## 15. Readiness Assessment for 12A-3
Ready for 12A-3 rendering pipeline integration:
- typed 043 payload now exists,
- canonical current-semantics extraction is implemented,
- sparse-data behavior is stable,
- generated-document lifecycle seam is callable from runtime,
- template default uniqueness ambiguity is bounded and guarded.
