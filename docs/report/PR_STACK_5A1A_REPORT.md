# PR Stack 5A1A Report — Search Projection Backbone Integrity

## 1. Objective
Complete the missing canonical search backbone under Stack 5A1 by making Postgres `search.*_projection` tables real in baseline bootstrap, rebuilding projections from canonical truth, aligning Postgres search SQL to real schema, making Meili full reindex stale-safe, and fixing admin/doctor search guard + i18n gaps.

## 2. Docs Read
1. `README.md`
2. `docs/18_development_rules_and_baseline.md`
3. `docs/10_architecture.md`
4. `docs/12_repo_structure_and_code_map.md`
5. `docs/40_search_model.md`
6. `docs/30_data_model.md`
7. `docs/20_domain_model.md`
8. `docs/15_ui_ux_and_product_rules.md`
9. `docs/17_localization_and_i18n.md`
10. `docs/22_access_and_identity_model.md`
11. `docs/23_policy_and_configuration_model.md`
12. `docs/70_bot_flows.md`
13. `docs/72_admin_doctor_owner_ui_contracts.md`
14. `docs/80_integrations_and_infra.md`
15. `docs/85_security_and_privacy.md`
16. `docs/90_pr_plan.md`
17. `docs/95_testing_and_launch.md`
18. `docs/report/PR_STACK_5A1_REPORT.md`

## 3. Scope Implemented
- Added canonical `search` schema and `search.patient_search_projection`, `search.doctor_search_projection`, `search.service_search_projection` to baseline bootstrap.
- Added projection rebuild service that truncates and rebuilds search projections from canonical tables:
  - patients from `core_patient.*`
  - doctors from `core_reference.doctors`
  - services from `core_reference.services` + locale catalogs
- Added runnable rebuild command: `scripts/rebuild_search_projections.py`.
- Aligned `PostgresSearchBackend` SQL with concrete projection columns and clinic scoping.
- Updated Meili reindex to clear each index first, then add batch docs (stale-safe full rebuild).
- Fixed admin/doctor search role-guard behavior and localized usage/result/no-match text.
- Added compact patient quick result formatting (display name, number, phone hint, flags summary, status).
- Added/expanded tests for bootstrap, rebuild, backend behavior, reindex stale handling, and UI guards/i18n.

## 4. Search Projection Schema Summary
Implemented projection tables (baseline bootstrap, no migration clutter):
- `search.patient_search_projection`
  - includes `patient_id`, `clinic_id`, `patient_number`, name variants (`display_name`, `full_name_legal`, `first_name`, `last_name`, `middle_name`), normalized/token/translit fields, `external_id_normalized`, `primary_phone_normalized`, `preferred_language`, `primary_photo_ref`, `active_flags_summary`, `status`, `updated_at`.
- `search.doctor_search_projection`
  - includes `doctor_id`, `clinic_id`, `branch_id`, `display_name`, normalized/token/translit fields, `specialty_code`, `specialty_label`, `public_booking_enabled`, `status`, `updated_at`.
- `search.service_search_projection`
  - includes `service_id`, `clinic_id`, `code`, `title_key`, `localized_search_text_ru`, `localized_search_text_en`, `specialty_required`, `status`, `updated_at`.

Indexing added for clinic + exact/strict lookups (patient number, phone, external id, name normalized; doctor/service clinic indexes).

## 5. Projection Rebuild Strategy
- Implemented in `SearchProjectionRebuilder` (`app/projections/search/rebuilder.py`).
- Strategy is explicit truncate + full rebuild from canonical truth.
- Patient enrichment includes:
  - normalized name + tokens
  - translit tokens (Cyrillic→Latin map)
  - primary phone normalized
  - primary external ID normalized
  - primary photo ref
  - compact active flags summary (flag types only)
- Doctor projection derives normalized/translit name and specialty fields.
- Service projection resolves localized RU/EN search text via locale catalogs by `title_key`.

## 6. Postgres Backend Alignment Notes
- Removed schema ambiguity by querying only real projection columns.
- Strict patient path supports:
  - exact patient number
  - exact normalized phone
  - exact external ID
  - exact normalized name
- Fallback supports normalized/token/translit matching.
- All queries remain clinic-scoped (`WHERE clinic_id = :clinic_id`).

## 7. Meili Full Reindex Strategy
Chosen strategy: **clear index documents first, then add all canonical projection docs in batches**.

Why: avoids stale document retention after full rebuild while preserving batch writes.

Implementation changes:
- `MeiliClient` now has `clear_documents` + `add_documents`.
- `MeiliReindexService` calls `clear_documents()` before batch insert for each index.

## 8. UI Guard / i18n Fixes
- Admin `/search_patient` now exits immediately after failed guard (no downstream search execution).
- Doctor `/search_doctor` and `/search_service` now use the same role guard discipline as `/search_patient`.
- Search usage/help/no-match and section headers moved to i18n keys in RU/EN.
- Search handlers now produce localized, compact output.

## 9. Files Added
- `app/projections/search/rebuilder.py`
- `scripts/rebuild_search_projections.py`
- `tests/test_search_backbone_stack5a1a.py`
- `tests/test_search_ui_stack5a1a.py`
- `docs/report/PR_STACK_5A1A_REPORT.md`

## 10. Files Modified
- `app/infrastructure/db/bootstrap.py`
- `app/projections/search/__init__.py`
- `app/application/search/models.py`
- `app/infrastructure/search/projection_reader.py`
- `app/infrastructure/search/postgres_backend.py`
- `app/infrastructure/search/meili_documents.py`
- `app/infrastructure/search/meili_backend.py`
- `app/infrastructure/search/meili_client.py`
- `app/application/search/reindex.py`
- `app/interfaces/bots/search_handlers.py`
- `app/interfaces/bots/admin/router.py`
- `app/interfaces/bots/doctor/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_db_bootstrap.py`
- `tests/test_search_meili_stack5a1.py`

## 11. Commands Run
- `pytest -q tests/test_db_bootstrap.py tests/test_search_meili_stack5a1.py tests/test_search_backbone_stack5a1a.py tests/test_search_ui_stack5a1a.py`

## 12. Test Results
- 14 passed, 0 failed.

## 13. Remaining Known Limitations
- Transliteration is deterministic/basic and not language-model quality.
- Doctor `specialty_label` currently mirrors `specialty_code` until canonical specialty dictionary fields are introduced.
- Rebuild path is full refresh; targeted incremental projection hooks are not added in this PR.

## 14. Deviations From Docs (if any)
- None intentional relative to requested 5A1A scope.
- Voice retrieval remains explicitly out of scope in this PR.

## 15. Readiness Assessment for PR Stack 5B
- **Conditionally ready**: backbone is now concrete (baseline schema, rebuild path, aligned SQL, stale-safe Meili reindex, role-safe localized UI output, behavioral tests).
- 5B should build on this without re-litigating canonical projection ownership.
