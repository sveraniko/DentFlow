# PR UC-1 Report: Unified Card Shell + Callback/Navigation Foundation

## 1. Objective
Implement a shared, typed card framework for Telegram UI: shell model, compact/expanded mode behavior, source-aware callbacks/navigation, stale-safe action validation, and one-active-panel update helpers, with minimal profile adapters and tests.

## 2. Docs Read
- README.md
- docs/18_development_rules_and_baseline.md
- docs/10_architecture.md
- docs/12_repo_structure_and_code_map.md
- docs/15_ui_ux_and_product_rules.md
- docs/17_localization_and_i18n.md
- docs/16_unified_card_system.md
- docs/16-1_card_profiles.md
- docs/16-2_card_callback_contract.md
- docs/16-3_card_media_and_navigation_rules.md

## 3. Precedence Decisions
1. Followed README + architecture/development rules for layering and reusable typed contracts.
2. Followed card docs for callback semantic fields and source-aware navigation requirements.
3. Kept profile payloads minimal (non-goal in this PR).

## 4. Shared Card Shell Strategy
Added typed dataclasses/enums for shared shell concerns:
- profile/entity/mode identity
- source context and source references
- badges/meta/detail/actions/media/navigation
- immutable shell mode transition helper

## 5. Mode Model
Implemented explicit compact/expanded/list_row/picker mode enum and deterministic transition helper preserving same entity/source identity.

## 6. Source Context Strategy
Implemented explicit `SourceContext` enum and `SourceRef` typed object to preserve source panel + reference/index metadata for deterministic back behavior.

## 7. Callback Contract Strategy
Implemented callback codec with explicit semantic model carrying:
- profile
- entity_type
- entity_id
- action
- mode
- source_context
- source_ref
- page_or_index
- state_token

Compact payload is encoded/decoded with a versioned contract (`c1|...`).

## 8. Stale Protection Strategy
Implemented baseline stale/entity/context validation:
- rejects mismatched entity id
- rejects mismatched source context
- rejects stale state tokens
- returns localization keys for compact UI feedback

## 9. Media/Navigation Framework Notes
Implemented shared action family enum with media/navigation actions (`open`, `expand`, `collapse`, `back`, `cover`, `gallery`, `next`, `prev`, `page`, `home`) and deterministic back-target resolver for compact/expanded behavior.

## 10. Example Profile Adapter Notes
Implemented minimal adapters:
- `ProductCardAdapter`
- `BookingCardAdapter`

Both map thin seed payloads to shared card shell in compact/expanded modes without introducing full business UX scope.

## 11. Files Added
- `app/interfaces/cards/__init__.py`
- `app/interfaces/cards/models.py`
- `app/interfaces/cards/callbacks.py`
- `app/interfaces/cards/navigation.py`
- `app/interfaces/cards/panel_runtime.py`
- `app/interfaces/cards/rendering.py`
- `app/interfaces/cards/adapters.py`
- `tests/test_unified_card_framework_uc1.py`
- `docs/report/PR_UC1_REPORT.md`

## 12. Files Modified
- `locales/en.json`
- `locales/ru.json`

## 13. Commands Run
- `rg --files -g 'AGENTS.md'`
- `find . -maxdepth 2 -type f | head -n 200`
- multiple `sed -n` doc reads
- `find app -maxdepth 4 -type f`
- `rg -n "card|callback|panel" app tests | head -n 200`
- `python - <<'PY' ...` (locale key updates)
- `pytest -q tests/test_unified_card_framework_uc1.py`
- `pytest -q tests/test_i18n.py tests/test_search_ui_stack5a1a.py`

## 14. Test Results
- `tests/test_unified_card_framework_uc1.py`: pass
- `tests/test_i18n.py`: pass
- `tests/test_search_ui_stack5a1a.py`: pass

## 15. Known Limitations / Explicit Non-Goals
- No full business payload implementations for product/patient/doctor/booking profiles.
- No full aiogram callback handler migration to the new contract yet.
- No full media delivery engine yet; this PR provides action and navigation foundation.

## 16. Deviations From Docs (if any)
- None identified for UC-1 scope. Implementation intentionally stops at framework baseline and minimal adapters.

## 17. Readiness Assessment for PR UC-2
Ready for UC-2 profile expansion:
- Shared shell and semantic callback contract exist.
- Source-aware/stale-safe primitives exist.
- One-active-panel helper contract exists.
- Minimal profile adapters demonstrate shell hosting.
