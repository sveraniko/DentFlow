# PR 12A-4B Report: Template-Aware Rendering + Editable Artifact Path

## 1. Objective
Make the 043 export renderer truly template-aware so `template_source_ref` affects generated output, improve runtime robustness for locale/template resource lookup, and bind an honest editable source artifact where naturally supported by the plain-text rendering path.

## 2. Docs Read
1. `README.md`
2. `docs/18_development_rules_and_baseline.md`
3. `docs/10_architecture.md`
4. `docs/12_repo_structure_and_code_map.md`
5. `docs/30_data_model.md`
6. `docs/65_document_templates_and_043_mapping.md`
7. `docs/20_domain_model.md`
8. `docs/17_localization_and_i18n.md`
9. `docs/80_integrations_and_infra.md`
10. `docs/85_security_and_privacy.md`
11. `docs/90_pr_plan.md`
12. `docs/95_testing_and_launch.md`
13. `docs/report/PR_12A1_REPORT.md`
14. `docs/report/PR_12A2_REPORT.md`
15. `docs/report/PR_12A3_REPORT.md`
16. `docs/report/PR_12A4A_REPORT.md`
17. `docs/report/FULL_PROJECT_STATE_AUDIT.md`

## 3. Precedence Decisions
1. Keep renderer bounded and deterministic (no CMS), but make template selection semantically real at output level.
2. Preserve 12A-3 human-readable render guarantees while adding template-driven section structure.
3. Use file-system based template and locale resolution with robust fallback order to avoid CWD-only fragility.
4. Generate editable source artifact only because the selected text-template pipeline naturally supports it.

## 4. Template-Aware Rendering Strategy
- Introduced template file loading in `PlainText043Renderer` keyed by `template_source_ref`.
- Added concrete baseline templates:
  - default layout: `templates/exports/043/plain_text/v1`
  - clinic-specific variant layout: `templates/exports/043/plain_text/clinic_v1`
- Rendering now fills placeholder values into the resolved template text; different template files produce deterministic, observable output differences.

## 5. template_source_ref Usage Notes
- `template_source_ref` is no longer discarded in renderer.
- Supported source patterns:
  - `builtin://...` (resolved under export template base dir)
  - `file://...` absolute/expanded paths
  - plain relative/absolute paths
- Missing template sources now fail explicitly with `FileNotFoundError`.

## 6. Locale/Resource Robustness Notes
- Locale catalogs are now resolved via robust strategy:
  1. explicit renderer override path
  2. `DENTFLOW_LOCALES_DIR`
  3. `<cwd>/locales`
  4. repo-root `locales` resolved relative to module path
- Export template base dir similarly supports:
  1. explicit renderer override path
  2. `DENTFLOW_EXPORT_TEMPLATES_DIR`
  3. `<cwd>/templates/exports`
  4. repo-root `templates/exports` resolved relative to module path

## 7. Editable Artifact Notes
- Added `editable_source` support in renderer output contract.
- Plain-text renderer now emits a markdown editable source artifact (`text/markdown`, `.md`) containing:
  - template metadata
  - rendered preview block
  - manual completion notes
- Generation pipeline stores this editable source as a separate media asset (`generated_document_editable_source`) and binds `editable_source_asset_id` on generated document success.

## 8. Files Added
- `templates/exports/043/plain_text/v1`
- `templates/exports/043/plain_text/clinic_v1`
- `docs/report/PR_12A4B_REPORT.md`

## 9. Files Modified
- `app/application/export/rendering.py`
- `app/application/export/assembly.py`
- `tests/test_export_043_generation_12a3.py`

## 10. Commands Run
- `pwd; rg --files -g 'AGENTS.md'`
- `find .. -name AGENTS.md -print`
- `rg --files | head -n 200`
- `sed -n '1,220p' README.md`
- `sed -n '1,260p' docs/18_development_rules_and_baseline.md`
- `sed -n '1,260p' docs/10_architecture.md`
- `sed -n '1,260p' docs/65_document_templates_and_043_mapping.md`
- `sed -n '1,220p' docs/30_data_model.md`
- `sed -n '1,220p' docs/17_localization_and_i18n.md`
- `sed -n '1,260p' docs/report/PR_12A3_REPORT.md`
- `sed -n '1,320p' app/application/export/rendering.py`
- `sed -n '1,320p' app/application/export/services.py`
- `sed -n '1,320p' app/application/export/assembly.py`
- `sed -n '1,260p' app/application/export/models.py`
- `sed -n '1,520p' tests/test_export_043_generation_12a3.py`
- `rg -n "template_source_ref|plain_text_043|editable_source_asset_id|locales_dir|locales" app tests docs | head -n 200`
- `sed -n '220,310p' app/application/integration/google_calendar_projection.py`
- `sed -n '1,220p' app/application/export/__init__.py; sed -n '1,260p' app/bootstrap/runtime.py`
- `mkdir -p templates/exports/043/plain_text`
- `pytest -q tests/test_export_043_generation_12a3.py tests/test_export_043_assembly_12a2.py tests/test_document_export_foundation_12a1.py`
- `python -m compileall app/application/export tests/test_export_043_generation_12a3.py`

## 11. Test Results
- `pytest -q tests/test_export_043_generation_12a3.py tests/test_export_043_assembly_12a2.py tests/test_document_export_foundation_12a1.py` -> **15 passed**.
- `python -m compileall app/application/export tests/test_export_043_generation_12a3.py` -> completed successfully.

## 12. Known Limitations / Explicit Non-Goals
- No template CMS/editor introduced.
- No HTML->PDF or DOCX engine added.
- No new document families introduced.
- No e-signature/patient-portal scope.
- Template system remains file-based and bounded by current plain-text pipeline.

## 13. Final Readiness Assessment for the 12A line
12A-4B objective is met:
- template choice now affects deterministic output;
- `template_source_ref` is actively used in render path;
- locale/template resource path resolution is runtime-robust;
- editable source artifact is generated and bound honestly for this render pipeline;
- tests demonstrate template layer is no longer decorative while preserving human-readable output.
