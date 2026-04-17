# PR Stack 4C1A Report — Recovery Policy Wiring Integrity

## 1. Objective
Implement a narrow runtime/policy-integrity fix so reminder recovery and no-response escalation use persisted clinic-scoped policy at runtime, eliminate hardcoded `clinic_id="default"` resolution in recovery logic, and add regression tests for this failure mode.

## 2. Docs Read
1. `README.md`
2. `docs/18_development_rules_and_baseline.md`
3. `docs/10_architecture.md`
4. `docs/12_repo_structure_and_code_map.md`
5. `docs/23_policy_and_configuration_model.md`
6. `docs/30_data_model.md`
7. `docs/35_event_catalog.md`
8. `docs/80_integrations_and_infra.md`
9. `docs/85_security_and_privacy.md`
10. `docs/90_pr_plan.md`
11. `docs/report/PR_STACK_4A_REPORT.md`
12. `docs/report/PR_STACK_4A1_REPORT.md`
13. `docs/report/PR_STACK_4B1_REPORT.md`
14. `docs/report/PR_STACK_4B2_REPORT.md`
15. `docs/report/PR_STACK_4B2A_REPORT.md`
16. `docs/report/PR_STACK_4C1_REPORT.md`
17. `booking_docs/*` (targeted grep/read for reminder ownership and clinic policy implications)

## 3. Scope Implemented
- Worker bootstrap now loads policy from DB (`DbPolicyRepository`) instead of `InMemoryPolicyRepository`.
- Recovery service policy resolution now uses each reminder's real `clinic_id` for stale/retry/no-response policy keys.
- Hardcoded `clinic_id="default"` was removed from recovery policy reads.
- Recovery scans now fetch broad candidate sets and apply clinic-specific thresholds in service logic to keep per-clinic policy evaluation coherent.
- Added regression tests for worker wiring and clinic-aware recovery policy behavior.

## 4. Worker Policy Wiring Fix
- Updated `app/worker.py` to load `policy_repository = await DbPolicyRepository.load(settings.db)` and construct `PolicyResolver(policy_repository)`.
- This removes production-path dependence on an empty in-memory policy repository.

## 5. Clinic-Aware Recovery Policy Strategy
- `recover_stale_queued_reminders`:
  - scans queued reminders with a broad lower bound (`now - 1 minute`),
  - resolves `communication.reminder_stale_queued_after_minutes` per reminder `clinic_id`,
  - resolves `communication.reminder_retry_max_attempts` per reminder `clinic_id`,
  - applies stale/retry logic reminder-by-reminder against clinic policy.
- `detect_confirmation_no_response`:
  - scans sent confirmation reminders with a broad lower bound (`now - 1 minute`),
  - resolves `booking.non_response_escalation_enabled` per reminder `clinic_id`,
  - resolves `booking.non_response_escalation_after_minutes` per reminder `clinic_id`,
  - escalates only when clinic policy enables and threshold is met.
- Policy value lookups are cached per clinic per pass to keep behavior explicit and efficient.

## 6. Files Added
- `docs/report/PR_STACK_4C1A_REPORT.md`

## 7. Files Modified
- `app/worker.py`
- `app/application/communication/recovery.py`
- `tests/test_worker.py`
- `tests/test_reminder_recovery_stack4c1.py`

## 8. Commands Run
- `rg --files -g 'AGENTS.md'`
- `find .. -name AGENTS.md -print`
- `rg -n "ReminderRecoveryService|PolicyResolver|InMemoryPolicyRepository|worker|non_response|stale_queued|retry_max" app tests -S`
- `sed -n '1,120p' ...` across required docs/reports
- `rg -n "reminder|policy|clinic_id|escalation|non_response|recovery" booking_docs -S`
- `pytest -q tests/test_reminder_recovery_stack4c1.py tests/test_worker.py tests/test_runtime_wiring.py`

## 9. Test Results
- `tests/test_reminder_recovery_stack4c1.py`: pass
- `tests/test_worker.py`: pass
- `tests/test_runtime_wiring.py`: pass

## 10. Remaining Known Limitations
- Recovery repository query APIs still accept a single timestamp cutoff, so service performs clinic-specific threshold filtering after broad candidate retrieval.
- This PR does not redesign repository query shape or introduce multi-pass grouping SQL; it keeps the fix small and explicit.

## 11. Deviations From Docs (if any)
- No intentional architecture/doc deviations.

## 12. Booking-Base-v1 Readiness Assessment
For the 4C1A scope, recovery runtime now honors persisted clinic policy in worker and service paths instead of hardcoded/default-only resolution. This addresses the targeted integrity gap required before declaring Booking ready for `booking-base-v1` on recovery policy wiring.
