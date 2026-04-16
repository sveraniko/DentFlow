# PR Stack 3C2A Report — Existing Booking Identity Integrity

## 1. Objective

Deliver a narrow integrity fix for existing-booking control flow by:
- preventing `/my_booking` no-match from creating canonical patients,
- splitting new-booking and existing-booking contact-resolution semantics,
- binding existing-booking control actions to the active resolved control session/patient,
- rejecting stale/foreign callbacks safely.

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
17. booking_docs/10_booking_flow_dental.md  
18. booking_docs/50_booking_telegram_ui_contract.md  
19. booking_docs/booking_test_scenarios.md

## 3. Scope Implemented

- Introduced explicit split between:
  - new-booking contact resolution (`resolve_patient_for_new_booking_contact`), and
  - existing-booking lookup resolution (`resolve_patient_for_existing_booking_contact`).
- Updated existing-booking contact flow to preserve no-match as no-match (no patient create/attach).
- Added control-action validation helper for existing-booking actions.
- Bound existing-booking action callbacks to session + booking context.
- Updated callbacks to carry both `session_id` and `booking_id`.
- Added targeted tests for no-match pollution prevention and action integrity.

## 4. New Booking vs Existing Booking Resolution Split

### New booking (`/book`)
- exact match: attach existing canonical patient.
- no match: create minimal canonical patient and attach.
- ambiguous: escalate safely.

### Existing booking (`/my_booking`)
- exact match: attach resolved canonical patient and continue.
- no match: return no-match outcome without creating canonical patient.
- ambiguous: escalate safely.

Implementation detail:
- `resolve_patient_for_new_booking_contact` preserves create-on-no-match semantics for new booking.
- `resolve_patient_for_existing_booking_contact` returns typed `no_match` outcome with no create/attach path.

## 5. Existing-Booking No-Match Behavior

Current behavior in this PR:
- `/my_booking` no-match returns `BookingControlResolutionResult(kind="no_match")`.
- no call to canonical patient creator occurs in this path.
- session `resolved_patient_id` remains unset (`None`) for no-match path.
- patient registry is not mutated by this no-match flow.

Chosen session behavior:
- keep active existing-booking control session alive for UX continuity,
- keep it unresolved (no synthetic/phantom patient binding).

## 6. Control Action Integrity Strategy

Implemented helper:
- `validate_existing_booking_control_action(...)`.

Validation checks:
1. active session exists for `(clinic_id, telegram_user_id)`;
2. callback session matches latest active session;
3. latest session is `existing_booking_control` route;
4. session has resolved patient;
5. booking exists;
6. booking belongs to resolved patient;
7. booking status is eligible for requested action (where required).

Action methods now depend on that helper:
- `request_reschedule(...)`
- `cancel_booking(...)`
- `join_earlier_slot_waitlist(...)`

Callback contract hardening:
- existing-booking callback payloads now include `session_id + booking_id`.
- stale/mismatched callbacks fail safely and no mutation executes.

## 7. Files Added

- `docs/report/PR_STACK_3C2A_REPORT.md`

## 8. Files Modified

- `app/application/booking/telegram_flow.py`
- `app/interfaces/bots/patient/router.py`
- `tests/test_booking_patient_flow_stack3c1.py`

## 9. Commands Run

- `pytest -q tests/test_booking_patient_flow_stack3c1.py tests/test_booking_orchestration.py tests/test_runtime_wiring.py`

## 10. Test Results

- Pass: `24 passed in 6.12s`

## 11. Remaining Known Limitations

- Existing-booking action rejection currently maps to generic invalid-state localized feedback; finer-grained user text can be added later.
- Integrity validation currently treats latest active session as authoritative; this matches existing callback-stale policy.

## 12. Deviations From Docs (if any)

- None intentional for Stack 3C2A scope.

## 13. Readiness Assessment for next stack

- Ready to proceed.
- `/my_booking` no-match no longer creates/attaches phantom patients.
- Existing-booking control mutations are no longer allowed by naked `booking_id`; session/patient binding is now required.
