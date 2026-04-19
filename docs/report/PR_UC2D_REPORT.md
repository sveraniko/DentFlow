# PR UC-2D Report: Card Callback Runtime Completion

## 1. Objective
Complete the remaining UC-2 runtime/card interaction tails before UC-3 by making shared callback codec usage primary in real card interactions, removing critical legacy shortcut dependence in card-heavy paths, and migrating voice/card-adjacent runtime mode state to shared runtime storage.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/10_architecture.md
4. docs/12_repo_structure_and_code_map.md
5. docs/15_ui_ux_and_product_rules.md
6. docs/17_localization_and_i18n.md
7. docs/16_unified_card_system.md
8. docs/16-1_card_profiles.md
9. docs/16-2_card_callback_contract.md
10. docs/16-3_card_media_and_navigation_rules.md
11. docs/16-4_booking_card_profile.md
12. docs/16-5_card_runtime_state_and_redis_rules.md
13. docs/80_integrations_and_infra.md
14. docs/85_security_and_privacy.md
15. docs/report/PR_UC1_REPORT.md
16. docs/report/PR_UC1A_REPORT.md
17. docs/report/PR_UC2_REPORT.md
18. docs/report/PR_UC2A_REPORT.md
19. docs/report/PR_UC2B_REPORT.md
20. docs/report/PR_UC2C_REPORT.md
21. docs/redis_audit_2026-04-19.md

## 3. Scope Implemented
- Enforced shared card callback codec as required dependency in patient router and introduced runtime callback encoding helper.
- Migrated care catalog/product interaction buttons and booking-card action buttons to `c2|<token>` callback transport.
- Added runtime callback dispatch handler (`c2|`) to resolve callbacks via shared runtime and execute care/booking actions.
- Kept legacy callback handlers as non-primary backward compatibility paths.
- Migrated voice mode store to async/shared runtime-capable implementation and wired runtime-backed mode storage in bootstrap.
- Added runtime coordinator clear-session API required by voice mode cleanup.
- Expanded tests for shared voice mode state cross-coordinator behavior.

## 4. Callback Path Completion Notes
- Card-heavy patient care and booking-card action callback generation now uses `CardCallbackCodec.encode(...)` and shared token resolution path.
- Runtime callback handler decodes `c2` payloads and routes actions by semantic callback metadata (source context + action/page markers).
- Legacy string callback handlers remain as fallback for pre-existing/stale inline buttons but are no longer the primary emission path in migrated flows.

## 5. Legacy Shortcut Removal Notes
- Removed primary dependence on ad-hoc care/my-booking callback strings for newly rendered card interactions.
- Shared callback transport now drives the primary callback path for those card interactions.

## 6. Admin/Doctor Runtime Hardening Notes
- No new admin/doctor process-local card runtime shortcuts were introduced.
- Voice mode state used by admin/doctor voice-driven retrieval now uses shared runtime when runtime is provided by registry wiring, preventing process-local drift between coordinators.

## 7. Voice/Card State Migration Notes
- `VoiceSearchModeStore` now supports runtime-backed shared storage via actor session-state keys (`voice_mode` scope).
- Voice handler now awaits mode activation/read/clear operations.
- Bootstrap now constructs `VoiceSearchModeStore(runtime=self.card_runtime)` so production role routers use shared runtime mode state.
- In-memory fallback behavior remains available for isolated tests/standalone usage.

## 8. Files Added
- docs/report/PR_UC2D_REPORT.md

## 9. Files Modified
- app/interfaces/bots/patient/router.py
- app/application/voice/mode.py
- app/interfaces/cards/runtime_state.py
- app/interfaces/bots/voice_search.py
- app/bootstrap/runtime.py
- tests/test_voice_search_stack5b.py

## 10. Commands Run
- `rg --files -g 'AGENTS.md'`
- `find .. -name AGENTS.md -print`
- `sed -n ...` on required docs and runtime/card files
- `rg -n ...` audits for callback/runtime usage
- `pytest -q tests/test_unified_card_framework_uc1.py tests/test_voice_search_stack5b.py tests/test_runtime_wiring.py`

## 11. Test Results
- `tests/test_unified_card_framework_uc1.py`: pass
- `tests/test_voice_search_stack5b.py`: pass
- `tests/test_runtime_wiring.py`: pass

## 12. Remaining Known Limitations
- Booking session progression callbacks (`book:svc/doc/slot`) remain legacy-format in this PR and should be considered for a future full callback-contract sweep if they are elevated to card-profile callback semantics.
- Admin/doctor router surfaces are still mostly command/search flows; no broad card-surface migration was forced beyond preventing new local runtime shortcuts.

## 13. Deviations From Docs (if any)
- None intentional; compatibility fallback handlers were retained to avoid breaking stale already-sent inline messages while making codec path primary for newly rendered card interactions.

## 14. Readiness Assessment for PR UC-3
- Shared callback codec is now the primary emission path for existing patient card-heavy care/product and booking-card control interactions.
- Voice/card-adjacent mode state no longer depends on process-local-only storage in runtime wiring.
- Shared runtime interaction foundation is coherent enough for UC-3 booking-card business implementation, with noted legacy booking-session callback tail explicitly documented.
