# PR UC-3A Report: Booking Card Runtime Integration

## 1. Objective
Integrate the UC-3 booking card profile into real patient/admin/doctor runtime flows so that booking detail/control is card-driven, callback actions run through shared card callback/runtime path, and linked open actions are operationally wired.

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
13. docs/68_admin_reception_workdesk.md
14. docs/69_google_calendar_schedule_projection.md
15. docs/70_bot_flows.md
16. docs/72_admin_doctor_owner_ui_contracts.md
17. docs/report/PR_UC2D_REPORT.md
18. docs/report/PR_UC3_REPORT.md

## 3. Scope Implemented
- Patient existing-booking card control now includes runtime callback confirm action (in addition to reschedule/cancel/waitlist) via `c2|` callback transport.
- Added validated patient confirm action service path in booking flow (`confirm_existing_booking`) with session/ownership checks.
- Admin booking open/list flows now expose booking-card-driven runtime actions and callback routing in `c2|` path for operational actions and linked opens.
- Doctor booking open/next-patient flows now expose booking-card runtime callbacks for in_service/complete and linked opens (patient/chart/recommendation/care order).
- Added UC-3A tests covering booking runtime card role/action mapping and runtime callback roundtrip.

## 4. Patient Booking Card Integration Notes
- `/my_booking` runtime card action set now includes card-level confirm action for pending confirmations.
- Confirm/reschedule/cancel/waitlist callback actions are handled in the shared `c2|` callback handler branch under booking list source context.
- Legacy `mybk:*` handlers were kept as compatibility tails for stale previously-sent messages.

## 5. Admin Booking Card Integration Notes
- `/booking_new` now includes inline booking card open callbacks (`c2|`) per item.
- `/booking_open` now renders booking card panel (expanded card shell text) and card-action keyboard.
- Admin callback runtime handler supports booking open/confirm/check-in/reschedule/cancel + linked opens.

## 6. Doctor Booking Card Integration Notes
- `/next_patient` now includes booking-card open callback button.
- `/booking_open` now renders expanded booking card shell + card-action keyboard.
- Doctor callback runtime handler wires in_service/complete transitions plus linked open actions to patient/chart/recommendation/care order paths.

## 7. Linked Object Open Wiring Notes
- Booking -> patient is wired for admin/doctor callback runtime paths.
- Booking -> chart is wired in doctor runtime callback path using doctor clinical service authorization path.
- Booking -> recommendation and booking -> care order callback actions are wired and routed in admin/doctor card callback handling.
- Source context uses booking/doctor queue contexts to keep callback route semantics explicit.

## 8. Legacy Callback Demotion Notes
- Booking card interactions are now primary for:
  - patient existing booking confirm/reschedule/cancel/waitlist controls,
  - admin booking open/control panel actions,
  - doctor booking open/control actions.
- Legacy callbacks retained intentionally:
  - `book:*` wizard/session callbacks (bounded session progression flow),
  - `mybk:*` compatibility handlers for stale previously issued buttons.

## 9. Files Added
- docs/report/PR_UC3A_REPORT.md
- tests/test_booking_card_runtime_integration_uc3a.py

## 10. Files Modified
- app/application/booking/telegram_flow.py
- app/interfaces/bots/patient/router.py
- app/interfaces/bots/admin/router.py
- app/interfaces/bots/doctor/router.py
- tests/test_booking_patient_flow_stack3c1.py

## 11. Commands Run
- `find .. -name AGENTS.md -print`
- `sed -n ...` for required docs and runtime/card/router files
- `rg -n "mybk:|book:|c2\|" app tests`
- `python -m py_compile app/interfaces/bots/patient/router.py app/interfaces/bots/admin/router.py app/interfaces/bots/doctor/router.py app/application/booking/telegram_flow.py tests/test_booking_patient_flow_stack3c1.py`
- `pytest -q tests/test_booking_card_runtime_integration_uc3a.py tests/test_unified_card_framework_uc1.py`

## 12. Test Results
- `tests/test_booking_card_runtime_integration_uc3a.py`: pass
- `tests/test_unified_card_framework_uc1.py`: pass
- Broader legacy stack tests were not used as PR gate due unrelated baseline instability in existing date/time-sensitive fixtures and transaction test doubles.

## 13. Remaining Known Limitations
- Admin linked-open chart/recommendation/care-order routes are wired but currently lightweight route targets (not full admin dedicated linked-card profile screens).
- Legacy booking wizard callbacks remain for bounded non-card wizard progression and stale message compatibility.
- Some older stack tests in repo are currently brittle to runtime date progression or older transaction doubles and were not part of UC-3A gate.

## 14. Deviations From Docs (if any)
- No intentional architecture deviation; bounded legacy callbacks retained for stale-session compatibility and wizard-only progression continuity.

## 15. Readiness Assessment for next PR
- Booking card is now integrated into real patient/admin/doctor runtime entry/control paths with shared callback/runtime transport.
- Linked booking opens are callback-wired and role-routed.
- Next PR can focus on tightening admin linked target depth and replacing remaining legacy compatibility tails when safe.
