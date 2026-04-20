# PR 12A-1 Report: Document Registry + Template Foundation

## 1. Objective
Implement the document/export foundation layer for DentFlow as a bounded registry/tracking subsystem, including:
- document template registry,
- generated document registry,
- explicit template resolution,
- generation status model,
- artifact binding metadata,
- and tests.

This PR intentionally does **not** implement full 043 data assembly or rendering.

## 2. Docs Read
Read for this implementation (in the requested precedence sequence and adjacent supporting docs):
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
19. `docs/report/PR_STACK_7A_REPORT.md`
20. `docs/report/PR_STACK_7A1_REPORT.md`
21. `docs/report/PR_STACK_10A_REPORT.md`
22. `docs/report/PR_STACK_11A_REPORT.md`
23. `docs/report/PR_STACK_11A1_REPORT.md`
24. `docs/report/FULL_PROJECT_STATE_AUDIT.md`

## 3. Precedence Decisions
1. **Projection-not-truth rule enforced**: generated document records were modeled as metadata/artifact tracking only; no patient/booking/clinical canonical fields were duplicated into document tables.
2. **Baseline discipline enforced**: schema was added directly in `app/infrastructure/db/bootstrap.py`; no migration-chain clutter was introduced.
3. **Deterministic template resolution made explicit**: clinic-specific active templates are preferred, then default active templates, with deterministic version ordering.
4. **Bounded generation status model chosen**: only `pending`, `generating`, `generated`, `failed` were implemented in this foundation PR.

## 4. Template Registry Schema Summary
Added `media_docs.document_templates` with:
- `document_template_id` (PK)
- `clinic_id` nullable (clinic override vs default)
- `template_type`
- `template_version` (positive int)
- `locale`
- `render_engine`
- `template_source_ref`
- `is_active`
- `created_at`
- `updated_at`

Constraints/indexes:
- unique `(clinic_id, template_type, locale, template_version)`
- resolution index by type/locale/clinic/active/version/update time.

## 5. Generated Document Registry Schema Summary
Added `media_docs.generated_documents` with:
- `generated_document_id` (PK)
- `clinic_id`
- `patient_id`
- `chart_id` nullable
- `encounter_id` nullable
- `booking_id` nullable
- `document_template_id`
- `document_type`
- `generation_status`
- `generated_file_asset_id` nullable
- `editable_source_asset_id` nullable
- `created_by_actor_id` nullable
- `created_at`
- `updated_at`
- `generation_error_text` nullable

Constraints/indexes:
- status check (`pending`, `generating`, `generated`, `failed`)
- generated status requires `generated_file_asset_id`
- context indexes for patient/chart/booking and clinic+status.

## 6. Template Resolution Strategy
Implemented in `DocumentTemplateRegistryService.resolve_active_template`:
1. resolve active clinic-specific templates for `(template_type, locale, clinic_id)`
2. if none matched, resolve active default templates `(template_type, locale, clinic_id=NULL)`
3. deterministic selection:
   - explicit `template_version` if requested
   - otherwise highest version (with stable tie-breakers)
4. if still missing, raise explicit `TemplateResolutionError`.

## 7. Document Status Model
Implemented bounded statuses:
- `pending`
- `generating`
- `generated`
- `failed`

Explicit transitions:
- `pending -> generating|failed`
- `generating -> generated|failed`
- terminal: `generated`, `failed`

Failure path preserves `generation_error_text`.
Success path requires and binds `generated_file_asset_id`.

## 8. Artifact Binding Strategy
Added `media_docs.media_assets` as the artifact metadata table and bound generated documents via FKs:
- `generated_file_asset_id -> media_docs.media_assets.media_asset_id`
- `editable_source_asset_id -> media_docs.media_assets.media_asset_id`

No raw file/blob columns were added to `generated_documents`; only metadata references are tracked.

## 9. Files Added
- `app/domain/media_docs/models.py`
- `app/application/export/services.py`
- `app/infrastructure/db/document_repository.py`
- `tests/test_document_export_foundation_12a1.py`
- `docs/report/PR_12A1_REPORT.md`

## 10. Files Modified
- `app/domain/media_docs/__init__.py`
- `app/application/export/__init__.py`
- `app/infrastructure/db/bootstrap.py`
- `tests/test_db_bootstrap.py`

## 11. Commands Run
- `rg --files -g 'AGENTS.md'`
- `find .. -name AGENTS.md -print`
- `rg --files | head -n 200`
- `rg -n "media_docs|document_template|generated_document|asset_id|media" app scripts docs/30_data_model.md docs/65_document_templates_and_043_mapping.md docs/20_domain_model.md docs/25_state_machines.md`
- `pytest -q tests/test_document_export_foundation_12a1.py tests/test_db_bootstrap.py`
- `python -m compileall app tests/test_document_export_foundation_12a1.py`

## 12. Test Results
- `pytest -q tests/test_document_export_foundation_12a1.py tests/test_db_bootstrap.py` -> **16 passed**
- `python -m compileall app tests/test_document_export_foundation_12a1.py` -> completed successfully

## 13. Known Limitations / Explicit Non-Goals
Not implemented in this PR:
- full 043 data assembly
- renderer implementation (PDF/HTML/DOCX generation)
- doctor/admin generation UI
- patient document portal
- e-signature workflows
- broad template CMS/editor
- invoice/order doc wave
- AI document generation

## 14. Deviations From Docs (if any)
No intentional deviations from the specified docs for this foundation scope.

## 15. Readiness Assessment for 12A-2
This branch is ready for 12A-2 pipeline work because it now has:
- deterministic template lookup,
- generated document lifecycle/status tracking,
- artifact reference slots,
- context-queryable generated document registry,
- and tests guarding foundation behavior.

12A-2 can now plug in assembler/renderer steps by:
1. resolving a template,
2. creating a pending/generated-document record,
3. transitioning `pending -> generating -> generated|failed`,
4. binding produced media asset IDs.
