# PR Stack 5B1 Report — Real STT Adapter + Voice Fault Boundary

## 1. Objective
Complete Stack 5B production-readiness for narrow voice-assisted retrieval by adding one real STT adapter option, coherent runtime provider selection, and safe fault boundaries for Telegram voice intake and STT failures.

## 2. Docs Read
Read before implementation (requested order):
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/10_architecture.md
4. docs/12_repo_structure_and_code_map.md
5. docs/40_search_model.md
6. docs/15_ui_ux_and_product_rules.md
7. docs/17_localization_and_i18n.md
8. docs/80_integrations_and_infra.md
9. docs/85_security_and_privacy.md
10. docs/90_pr_plan.md
11. docs/95_testing_and_launch.md
12. docs/report/PR_STACK_5B_REPORT.md

## 3. Scope Implemented
- Added one real production-capable STT adapter: OpenAI Audio Transcriptions provider.
- Added coherent runtime STT provider selection for `disabled`, `fake`, and `openai`.
- Added typed safe fallback behavior for Telegram voice intake failures and STT provider runtime faults.
- Preserved temp voice file cleanup across all success/failure paths.
- Strengthened tests for runtime wiring and fault boundaries.

## 4. Real STT Provider Strategy
Implemented `OpenAISpeechToTextProvider` behind existing `SpeechToTextProvider` abstraction.

### Config keys
- `STT_PROVIDER=openai`
- `STT_OPENAI_API_KEY`
- `STT_OPENAI_MODEL` (default `gpt-4o-mini-transcribe`)
- `STT_OPENAI_ENDPOINT` (default `https://api.openai.com/v1/audio/transcriptions`)
- Existing: `STT_TIMEOUT_SEC`, `STT_LANGUAGE_HINT`, `STT_CONFIDENCE_THRESHOLD`

### Request/response assumptions
- Sends multipart/form-data to OpenAI transcriptions endpoint.
- Sends `model`, optional `language`, and a single audio file payload.
- Expects JSON object with `text` field.
- If transcript text is missing/empty, resolved as `transcription_failed` fallback.

### Timeout/error handling
- Network/timeout conditions resolve to typed `provider_timeout`.
- Other provider failures resolve to typed `provider_error`.

## 5. Runtime Provider Selection
Runtime now uses `build_speech_to_text_provider(stt_config)`:
- `enabled=false` -> disabled provider
- `provider=disabled` -> disabled provider
- `provider=fake` -> fake provider
- `provider=openai` -> OpenAI provider (requires API key)
- Unknown provider -> startup `RuntimeError`

This removes fake-only runtime wiring while preserving fake/disabled paths for local/tests.

## 6. Fault Boundary Strategy
In Telegram voice handling:
- `get_file`, `download_file`, and local file reads are wrapped in safe boundary.
- Any intake exception returns typed fallback `download_failed` (localized user feedback).
- Temp file cleanup remains in `finally` and executes even when failures occur.

In STT service boundary:
- Provider exceptions/timeouts are caught and converted into typed outcomes:
  - `provider_timeout`
  - `provider_error`
- Handler degrades safely via localized fallback response and no search mutation.

## 7. Files Added
- `app/infrastructure/speech/openai_provider.py`
- `tests/test_stt_stack5b1_runtime.py`
- `docs/report/PR_STACK_5B1_REPORT.md`

## 8. Files Modified
- `app/application/voice/models.py`
- `app/application/voice/service.py`
- `app/interfaces/bots/voice_search.py`
- `app/bootstrap/runtime.py`
- `app/config/settings.py`
- `tests/test_voice_search_stack5b.py`
- `locales/en.json`
- `locales/ru.json`
- `.env.example`

## 9. Commands Run
- `find .. -name AGENTS.md -print`
- `rg -n "SpeechToText|voice|stt|telegram|transcrib" -S app tests docs`
- `pytest -q tests/test_voice_search_stack5b.py tests/test_stt_stack5b1_runtime.py`
- `pytest -q tests/test_search_ui_stack5a1a.py`

## 10. Test Results
- `pytest -q tests/test_voice_search_stack5b.py tests/test_stt_stack5b1_runtime.py` -> 15 passed
- `pytest -q tests/test_search_ui_stack5a1a.py` -> 3 passed

## 11. Remaining Known Limitations
- OpenAI adapter parses only transcript text and optional confidence field if present.
- No multi-provider orchestration in this PR (intentionally out of scope).
- No broad voice assistant behavior (intentionally out of scope).

## 12. Deviations From Docs (if any)
- None intentional.
- Voice remains narrow search input, uses canonical search services, and does not persist raw audio as business truth.

## 13. Readiness Assessment for Stack 6A
Ready to proceed:
- Runtime is no longer fake-only.
- Real STT adapter option exists and is selectable.
- Telegram intake + provider runtime faults degrade safely.
- Fake/disabled paths remain intact for test/dev.
- Behavioral tests cover core Stack 5B1 fault scenarios.
