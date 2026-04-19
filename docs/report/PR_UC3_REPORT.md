# PR UC-3 Report

## 1. Objective
Implement the booking card profile on top of the shared unified card runtime, including compact/expanded behavior, explicit role variants, linked-object open actions, and runtime-seeded card assembly.

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
13. docs/22_access_and_identity_model.md
14. docs/23_policy_and_configuration_model.md
15. docs/25_state_machines.md
16. docs/70_bot_flows.md
17. docs/72_admin_doctor_owner_ui_contracts.md
18. docs/68_admin_reception_workdesk.md
19. docs/69_google_calendar_schedule_projection.md
20. docs/80_integrations_and_infra.md
21. docs/85_security_and_privacy.md
22. docs/90_pr_plan.md
23. docs/95_testing_and_launch.md
24. docs/report/PR_UC1_REPORT.md
25. docs/report/PR_UC1A_REPORT.md
26. docs/report/PR_UC2_REPORT.md
27. docs/report/PR_UC2A_REPORT.md
28. docs/report/PR_UC2B_REPORT.md
29. docs/report/PR_UC2C_REPORT.md
30. docs/report/PR_UC2D_REPORT.md

## 3. Precedence Decisions
- Used `docs/16-4_booking_card_profile.md` as the primary behavior contract for compact/expanded content, role split, and linked-object boundaries.
- Kept callback/runtime assumptions aligned with UC-2D carry-forward: booking card actions are represented in shared card action/callback semantics and remain compatible with existing `c2|` callback transport.
- Preserved booking domain ownership in booking services; card-layer work stays projection/rendering oriented.

## 4. Booking Card Builder Strategy
- Added `BookingRuntimeSnapshot` + `BookingRuntimeViewBuilder` in the shared card adapter layer.
- Builder assembles runtime-aware booking seed data:
  - local-time formatted datetime from timezone-aware timestamp
  - patient/doctor/service/branch/status summary
  - compact chips/flags
  - reminder/reschedule/source/contact/recommendation/care/chart hints
  - role/status-based action visibility matrix.

## 5. Compact/Expanded Design Notes
- Compact mode now emphasizes booking identity and actionability:
  - title/subtitle for rapid scan
  - status + compact badges
  - core meta lines (time/patient/doctor/service/branch/status)
  - bounded action density.
- Expanded mode adds bounded operational context only:
  - channel, contact hint (role-safe), reminder/reschedule summary
  - linked recommendation/care/chart summaries
  - next-step summary.

## 6. Role Variant Notes
- Added explicit role variant support through `BookingCardSeed.role_variant` (`patient|admin|doctor|owner`).
- Enforced role/status action visibility for:
  - patient: confirm/reschedule/cancel
  - admin: confirm/arrived + linked opens
  - doctor: in_service/complete + linked opens
  - owner: conservative read-only posture (no routine mutation actions).

## 7. Linked Object Navigation Notes
- Booking card action surface now includes linked-open actions:
  - patient
  - chart
  - recommendation
  - care order
- These are exposed as card actions for callback/runtime transport rather than embedding linked objects into booking content.

## 8. Legacy Callback Migration Notes
- UC-2D runtime callback path (`c2|token`) remains the primary shared callback transport and remains compatible with booking card actions.
- Existing legacy booking wizard callbacks (`book:*`) are still bounded to session wizard stages and were not expanded.
- Legacy `mybk:*` fallback paths remain compatibility tails for old/stale messages; card-layer booking actions now align with unified card action semantics.

## 9. Files Added
- `docs/report/PR_UC3_REPORT.md`

## 10. Files Modified
- `app/interfaces/cards/models.py`
- `app/interfaces/cards/adapters.py`
- `app/interfaces/cards/__init__.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_unified_card_framework_uc1.py`

## 11. Commands Run
- `python -m json.tool locales/en.json >/dev/null`
- `python -m json.tool locales/ru.json >/dev/null`
- `pytest -q tests/test_unified_card_framework_uc1.py`
- `pytest -q tests/test_runtime_wiring.py`

## 12. Test Results
- `tests/test_unified_card_framework_uc1.py`: pass (8 passed)
- `tests/test_runtime_wiring.py`: pass (2 passed)

## 13. Known Limitations / Explicit Non-Goals
- This PR focuses on shared booking card profile runtime/rendering and card-layer behavior.
- It does not rewrite booking orchestration/domain logic.
- Full admin/doctor/owner card-driven bot surface migration is intentionally bounded and remains incremental.

## 14. Deviations From Docs (if any)
- None intentional in card-layer scope. Some legacy callback compatibility handlers remain intentionally bounded for stale-message safety.

## 15. Readiness Assessment for next PR
- Shared booking card profile now has runtime builder, explicit role variants, bounded compact/expanded behavior, and linked action surface in the unified card shell.
- Repo is ready for deeper role-router callback dispatch integration and end-to-end booking-card-first UX migration in subsequent PRs.
