# PR Stack 5A1 Report — Meilisearch Adapter + Hybrid Query Path

## 1. Objective
Implement a Meilisearch-backed retrieval layer on top of canonical Postgres search projections, with strict-first patient search and Meili-primary doctor/service search plus explicit fallback.

## 2. Docs Read
- README.md
- docs/18_development_rules_and_baseline.md
- docs/10_architecture.md
- docs/12_repo_structure_and_code_map.md
- docs/40_search_model.md
- docs/30_data_model.md
- docs/85_security_and_privacy.md

## 3. Precedence Decisions
- Search truth remains in Postgres projection tables under `search.*_search_projection`.
- Meilisearch is an acceleration/query adapter only.
- Patient path is strict Postgres first, Meili suggestions second.

## 4. Meilisearch Integration Summary
- Added structured Meili config fields in `SearchConfig`.
- Added `HttpMeiliClient` adapter with index settings update, document replace, and query.
- Added `MeiliSearchBackend` implementing typed patient/doctor/service queries.

## 5. Index Schema / Settings Summary
- Patient index: searchable name/token/translit/patient_number/phone; filterable by clinic/status; displayed only minimized projection fields.
- Doctor index: searchable by name/specialty tokens; filterable clinic/branch/public-booking/status.
- Service index: searchable RU/EN text fields, code/title key; filterable clinic/specialty_required/status.

## 6. Projection-to-Document Mapping Strategy
- Explicit mappers from projection row dataclasses to Meili documents:
  - patient projection -> `MeiliPatientDocument`
  - doctor projection -> `MeiliDoctorDocument`
  - service projection -> `MeiliServiceDocument`
- No direct mapping from core truth tables.

## 7. Hybrid Patient Search Strategy
- Strict pass via Postgres (`patient_number`, normalized phone, external id, exact normalized name).
- Meili fuzzy suggestions requested second.
- Merge strategy:
  - strict rows always first;
  - Meili only additive;
  - duplicate `patient_id` removed from suggestion section.

## 8. Doctor/Service Fallback Strategy
- Attempt Meili first.
- On Meili failure/unavailability: log and fallback to Postgres projection search backend.

## 9. Reindex / Sync Strategy
- Added full reindex service for patients/doctors/services from projection tables.
- Added `scripts/reindex_meili.py` command for `all|patients|doctors|services`.
- Added batch-based replace with configurable batch size.

## 10. Files Added
- app/application/search/models.py
- app/application/search/backends.py
- app/application/search/service.py
- app/application/search/reindex.py
- app/infrastructure/search/meili_client.py
- app/infrastructure/search/meili_backend.py
- app/infrastructure/search/meili_documents.py
- app/infrastructure/search/postgres_backend.py
- app/infrastructure/search/projection_reader.py
- app/interfaces/bots/search_handlers.py
- scripts/reindex_meili.py
- docs/report/PR_STACK_5A1_REPORT.md
- tests/test_search_meili_stack5a1.py

## 11. Files Modified
- app/config/settings.py
- app/bootstrap/runtime.py
- app/interfaces/bots/admin/router.py
- app/interfaces/bots/doctor/router.py
- .env.example

## 12. Commands Run
- `pytest tests/test_search_meili_stack5a1.py`
- `pytest`

## 13. Test Results
- Added targeted unit tests for mappings, hybrid behavior, fallback, reindex wiring, and search handler behavior.

## 14. Known Limitations / Explicit Non-Goals
- No voice search or STT.
- No AI/semantic retrieval.
- No owner analytics search.
- No event-driven incremental sync in this stack.
- Runtime bot strings for new search commands are currently compact/plain.

## 15. Deviations From Docs (if any)
- None intentional. If projection table schemas differ from assumptions (`external_id_normalized`, `name_normalized`, token fields), SQL may require alignment patch in next stack.

## 16. Readiness Assessment for PR Stack 5B
- Ready as a foundation for voice retrieval stack: strict-first patient safety preserved, Meili adapter introduced, and fallback behavior covered by tests.
