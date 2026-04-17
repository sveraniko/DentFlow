# PR Stack 6A Report — Doctor Operational Surface

## 1. Objective
Implement a doctor-first operational layer (queue, next patient, compact booking/patient cards, and minimal booking-state actions) without introducing clinical charting.

## 2. Docs Read
- README.md
- docs/18_development_rules_and_baseline.md
- docs/10_architecture.md
- docs/12_repo_structure_and_code_map.md
- docs/15_ui_ux_and_product_rules.md
- docs/17_localization_and_i18n.md
- docs/25_state_machines.md
- docs/20_domain_model.md
- docs/30_data_model.md
- docs/22_access_and_identity_model.md
- docs/23_policy_and_configuration_model.md
- docs/40_search_model.md
- docs/70_bot_flows.md
- docs/72_admin_doctor_owner_ui_contracts.md
- docs/80_integrations_and_infra.md
- docs/85_security_and_privacy.md
- docs/90_pr_plan.md
- docs/95_testing_and_launch.md
- docs/report/PR_STACK_5A1_REPORT.md
- docs/report/PR_STACK_5A1A_REPORT.md
- docs/report/PR_STACK_5B_REPORT.md
- docs/report/PR_STACK_5B1_REPORT.md

## 3. Precedence Decisions
- Preserved booking lifecycle truth in canonical booking services; no direct state writes in handlers.
- Enforced explicit doctor identity mapping via `access_identity.doctor_profiles` and safe failure keys.
- Kept doctor UI operational/compact; no charting fields introduced.

## 4. Doctor Surface Scope Implemented
- Added doctor home command: `/doctor_home`.
- Added doctor operational commands:
  - `/today_queue`
  - `/next_patient`
  - `/booking_open <booking_id>`
  - `/patient_open <patient_id>`
  - `/booking_action <booking_id> <checked_in|in_service|completed>`

## 5. Queue / Next-Patient Strategy
- Queue = today UTC window bookings for resolved doctor profile in live operational statuses.
- Sorted ascending by scheduled start time.
- Next patient = first future queue item else first queue item if already started.

## 6. Doctor Action Scope and Transition Rules
- Implemented actions: `checked_in`, `in_service`, `completed`.
- `checked_in` + `in_service` go through canonical `BookingStateService.transition_booking`.
- `completed` goes through canonical orchestration `complete_booking`.
- Invalid transitions return safe invalid-state response.

## 7. Identity / Doctor Mapping Handling
- Added `AccessResolver.resolve_doctor_id` and DB loading of `doctor_profiles`.
- Safe localized failures for:
  - missing doctor mapping
  - ambiguous doctor mapping
  - unbound or wrong role

## 8. Search/Voice Integration Notes
- Existing doctor search/voice handlers retained.
- Added operational bridge: `id:<patient_id>` query path returns quick-open hint to `/patient_open`.
- Voice remains retrieval-only; no booking mutation added in voice path.

## 9. Files Added
- `app/application/doctor/operations.py`
- `app/application/doctor/__init__.py`
- `tests/test_doctor_operational_stack6a.py`
- `docs/report/PR_STACK_6A_REPORT.md`

## 10. Files Modified
- `app/application/access.py`
- `app/infrastructure/db/repositories.py`
- `app/interfaces/bots/doctor/router.py`
- `app/bootstrap/runtime.py`
- `locales/en.json`
- `locales/ru.json`

## 11. Commands Run
- `rg --files -g 'AGENTS.md'`
- `find .. -maxdepth 3 -name AGENTS.md`
- `rg -n ...` doc/code discovery commands
- `pytest -q tests/test_doctor_operational_stack6a.py tests/test_search_ui_stack5a1a.py tests/test_voice_search_stack5b.py`

## 12. Test Results
- New Stack 6A behavioral tests added and passed.
- Prior search/voice tests for stack 5A/5B still pass.

## 13. Known Limitations / Explicit Non-Goals
- No clinical charting, encounters, diagnosis, treatment plans, or clinical notes.
- No doctor-side cancel/reschedule/no-show actions in this stack.
- Queue window currently uses UTC day boundaries.

## 14. Deviations From Docs (if any)
- None intentional.

## 15. Readiness Assessment for Stack 7A
- Ready to layer chart-aware workflows in Stack 7A on top of stable doctor operational queue/detail/actions, with identity-safe doctor mapping now in place.
