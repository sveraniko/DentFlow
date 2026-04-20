# PR 12A-4A Report: Doctor/Admin Generation Entry + Document Registry UX

## 1. Objective
Expose the already implemented 12A-1/12A-2/12A-3 document export pipeline to real doctor/admin runtime usage with bounded, role-safe generation entrypoints, visible generated-document registry interactions, open/download/regenerate actions, and human-readable statuses/failure messaging.

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
22. `docs/report/FULL_PROJECT_STATE_AUDIT.md`

## 3. Precedence Decisions
1. **Projection semantics preserved:** generated documents remain metadata/artifact records and are only listed/opened/regenerated as derived outputs.
2. **Real app seam enforced:** generation/regeneration routes call `DocumentExportApplicationService.generate_043_export` only.
3. **Role-safe bounded UX:** doctor/admin only; patient role remains non-generator.
4. **Explicit template-resolution behavior:** template failures surface as explicit user-facing template-availability error text.
5. **No 12A-4B overreach:** renderer/template realism remains unchanged.

## 4. Generation Entry Strategy
- Added doctor generation command from booking+patient context:
  - `/doc_generate <patient_id> <booking_id> [locale]`
  - verifies doctor role, clinic scope, doctor-booking ownership, and patient visibility.
- Added admin generation command from patient/chart context:
  - `/admin_doc_generate <patient_id> <chart_id> [locale]`
  - scoped to actor clinic.
- Both paths call the same app seam (`generate_043_export`) and propagate template-resolution failure separately.

## 5. Registry UI Strategy
- Added bounded doctor registry listing:
  - `/doc_registry_booking <booking_id>`
- Added bounded admin registry listing:
  - `/admin_doc_registry_patient <patient_id>`
- Added detail/open cards:
  - doctor: `/doc_open <generated_document_id>`
  - admin: `/admin_doc_open <generated_document_id>`
- Status rendering uses localized friendly labels (`pending`, `generating`, `generated`, `failed`) and compact failure hinting.

## 6. Retry/Regenerate Strategy
- Added regenerate commands:
  - doctor: `/doc_regenerate <generated_document_id>`
  - admin: `/admin_doc_regenerate <generated_document_id>`
- Regeneration creates a new generated-document record via app seam using original context where safe (`patient_id`, `chart_id`, optional booking/encounter).
- If context is incomplete (e.g., no `chart_id`), regenerate is explicitly blocked with clear bounded message.

## 7. Human-Readable Status/Failure Notes
- Added i18n keys for generation statuses and errors in `en`/`ru`.
- Added explicit message for template-resolution failure.
- Added explicit message for generated-with-missing-artifact inconsistency.
- Avoided exposing exception internals/stack traces in user text.

## 8. Files Added
- `tests/test_document_registry_ui_12a4a.py`
- `docs/report/PR_12A4A_REPORT.md`

## 9. Files Modified
- `app/interfaces/bots/doctor/router.py`
- `app/interfaces/bots/admin/router.py`
- `app/bootstrap/runtime.py`
- `locales/en.json`
- `locales/ru.json`

## 10. Commands Run
- `pwd && rg --files -g 'AGENTS.md'`
- `find . -maxdepth 2 -type f | sed 's#^./##' | head -n 200`
- `rg -n "DocumentExport|export 043|generated document|document registry|artifact" app tests docs | head -n 200`
- `sed -n '1,420p' app/application/export/assembly.py`
- `sed -n '1,320p' app/application/export/services.py`
- `sed -n '1,280p' app/interfaces/bots/doctor/router.py`
- `sed -n '1,260p' app/interfaces/bots/admin/router.py`
- `sed -n '1,260p' app/bootstrap/runtime.py`
- `pytest -q tests/test_document_registry_ui_12a4a.py tests/test_export_043_generation_12a3.py tests/test_export_043_assembly_12a2.py tests/test_document_export_foundation_12a1.py`
- `python -m compileall app/interfaces/bots/admin/router.py app/interfaces/bots/doctor/router.py tests/test_document_registry_ui_12a4a.py`

## 11. Test Results
- `pytest -q tests/test_document_registry_ui_12a4a.py tests/test_export_043_generation_12a3.py tests/test_export_043_assembly_12a2.py tests/test_document_export_foundation_12a1.py` -> **17 passed**.
- `python -m compileall app/interfaces/bots/admin/router.py app/interfaces/bots/doctor/router.py tests/test_document_registry_ui_12a4a.py` -> completed successfully.

## 12. Known Limitations / Explicit Non-Goals
- No patient document portal.
- No giant document center.
- No template realism redesign (12A-4B scope).
- No new document families beyond current 043 line.
- Download path currently returns bounded artifact reference text (not a full binary transport UX redesign).

## 13. Deviations From Docs (if any)
- No intentional architectural deviations.
- Admin generation entry for this PR is chart-context command driven (bounded) rather than a broader panel workflow.

## 14. Readiness Assessment for 12A-4B
Ready for 12A-4B:
- doctor/admin can now trigger real generation through app seam;
- generated document registry is visible and queryable in role surfaces;
- open/download/regenerate actions exist in bounded form;
- statuses/failure messaging are localized and human-readable;
- tests cover role gating, seam usage, registry display, artifact access, and template-failure surfacing.
