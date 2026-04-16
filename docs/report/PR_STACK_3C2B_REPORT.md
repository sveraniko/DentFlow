# PR Stack 3C2B Report — Existing Booking Session Identity Reset Integrity

## 1. Objective

Deliver a narrow identity/session-integrity fix for existing-booking control so that a new `/my_booking` lookup cannot retain stale resolved patient identity from a prior lookup/session.

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
10. docs/40_search_model.md  
11. docs/70_bot_flows.md  
12. docs/72_admin_doctor_owner_ui_contracts.md  
13. docs/85_security_and_privacy.md  
14. docs/90_pr_plan.md  
15. docs/report/PR_STACK_3C1_REPORT.md  
16. docs/report/PR_STACK_3C2_REPORT.md  
17. docs/report/PR_STACK_3C2A_REPORT.md  
18. booking_docs/10_booking_flow_dental.md  
19. booking_docs/50_booking_telegram_ui_contract.md  
20. booking_docs/booking_test_scenarios.md

## 3. Scope Implemented

- Hardened existing-booking control session identity semantics by rotating to a fresh control session for each new lookup attempt.
- Ensured no-match and ambiguous outcomes return/retain unresolved control context (`resolved_patient_id=None`) for the active lookup session.
- Preserved action-integrity validation behavior so old callbacks tied to older session IDs fail as stale/mismatched.
- Added transition tests for same Telegram user:
  - exact-match -> no-match
  - exact-match -> ambiguous

## 4. Chosen Session Identity Reset Strategy

### Option A — Fresh session strategy (implemented)

For every `resolve_existing_booking_by_contact(...)` invocation, the flow now starts a **new** `existing_booking_control` session before resolution.

Why this was chosen:
- Naturally invalidates old callback/session bindings (old callback carries old session_id).
- Guarantees active lookup context starts unresolved.
- Avoids accidental state carry-over in reused session rows.

## 5. Existing-Booking No-Match / Ambiguous Safety Behavior

- **no_match**: returns a no-match result with the new active control session unresolved (`resolved_patient_id` unset).
- **ambiguous_escalated**: escalates safely and keeps the active control session unresolved.
- In both paths, stale resolved identity from previous lookups cannot survive into the new active lookup context.

## 6. Control Action Integrity After Identity Change

Integrity is enforced by existing validation:
- action callback must target latest active session for `(clinic_id, telegram_user_id)`;
- callback session must match latest `existing_booking_control` session;
- session must contain resolved patient binding;
- booking must belong to that resolved patient.

After session rotation, prior callbacks are stale and fail validation.

## 7. Files Added

- `docs/report/PR_STACK_3C2B_REPORT.md`

## 8. Files Modified

- `app/application/booking/telegram_flow.py`
- `app/interfaces/bots/patient/router.py`
- `tests/test_booking_patient_flow_stack3c1.py`

## 9. Commands Run

- `pytest -q tests/test_booking_patient_flow_stack3c1.py`

## 10. Test Results

- Pass: `10 passed in 0.16s`

## 11. Remaining Known Limitations

- Existing-booking invalid-action feedback is still generic localized invalid-state messaging.
- This stack does not add richer explanatory stale-callback copy per failure reason.

## 12. Deviations From Docs (if any)

- None intentional for 3C2B scope.

## 13. Readiness Assessment for next stack

- **Ready** for next stack.
- Existing-booking control now avoids stale identity carry-over across new lookups and invalidates old action callbacks after lookup context changes.
