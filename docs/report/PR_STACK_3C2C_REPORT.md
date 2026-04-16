# PR Stack 3C2C Report — Booking Route-Type Session Isolation

## 1. Objective

Deliver a narrow route/session-integrity fix so booking route families do not cross-resume:
- `/book` must not resume `existing_booking_control` sessions.
- `/my_booking` must not depend on `service_first` sessions.
- Route-family resume behavior must be explicit and test-covered.

## 2. Docs Read

1. README.md  
2. docs/18_development_rules_and_baseline.md  
3. docs/10_architecture.md  
4. docs/12_repo_structure_and_code_map.md  
5. docs/15_ui_ux_and_product_rules.md  
6. docs/17_localization_and_i18n.md  
7. docs/25_state_machines.md  
8. docs/20_domain_model.md  
9. docs/30_data_model.md  
10. docs/70_bot_flows.md  
11. docs/72_admin_doctor_owner_ui_contracts.md  
12. docs/85_security_and_privacy.md  
13. docs/90_pr_plan.md  
14. docs/report/PR_STACK_3C1_REPORT.md  
15. docs/report/PR_STACK_3C2_REPORT.md  
16. docs/report/PR_STACK_3C2A_REPORT.md  
17. docs/report/PR_STACK_3C2B_REPORT.md  
18. booking_docs/10_booking_flow_dental.md  
19. booking_docs/50_booking_telegram_ui_contract.md  
20. booking_docs/booking_test_scenarios.md

## 3. Scope Implemented

- Made active-session resume route-family aware in booking patient flow service.
- Isolated `/book` and `/my_booking` session reuse semantics by route type.
- Hardened existing-booking action validation to resolve "latest" within existing-booking route family only.
- Added targeted contamination tests for:
  - existing -> book,
  - book -> existing,
  - coexistence + route-specific resume.

## 4. Route-Aware Resume Strategy

Implemented explicit route-family filtering helpers:
- `NEW_BOOKING_ROUTE_TYPES = {"service_first"}`
- `EXISTING_BOOKING_CONTROL_ROUTE_TYPES = {"existing_booking_control"}`

Resume policy:
- `/book` (`start_or_resume_session`) resumes only latest active session whose `route_type` is in `NEW_BOOKING_ROUTE_TYPES`; otherwise starts a new `service_first` session.
- `/my_booking` (`start_or_resume_existing_booking_session`) resumes only latest active session whose `route_type` is in `EXISTING_BOOKING_CONTROL_ROUTE_TYPES`; otherwise starts a new `existing_booking_control` session.

Callback/session guard policy:
- Generic booking callback validation now checks latest active session within the allowed route family (defaulting to new-booking family).
- Existing-booking control action validation now resolves latest active session within existing-booking family before validating callback/session identity and booking ownership.

## 5. Cross-Route Isolation Behavior

When both route families exist for one Telegram user:
- `/book` resumes only `service_first` family session.
- `/my_booking` resumes only `existing_booking_control` family session.
- A session from one family does not hijack entry/resume semantics of the other family.

## 6. Files Added

- `docs/report/PR_STACK_3C2C_REPORT.md`

## 7. Files Modified

- `app/application/booking/telegram_flow.py`
- `tests/test_booking_patient_flow_stack3c1.py`

## 8. Commands Run

- `pytest -q tests/test_booking_patient_flow_stack3c1.py`
- `pytest -q tests/test_booking_orchestration.py tests/test_runtime_wiring.py`

## 9. Test Results

- Pass: `13 passed in 0.19s`
- Pass: `16 passed in 4.14s`

## 10. Remaining Known Limitations

- New-booking route family is currently represented by `service_first` only; if additional new-booking route types are introduced later, they must be added to the explicit route-family constant.
- Existing generic stale-callback user messaging remains intentionally compact and unchanged in this stack.

## 11. Deviations From Docs (if any)

- None intentional for Stack 3C2C scope.

## 12. Readiness Assessment for next stack

- Ready for next stack.
- Route-family session resume contamination between `/book` and `/my_booking` is now isolated and behaviorally test-covered.
