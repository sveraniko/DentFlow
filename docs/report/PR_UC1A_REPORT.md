# PR UC-1A Report: Compact Callback Encoding + Strong Context Validation

## 1. Objective
Deliver a narrow callback/runtime integrity pass for the unified card shell by replacing oversized callback transport with a practical compact strategy and strengthening stale/context validation for source-aware safety.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/10_architecture.md
4. docs/12_repo_structure_and_code_map.md
5. docs/16_unified_card_system.md
6. docs/16-1_card_profiles.md
7. docs/16-2_card_callback_contract.md
8. docs/16-3_card_media_and_navigation_rules.md
9. docs/16-4_booking_card_profile.md
10. docs/report/PR_UC1_REPORT.md

## 3. Scope Implemented
- Replaced default raw callback transport with compact callback token encoding.
- Preserved semantic callback contract through server-side semantic payload registry lookup.
- Strengthened callback validation to support source_ref/page checks where required.
- Added tests for Telegram callback practicality, stronger context checks, stale safety, legacy decode compatibility, and semantic roundtrip.

## 4. Compact Callback Strategy
### Chosen approach
Opaque callback token + semantic lookup registry.

### Runtime shape
- Telegram callback payload now defaults to compact format: `c2|<token>`.
- Token is generated from a monotonic base36 id plus short digest suffix.
- Full semantic callback payload remains explicit in `CardCallback` and is reconstructed via codec registry lookup.

### Why this approach
- Keeps payload bounded for Telegram callback size constraints.
- Avoids brittle manual truncation of semantic fields.
- Preserves explicit semantic contract in typed model and decode result.
- Allows legacy `c1|...` payload decode for transition/regression stability.

## 5. Context Validation Strategy
Validation now supports stronger source-aware checks in addition to entity/context/state:
- `entity_id` match
- `source_context` match
- optional strict `source_ref` match (`require_source_ref_match=True`)
- optional strict `page_or_index` match (`require_page_or_index_match=True`)
- `state_token` match

This keeps safety configurable per action while enabling strong list/page-bound protection where relevant.

## 6. Files Added
- docs/report/PR_UC1A_REPORT.md

## 7. Files Modified
- app/interfaces/cards/callbacks.py
- tests/test_unified_card_framework_uc1.py
- locales/en.json
- locales/ru.json

## 8. Commands Run
- `sed -n '1,220p' README.md`
- `sed -n '1,260p' docs/18_development_rules_and_baseline.md`
- `sed -n '1,260p' docs/10_architecture.md`
- `sed -n '1,260p' docs/12_repo_structure_and_code_map.md`
- `sed -n '1,280p' docs/16_unified_card_system.md`
- `sed -n '1,260p' docs/16-1_card_profiles.md`
- `sed -n '1,320p' docs/16-2_card_callback_contract.md`
- `sed -n '1,320p' docs/16-3_card_media_and_navigation_rules.md`
- `sed -n '1,320p' docs/16-4_booking_card_profile.md`
- `sed -n '1,320p' docs/report/PR_UC1_REPORT.md`
- `pytest -q tests/test_unified_card_framework_uc1.py`
- `pytest -q tests/test_i18n.py`

## 9. Test Results
- `tests/test_unified_card_framework_uc1.py`: pass (includes callback size + stronger validation scenarios)
- `tests/test_i18n.py`: pass

## 10. Remaining Known Limitations
- Compact callback registry is in-memory and process-local in this foundation layer.
- No distributed callback token persistence implemented in this PR (out of scope).
- No full aiogram handler wiring in this PR (non-goal from UC-1A scope statement).

## 11. Deviations From Docs (if any)
- None. Semantic callback contract remains explicit while transport is compacted as allowed by callback contract docs.

## 12. Readiness Assessment for PR UC-2
Ready for UC-2 profile-rich work on callback/runtime integrity criteria:
- practical compact callback payload transport in place
- semantic callback reconstruction preserved
- stronger source_ref/page-aware validation available where relevant
- stale/entity/context safeguards preserved and tested
