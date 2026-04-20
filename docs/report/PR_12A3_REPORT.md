# PR 12A-3 Report: Rendering Engine + File Artifact Generation

## 1. Objective
Implement the first real 043 export rendering pipeline that converts the structured 12A-2 payload into a generated artifact, tracks the artifact in `media_docs.media_assets`, binds it into `media_docs.generated_documents`, and completes generation lifecycle to `generated`/`failed`.

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
20. `docs/report/PR_12A2_REPORT.md`
21. `docs/report/FULL_PROJECT_STATE_AUDIT.md`

## 3. Precedence Decisions
1. Export remains projection-only: generated documents track artifact metadata and references, not canonical clinical truth copies.
2. Generation lifecycle is explicit and terminal: success must end in `generated`, failures in `failed` with preserved error text.
3. Rendering polish is applied at render stage (service/doctor/branch/contact humanization) while keeping structured assembly seam intact.

## 4. Rendering Path Chosen
**Chosen path:** `Structured 043 payload -> Plain text renderer -> local filesystem artifact`.

Rationale:
- deterministic and testable baseline;
- minimal implementation surface for first real end-to-end generation;
- keeps room for future HTML/PDF engine expansion without blocking artifact tracking.

## 5. Artifact Generation Strategy
Pipeline implemented in `DocumentExportApplicationService.generate_043_export`:
1. resolve active template;
2. create generated-document row (`pending`);
3. transition to `generating`;
4. assemble structured payload;
5. render final human-readable text artifact;
6. store artifact in local filesystem storage adapter;
7. create `media_docs.media_assets` record;
8. bind `generated_file_asset_id` and mark generated document `generated`.

If any step after row creation fails, generated document transitions to `failed` and `generation_error_text` is persisted.

## 6. Generated Document Status Completion Notes
- `generate_043_export` now marks success via `mark_generation_success(...generated_file_asset_id=...)`.
- failure paths (e.g., storage failures) call `mark_generation_failed(...error_text=...)`.
- this closes the previous 12A-2 seam that intentionally stopped at `generating`.

## 7. Human-Readable Output Rendering Notes
Renderer now ensures output readability for final artifact:
- service label localization/humanization (locale lookup, then fallback humanization);
- doctor/branch label humanization fallback;
- contact hint transformation from machine shape (`contact_type:value`) to readable text (`Phone: ...`, `Telegram: ...`).

This prevents raw title keys and machine-shaped contact hints from leaking into the final 043 output when render-time resolution is possible.

## 8. Files Added
- `app/application/export/rendering.py`
- `tests/test_export_043_generation_12a3.py`
- `docs/report/PR_12A3_REPORT.md`

## 9. Files Modified
- `app/domain/media_docs/models.py`
- `app/domain/media_docs/__init__.py`
- `app/application/export/services.py`
- `app/infrastructure/db/document_repository.py`
- `app/application/export/models.py`
- `app/application/export/assembly.py`
- `app/application/export/__init__.py`
- `app/bootstrap/runtime.py`

## 10. Commands Run
- `pwd && rg --files -g 'AGENTS.md'`
- `find . -maxdepth 3 -type f | head -n 200`
- `sed -n '1,220p' README.md`
- `sed -n '1,220p' docs/65_document_templates_and_043_mapping.md`
- `sed -n '1,240p' docs/report/PR_12A2_REPORT.md`
- `sed -n '1,240p' docs/report/PR_12A1_REPORT.md`
- `rg -n "class DocumentExportApplicationService|Structured043ExportAssembler|generated_file_asset_id|media_assets|043|render" app tests | head -n 200`
- `pytest -q tests/test_export_043_generation_12a3.py tests/test_export_043_assembly_12a2.py tests/test_document_export_foundation_12a1.py`
- `python -m compileall app/application/export tests/test_export_043_generation_12a3.py`

## 11. Test Results
- `pytest -q tests/test_export_043_generation_12a3.py tests/test_export_043_assembly_12a2.py tests/test_document_export_foundation_12a1.py` -> 13 passed.
- `python -m compileall app/application/export tests/test_export_043_generation_12a3.py` -> completed successfully.

## 12. Known Limitations / Explicit Non-Goals
Not implemented in this PR:
- doctor/admin document center UI;
- patient document portal UX;
- rich template CMS/editor;
- HTML->PDF / DOCX engines;
- e-signatures;
- invoice/order doc families;
- AI document generation.

Current rendering baseline intentionally uses plain text artifact generation for deterministic first real pipeline delivery.

## 13. Deviations From Docs (if any)
No intentional deviations for this scope. A bounded renderer baseline was chosen (plain text artifact) as an acceptable first real rendering path.

## 14. Readiness Assessment for 12A-4
Ready for 12A-4 evolution:
- real generated artifact creation exists;
- generated/failure completion semantics are enforced;
- artifact metadata is stored and bound explicitly;
- render-stage humanization is in place;
- tests cover success, failure, and readability constraints.

12A-4 can now extend engine richness (e.g., HTML/PDF variants and broader template capabilities) on top of a real tracked generation pipeline.
