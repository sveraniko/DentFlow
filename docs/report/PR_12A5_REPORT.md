# PR 12A-5 Report: Hardening + Mapping Polish

## 1. Objective
Finish the 12A export line with a bounded hardening and mapping-polish pass for 043 export: improve payload-to-render mapping quality, sparse-data behavior, human readability, deterministic template fallback behavior, and generation/open/regenerate/failure coherence without expanding scope into new document families or workflow systems.

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
21. `docs/report/PR_12A3_REPORT.md`
22. `docs/report/PR_12A4A_REPORT.md`
23. `docs/report/PR_12A4B_REPORT.md`
24. `docs/report/FULL_PROJECT_STATE_AUDIT.md`

## 3. Precedence Decisions
1. Kept export as projection (no canonical truth moved into document tables).
2. Prioritized mapping and readability fixes inside existing assembler/renderer/template seams.
3. Added deterministic conflict failure for ambiguous active template rows rather than silent best-effort selection.
4. Kept editable artifact support bounded to current plain-text pipeline and clarified its role.

## 4. Mapping Polish Summary
- Adjusted booking mapping behavior so unresolved doctor/service/branch references do not leak raw IDs into output labels.
- Added explicit warnings for unresolved booking references (`booking_doctor_unresolved`, `booking_service_unresolved`, `booking_branch_unresolved`) so missing reference truth is visible but non-crashing.
- Preserved existing structural section model while improving mapping quality for document-facing text values.

## 5. Sparse-Data Handling Notes
- Added explicit warning for missing patient contact (`patient_contact_missing`).
- Renderer now emits clearer sparse defaults for diagnosis, treatment plan, notes, imaging, and odontogram instead of bare machine-shaped placeholders.
- Warnings are humanized in rendered output instead of showing raw warning keys.

## 6. Template Fallback Notes
- `DocumentTemplateRegistryService` now raises `TemplateResolutionError` when template resolution is ambiguous (same highest active version in scope or duplicate matches for explicit version).
- Fallback order remains clinic-specific first, then default template scope, but now deterministic with explicit failure on unresolved conflicts.

## 7. Human-Readable Output Notes
- Replaced output of raw warning keys with human-readable warning messages.
- Rendered booking reference text as human context (`Linked scheduled booking` / `No linked booking`) instead of exposing raw booking IDs in document body.
- Improved fallback labels and placeholders to reduce machine-like export text.

## 8. Lifecycle/Open/Regenerate Notes
- Existing generation/open/regenerate routes were kept bounded.
- This pass focused on improving generated content quality and template resolution determinism so failure/open behavior communicates cleaner causes (especially template ambiguity/fallback failures).
- Editable source remains stored as a separate artifact and not mixed with generated final export artifact.

## 9. Files Added
- `docs/report/PR_12A5_REPORT.md`

## 10. Files Modified
- `app/application/export/assembly.py`
- `app/application/export/rendering.py`
- `app/application/export/services.py`
- `templates/exports/043/plain_text/v1`
- `templates/exports/043/plain_text/clinic_v1`
- `tests/test_export_043_assembly_12a2.py`
- `tests/test_export_043_generation_12a3.py`

## 11. Commands Run
- `pwd && rg --files -g 'AGENTS.md'`
- `rg --files | head -n 200`
- `rg --files docs | sort`
- `sed -n '1,220p' README.md`
- `sed -n '1,220p' docs/18_development_rules_and_baseline.md`
- `sed -n '1,260p' docs/65_document_templates_and_043_mapping.md`
- `sed -n '1,240p' tests/test_export_043_generation_12a3.py`
- `sed -n '1,260p' tests/test_document_registry_ui_12a4a.py`
- `sed -n '1,260p' docs/report/PR_12A4B_REPORT.md`
- `sed -n '1,320p' app/application/export/assembly.py`
- `sed -n '1,380p' app/application/export/rendering.py`
- `sed -n '1,420p' app/application/export/services.py`
- `sed -n '1,340p' app/application/export/models.py`
- `sed -n '1,240p' templates/exports/043/plain_text/v1`
- `sed -n '1,260p' templates/exports/043/plain_text/clinic_v1`
- `sed -n '1,320p' tests/test_export_043_assembly_12a2.py`
- `sed -n '320,620p' tests/test_export_043_assembly_12a2.py`
- `pytest -q tests/test_export_043_assembly_12a2.py tests/test_export_043_generation_12a3.py tests/test_document_registry_ui_12a4a.py`
- `python -m compileall app/application/export tests/test_export_043_assembly_12a2.py tests/test_export_043_generation_12a3.py`

## 12. Test Results
- `pytest -q tests/test_export_043_assembly_12a2.py tests/test_export_043_generation_12a3.py tests/test_document_registry_ui_12a4a.py` -> **16 passed**.
- `python -m compileall app/application/export tests/test_export_043_assembly_12a2.py tests/test_export_043_generation_12a3.py` -> completed successfully.

## 13. Remaining Known Limitations
- No new export engines (PDF/DOCX templating) added in this PR.
- No portal or e-signature behavior added.
- Warning localization is currently renderer-internal English text; full i18n warning dictionaries are not introduced in this bounded pass.
- Open/download still exposes storage references directly in bot text response (unchanged behavior from prior line).

## 14. Final Readiness Assessment for the 12A line
The 12A line is now materially closer to closure quality:
- mapping determinism is stronger,
- sparse-data rendering is cleaner,
- template fallback conflict handling is safer,
- output is less machine-shaped,
- and edge-case tests are stronger.

Not perfect, but complete enough to close the current 12A convergence scope and move to the next major block without carrying obvious quality debt in 043 generation.
