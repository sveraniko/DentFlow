# PR Stack 5B Report — Voice-Assisted Retrieval

## 1. Objective
Implement a narrow, production-safe voice-assisted retrieval layer for admin/doctor operational search on top of canonical Search Core + Meilisearch hybrid search, without introducing general assistant behavior.

## 2. Docs Read
Read and used for implementation decisions (in requested precedence order):
- README.md
- docs/18_development_rules_and_baseline.md
- docs/10_architecture.md
- docs/12_repo_structure_and_code_map.md
- docs/40_search_model.md
- docs/15_ui_ux_and_product_rules.md
- docs/17_localization_and_i18n.md
- docs/22_access_and_identity_model.md
- docs/23_policy_and_configuration_model.md
- docs/20_domain_model.md
- docs/30_data_model.md
- docs/70_bot_flows.md
- docs/72_admin_doctor_owner_ui_contracts.md
- docs/80_integrations_and_infra.md
- docs/85_security_and_privacy.md
- docs/90_pr_plan.md
- docs/95_testing_and_launch.md
- docs/report/PR_STACK_5A1_REPORT.md
- docs/report/PR_STACK_5A1A_REPORT.md

## 3. Precedence Decisions
1. Voice is implemented as an input modality only; canonical truth remains in existing search + core models.
2. Voice pipeline reuses canonical search services (`HybridSearchService`) instead of adding parallel search logic.
3. Voice retrieval is restricted to admin/doctor surfaces and explicit mode activation commands.
4. Safe fallback is preferred over convenience for uncertain or failed STT outcomes.

## 4. STT Provider Strategy
- Added STT configuration block under `STT_*` env keys.
- Added `SpeechToTextProvider` abstraction with typed input/output.
- Added concrete providers:
  - `FakeSpeechToTextProvider` (deterministic adapter for controlled local/testing use)
  - `DisabledSpeechToTextProvider` (safe default behavior)
- Added `SpeechToTextService` to apply confidence threshold and sanitize empty transcript handling.

## 5. Voice Mode Strategy
- Added explicit short-lived voice search modes:
  - `/voice_find_patient`
  - `/voice_find_doctor`
  - `/voice_find_service`
- Mode state stored in `VoiceSearchModeStore`, scoped by actor Telegram ID with TTL and cleanup.
- Voice messages are interpreted for search only when an active mode exists.

## 6. Confidence / Fallback Strategy
Typed STT outcomes are handled explicitly:
- `success`
- `transcription_failed`
- `low_confidence`
- `unsupported_audio`
- `too_long`
- `too_large`
- `mode_not_active`

Fallback behavior:
- No mutation and no guessed results on weak/failed STT.
- Localized prompt to retry voice or type manually.
- If STT succeeds but search has no matches, standard no-match search rendering is returned.

## 7. Search Integration Notes
- Patient voice search calls canonical `run_patient_search` -> strict-first hybrid path.
- Doctor voice search calls canonical `run_doctor_search` -> Meili-primary with PG fallback via `HybridSearchService`.
- Service voice search calls canonical `run_service_search` -> locale-aware Meili-primary with PG fallback.
- Voice result rendering uses existing search surfaces; no duplicate UI channel was introduced.

## 8. Privacy / Retention Handling
- Raw Telegram voice files are downloaded to temporary files only for transcription intake.
- Temporary files are deleted in all cases (`finally` cleanup path).
- No raw audio is stored as canonical business data.
- No transcript is persisted as system truth; transcript echo is transient user feedback only.

## 9. Files Added
- `app/application/voice/__init__.py`
- `app/application/voice/models.py`
- `app/application/voice/provider.py`
- `app/application/voice/mode.py`
- `app/application/voice/service.py`
- `app/infrastructure/speech/fake_provider.py`
- `app/infrastructure/speech/disabled_provider.py`
- `app/interfaces/bots/voice_search.py`
- `tests/test_voice_search_stack5b.py`
- `docs/report/PR_STACK_5B_REPORT.md`

## 10. Files Modified
- `app/config/settings.py`
- `app/bootstrap/runtime.py`
- `app/interfaces/bots/admin/router.py`
- `app/interfaces/bots/doctor/router.py`
- `tests/test_search_ui_stack5a1a.py`
- `locales/en.json`
- `locales/ru.json`
- `.env.example`

## 11. Commands Run
- `find .. -name AGENTS.md -print`
- `rg -n "voice|speech|stt|..." app docs tests`
- `pytest -q tests/test_search_ui_stack5a1a.py tests/test_voice_search_stack5b.py`

## 12. Test Results
- `pytest -q tests/test_search_ui_stack5a1a.py tests/test_voice_search_stack5b.py` -> **9 passed**

## 13. Known Limitations / Explicit Non-Goals
- No general conversational voice assistant behavior.
- No patient-facing broad voice discovery surface.
- No voice-triggered booking mutation flows.
- Current concrete STT adapter is deterministic fake provider for safe/local integration paths; provider abstraction is ready for production STT adapter wiring in later stack work.

## 14. Deviations From Docs (if any)
- None intentional. Implementation follows narrow voice retrieval scope and canonical search integration rules.

## 15. Readiness Assessment for PR Stack 6A
Ready for Stack 6A with caveat:
- Core voice retrieval scaffolding, role guards, mode integrity, fallback behavior, and tests are in place.
- Production STT adapter implementation can be added behind existing provider abstraction without changing caller contracts.
