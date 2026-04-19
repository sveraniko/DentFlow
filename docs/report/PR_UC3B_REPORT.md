# PR UC-3B Report: Booking Card Completion

## 1. Objective
Complete booking card runtime behavior so patient/admin/doctor flows use the unified booking card shell as the primary booking object, improve linked open behavior to real navigable paths, and fix local-time and label quality issues in booking card snapshots.

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
16. docs/68_admin_reception_workdesk.md
17. docs/69_google_calendar_schedule_projection.md
18. docs/70_bot_flows.md
19. docs/72_admin_doctor_owner_ui_contracts.md
20. docs/80_integrations_and_infra.md
21. docs/85_security_and_privacy.md
22. docs/90_pr_plan.md
23. docs/95_testing_and_launch.md
24. docs/report/PR_UC3A_REPORT.md

## 3. Scope Implemented
- Replaced patient booking detail render path from legacy text card formatter to unified booking card shell rendering in primary existing-booking flow surfaces.
- Added booking snapshot builder in booking flow service to centralize label/timezone resolution and support adapter-driven shells across flows.
- Updated admin booking card rendering to use snapshot builder + runtime adapter data (local timezone hierarchy + resolved labels).
- Updated doctor booking card rendering to use local timezone resolution (branch > clinic > UTC fallback).
- Replaced linked object open callbacks (admin/doctor) from command shortcuts/alert stubs to navigable panels with explicit Back action to booking card.
- Strengthened tests for booking card snapshot local-time/label behavior and maintained existing UC-3A runtime tests.

## 4. Patient Booking Card Completion Notes
- Existing-booking result and post-action rerenders now go through booking runtime snapshot -> BookingRuntimeViewBuilder -> BookingCardAdapter -> CardShellRenderer.
- Legacy `_render_booking_card_text(...)` formatter is removed from primary patient booking control path.
- Confirm/reschedule/cancel actions continue to run through `c2|` callback payload path and re-render card shell output.
- Legacy `mybk:*` callbacks remain as bounded compatibility tail handlers for stale buttons only.

## 5. Admin Booking Card Completion Notes
- Admin booking open panel now uses snapshot builder from booking flow service instead of direct UTC + raw-id assembly.
- Booking card continues using expanded mode with action keyboard and `c2|` callback transport.
- Action callbacks (confirm/checked-in/reschedule/cancel) still mutate booking state then re-render through unified shell.

## 6. Doctor Booking Card Completion Notes
- Doctor booking shell snapshot now resolves timezone context from branch/clinic fallback order instead of fixed UTC.
- Doctor queue-opened booking cards keep booking-card-as-primary behavior with role-safe actions.
- In-service/complete actions remain callback-driven and re-render card shell after state changes.

## 7. Linked Object Open Wiring Notes
- Admin linked opens (`open_patient`, `open_chart`, `open_recommendation`, `open_care_order`) now edit the current message into a linked object panel and include Back callback to reopen booking card.
- Doctor linked opens (`open_patient`, `open_chart`, `open_recommendation`, `open_care_order`) now follow the same real navigable panel pattern with Back callback.
- Removed primary reliance on `/recommendations ...` and `/care_orders ...` textual shortcut responses in booking linked-open callbacks.

## 8. Local-Time / Label Resolution Notes
- Booking flow card builder now resolves timezone by: branch timezone -> clinic timezone -> `UTC` fallback.
- Booking card datetime labels now render in resolved local timezone instead of forced UTC for the affected paths.
- Snapshot builder centralizes resolved labels for doctor/service/branch and supports patient label injection by context.

## 9. Legacy Path Demotion Notes
- `book:*` remains wizard/session progression only.
- `mybk:*` remains compatibility tail for stale already-delivered patient messages.
- Booking detail/control primary runtime path remains `c2|` callback payloads + unified booking shell rendering.

## 10. Files Added
- docs/report/PR_UC3B_REPORT.md

## 11. Files Modified
- app/application/booking/telegram_flow.py
- app/interfaces/bots/patient/router.py
- app/interfaces/bots/admin/router.py
- app/interfaces/bots/doctor/router.py
- tests/test_booking_patient_flow_stack3c1.py

## 12. Commands Run
- `rg --files -g 'AGENTS.md'`
- `rg --files README.md docs/...`
- `sed -n ... docs/report/PR_UC3A_REPORT.md`
- `sed -n ... docs/16-4_booking_card_profile.md`
- `sed -n ... docs/16-2_card_callback_contract.md`
- `sed -n ... docs/16-5_card_runtime_state_and_redis_rules.md`
- `rg -n ... app/interfaces/bots/*/router.py app/application/booking/telegram_flow.py`
- `python -m py_compile app/application/booking/telegram_flow.py app/interfaces/bots/patient/router.py app/interfaces/bots/admin/router.py app/interfaces/bots/doctor/router.py tests/test_booking_patient_flow_stack3c1.py`
- `pytest -q tests/test_booking_card_runtime_integration_uc3a.py tests/test_booking_patient_flow_stack3c1.py`

## 13. Test Results
- `tests/test_booking_card_runtime_integration_uc3a.py`: pass
- `tests/test_booking_patient_flow_stack3c1.py`: pass

## 14. Remaining Known Limitations
- Admin linked-open panels for recommendation/care-order are navigable panels but remain lightweight summary stubs, not full dedicated card profiles yet.
- Patient role booking card remains focused on own-booking operations and does not expose linked-open actions by design.
- Legacy callback compatibility handlers (`mybk:*`) still exist for stale-message continuity.

## 15. Deviations From Docs (if any)
- No intentional architecture-level deviation. Linked open targets for admin recommendation/care order remain lightweight navigable panels rather than full profile cards in this bounded PR scope.

## 16. Readiness Assessment for next PR
- Booking card is now materially closer to true primary runtime object behavior across patient/admin/doctor paths.
- Remaining next-step depth is to replace lightweight linked target panels with richer linked object cards where product contract requires.
