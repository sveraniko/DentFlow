# PR UC-2C Report: Redis-First Card Runtime Migration in Real Flows

## 1. Objective
Make shared Redis-backed card runtime state the real production interaction path in patient Telegram flows by removing process-local panel/session/mode/care runtime dictionaries from the migrated flow path.

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
20. docs/redis_audit_2026-04-19.md

## 3. Scope Implemented
- Added shared actor session-state storage primitives to card runtime state store/coordinator (`card:session:<scope>:<actor_id>` with TTL).
- Migrated patient router runtime interaction state (booking session/mode/care-state/panel binding) from process-local dicts to shared runtime state.
- Enforced panel family usage in real patient handlers (`PATIENT_CATALOG` for care flow, `BOOKING_DETAIL` for booking flow) via runtime active panel store.
- Added stale-safe guard for callback-triggered panel edits when callback message is no longer the active panel in that panel family.
- Added tests covering shared actor runtime state cross-coordinator usage and stale active-panel safety behavior.

## 4. Migrated Flows
- Patient booking entry + booking callback progression (`/book`, `/my_booking`, service/doctor/slot callbacks, contact submission handling).
- Patient care catalog/product/reserve callback navigation (`/care` and `care:*` callback path).
- Existing booking card action callbacks (`mybk:*` callbacks) now rely on shared session-state retrieval.

## 5. Process-Local State Removed
Removed process-local production runtime dictionaries from `app/interfaces/bots/patient/router.py`:
- `panel_by_user`
- `session_by_user`
- `mode_by_user`
- `care_state_by_user`

## 6. Shared Runtime State Usage in Real Handlers
Real patient handlers now use shared runtime state for:
- actor session correlation state (`booking_session_id`, `booking_mode`, care state blob)
- active panel state resolution and rebinding on send/edit panel operations
- panel-family-aware active panel supersession and stale callback rejection

## 7. Panel Family / Invalidation Notes
- Care flow panel updates are bound under `PanelFamily.PATIENT_CATALOG`.
- Booking flow panel updates are bound under `PanelFamily.BOOKING_DETAIL`.
- Runtime active panel record is superseded per family on each render/update.
- Callback edit is stale-rejected when callback message is not the active message for that actor+family.

## 8. Missing-State / Restart-Safe Behavior
- Missing session state now causes existing safe behavior (session-missing localized message / early return), but state origin is shared runtime store instead of process memory.
- Missing/stale active panel in callback edit path is handled with localized stale callback alert.
- Actor interaction state is now shareable across coordinators/workers as long as runtime store survives (restart-safe within TTL policy).

## 9. Files Added
- docs/report/PR_UC2C_REPORT.md

## 10. Files Modified
- app/interfaces/cards/runtime_state.py
- app/interfaces/bots/patient/router.py
- tests/test_unified_card_framework_uc1.py

## 11. Commands Run
- `rg --files -g 'AGENTS.md'`
- `find .. -name AGENTS.md -maxdepth 4`
- multiple `sed -n` reads for required docs and prior UC reports
- `rg "panel_by_user|session_by_user|mode_by_user|care_state_by_user|..." app/interfaces/bots app/application -n`
- `pytest -q tests/test_unified_card_framework_uc1.py`
- `rg "panel_by_user|session_by_user|mode_by_user|care_state_by_user" app/interfaces/bots/patient/router.py -n`

## 12. Test Results
- `tests/test_unified_card_framework_uc1.py`: pass (7 passed)
- Added coverage for shared actor session state and stale active panel validation

## 13. Remaining Known Limitations
- This PR migrates patient flow runtime state; admin/doctor flow-local runtime hardening remains follow-up work.
- `card_callback_codec` injection in patient router remains unused in this migration pass (callback payload format migration is outside this PR scope).
- Voice mode store remains process-local (not part of this card runtime migration target).

## 14. Deviations From Docs (if any)
- None intentional for UC-2C scope.

## 15. Readiness Assessment for PR UC-3
- Patient card-heavy runtime path now uses shared interaction state instead of process-local dictionaries.
- One-active-panel family semantics are actively applied in real patient handlers.
- Restart/multi-worker resilience is materially improved for migrated patient flow state.
- Repo is ready for UC-3 booking-card business implementation on top of shared runtime interaction state.
