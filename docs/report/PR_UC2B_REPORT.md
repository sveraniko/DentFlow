# PR UC-2B Report

## 1. Objective
Finish UC-2A runtime hardening by wiring shared card runtime state into real application bootstrap/runtime, adding a real Redis-backed production adapter path, and replacing pass-through runtime view builders for product/patient/doctor seeds with runtime-aware assembly.

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

## 3. Scope Implemented
- Added production Redis adapter for card runtime state and callback token storage.
- Wired runtime store/coordinator/codec in real `RuntimeRegistry` bootstrap path.
- Passed runtime/codec dependencies into patient/admin/doctor router construction seams.
- Replaced decorative runtime view builders with runtime snapshot assembly for product/patient/doctor card seeds.
- Strengthened tests to verify runtime wiring and builder behavior are real (not pass-through wrappers).

## 4. Redis Runtime Wiring Strategy
- Introduced `AsyncRedisRuntimeAdapter` backed by `redis.asyncio` and configured via `Settings.redis.url`.
- Added `build_card_runtime_redis(settings)` factory:
  - production env (`prod` / `production`) -> Redis adapter
  - non-production env -> in-memory adapter for local/dev/test workflow.
- This keeps a real production Redis path while preserving low-friction local testing.

## 5. Bootstrap Integration Notes
- `RuntimeRegistry` now constructs:
  - `CardRuntimeStateStore`
  - `CardRuntimeCoordinator`
  - `CardCallbackCodec`
- Wiring happens during app bootstrap, not just in tests.
- Runtime/codec references are injected into router factories so handler/runtime seams can consume shared card runtime state.

## 6. Product/Patient/Doctor Builder Strategy
- Added explicit runtime snapshots for each profile:
  - `ProductRuntimeSnapshot`
  - `PatientRuntimeSnapshot`
  - `DoctorRuntimeSnapshot`
- Builders now assemble seeds from runtime snapshot data:
  - Product: localized title/description fallback, stock status to availability label, branch/recommendation/media info.
  - Patient: display-name assembly, contact masking, active flag summary, booking/recommendation/order/chart snippets.
  - Doctor: specialty/branch with queue + today operational hint assembly.
- Builders now act as real seams from runtime truth snapshots to UI card seed model.

## 7. Files Added
- `app/infrastructure/cache/redis_runtime.py`
- `docs/report/PR_UC2B_REPORT.md`

## 8. Files Modified
- `app/bootstrap/runtime.py`
- `app/infrastructure/cache/__init__.py`
- `app/interfaces/cards/adapters.py`
- `app/interfaces/cards/__init__.py`
- `app/interfaces/bots/patient/router.py`
- `app/interfaces/bots/admin/router.py`
- `app/interfaces/bots/doctor/router.py`
- `tests/test_unified_card_framework_uc1.py`
- `tests/test_runtime_wiring.py`
- `pyproject.toml`

## 9. Commands Run
- `pytest -q tests/test_unified_card_framework_uc1.py tests/test_runtime_wiring.py`

## 10. Test Results
- `tests/test_unified_card_framework_uc1.py`: pass
- `tests/test_runtime_wiring.py`: pass

## 11. Remaining Known Limitations
- Router seams now receive runtime/codec, but existing booking/patient flow internals still use legacy callback/state mechanics in many places; full callback-handler migration remains future work.
- Non-production runtime defaults to in-memory state; production uses Redis-backed path.

## 12. Deviations From Docs (if any)
- None intentional for UC-2B scope.

## 13. Readiness Assessment for PR UC-3
- Runtime foundation is now materially ready:
  - production Redis path exists and is wired in bootstrap
  - shared card runtime coordinator exists in real app runtime graph
  - profile runtime builders perform concrete assembly
  - tests cover runtime wiring + builder behavior
- UC-3 can proceed with booking-card business work on top of this foundation.
