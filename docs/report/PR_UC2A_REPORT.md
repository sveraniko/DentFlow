# PR UC-2A Report

## 1. Objective
Implement Redis/shared runtime state for unified card callbacks and active panels, add panel-family-aware supersession and TTL behavior, remove hardcoded profile strings, and introduce runtime view-model seams for product/patient/doctor cards.

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
- docs/16-4_booking_card_profile.md
- docs/16-5_card_runtime_state_and_redis_rules.md
- docs/80_integrations_and_infra.md
- docs/85_security_and_privacy.md
- docs/report/PR_UC1_REPORT.md
- docs/report/PR_UC1A_REPORT.md
- docs/report/PR_UC2_REPORT.md

## 3. Scope Implemented
- Added shared runtime store abstractions for callback tokens and active panel state.
- Replaced process-local callback token map with runtime-backed compact token resolution.
- Replaced process-local active panel map with runtime-backed panel state keyed by actor + panel family.
- Added panel family enum and supersede semantics by family key replacement.
- Added explicit TTL config for callback/panel/source state.
- Added stale-safe behavior on missing/expired callback tokens and stale panel state.
- Localized remaining hardcoded profile labels/actions/detail lines.
- Added runtime view builders for product/patient/doctor card seeds.
- Updated tests to validate runtime/shared behavior and localization path.

## 4. Redis Callback Registry Strategy
- Store compact callback payload bindings under `card:cb:<token>`.
- Keep Telegram callback data compact (`c2|<token>`).
- Resolve token server-side to semantic callback payload.
- Missing/expired token raises `CardCallbackError("invalid_callback_token")` to trigger stale-safe UX.

## 5. Panel Runtime State Strategy
- Store active panel entries under `card:panel:<actor_id>:<panel_family>`.
- Persist actor/chat/message + source context + state token + profile/entity correlation.
- Runtime coordinator binds/supersedes active state and validates freshness.

## 6. Panel Family Model
- Introduced explicit `PanelFamily` enum covering required families:
  - patient_home
  - patient_catalog
  - recommendation_flow
  - doctor_queue
  - admin_today
  - booking_detail
  - care_order_flow
  - search_results

## 7. TTL / Expiration Strategy
- `RuntimeTtlConfig` defaults:
  - callback: 30 minutes
  - panel: 2 hours
  - source context: 1 hour
- Tests cover immediate callback expiration behavior (`callback_ttl_sec=0`) and stale-safe rejection.

## 8. Stale/Graceful Degradation Notes
- Missing/expired callback token returns stale-safe error path.
- Superseded panel in same family replaces canonical active panel.
- Stale callback validation still enforces entity/source/page/state checks through existing `validate_stale_callback` flow.

## 9. Localization Fixes
- Removed hardcoded profile/action/detail strings from adapters.
- Added localized keys for card actions and profile detail labels in `locales/en.json` and `locales/ru.json`.

## 10. Runtime View Builder Strategy
- Added lightweight runtime view builders:
  - `ProductRuntimeViewBuilder`
  - `PatientRuntimeViewBuilder`
  - `DoctorRuntimeViewBuilder`
- Builders provide a stable seam for fresh runtime snapshot assembly before adapter rendering.

## 11. Files Added
- `app/interfaces/cards/runtime_state.py`
- `docs/report/PR_UC2A_REPORT.md`

## 12. Files Modified
- `app/interfaces/cards/callbacks.py`
- `app/interfaces/cards/panel_runtime.py`
- `app/interfaces/cards/adapters.py`
- `app/interfaces/cards/__init__.py`
- `tests/test_unified_card_framework_uc1.py`
- `locales/en.json`
- `locales/ru.json`

## 13. Commands Run
- `pytest tests/test_unified_card_framework_uc1.py`

## 14. Test Results
- Unified card runtime/localization test suite passed.

## 15. Remaining Known Limitations
- Redis client wiring into runtime bootstrap/bot routers is not yet integrated; runtime store abstraction is ready and tests use shared in-memory Redis stub.
- No booking-card business logic changes included (explicitly out of scope).

## 16. Deviations From Docs (if any)
- Production Redis transport wiring is prepared by abstraction but not yet connected to app bootstrap in this PR.

## 17. Readiness Assessment for PR UC-3
- Card runtime state contract now has a shared-store seam, panel-family model, TTL knobs, stale-safe token behavior, and localized profile rendering.
- UC-3 can build on this runtime contract without reworking card shell/callback semantics.
