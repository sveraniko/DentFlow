# PAT-006 audit — Patient reminder acknowledgement flow (2026-04-21)

## 1. Executive verdict

**Verdict: Partial.**

PAT-006 is **not missing**: reminder `ack` exists in runtime, is delivered on specific reminder types (`booking_previsit`, `booking_day_of`, `booking_next_visit_recall`), is handled transactionally, marks the reminder as `acknowledged`, and now hands off to canonical patient booking continuity panel on accepted callback. However, PAT-006 is still **not fully closed/coherent** as a product scenario because runtime semantics of `ack` are narrow and slightly mixed: it mostly records reminder acknowledgement (non-destructive), does not mutate booking status, does not explicitly alter future reminder plan, and relies on generic outcome copy that may read close to “confirmation” unless product semantics are explicitly frozen. In short: implementation is real and safe, but scenario closure-level semantics/policy and explicit acceptance framing are incomplete.

**Final recommendation.**

Treat PAT-006 as a bounded closure wave (A6), not a redesign. Keep the current reminder action transaction model, callback integrity checks, and PAT-A3 continuity handoff. Close the remaining gap by explicitly codifying `ack` product semantics as distinct from attendance confirmation, adding targeted reminder-ack continuity/semantics regression coverage, and tightening patient-facing copy/visibility rules (what happens after first `ack`, and whether any future reminder behavior is intentionally affected).

---

## 2. Current real flow

### 2.1 Current behavior (runtime truth)

1. **Reminder is delivered from Communication layer**
   - Reminder jobs are created/planned in communication (`communication.reminder_jobs`) and delivered by `ReminderDeliveryService`.
   - Message text is rendered with reminder context + localized summary.
   - Action buttons are selected by reminder type.

2. **`ack` action availability**
   - `ack` is available for reminder types:
     - `booking_previsit`
     - `booking_day_of`
     - `booking_next_visit_recall`
   - For confirmation-oriented reminders (`booking_confirmation`, `booking_no_response_followup`), actions are `confirm/reschedule/cancel` (no `ack`).

3. **How patient acknowledges a reminder**
   - Patient taps inline callback `rem:ack:<reminder_id>` in the reminder message.
   - `patient/router.py::reminder_action_callback` validates payload shape/action and calls:
     - `ReminderActionService.handle_action(reminder_id=..., action="ack", provider_message_id=...)`.

4. **What `ack` does in service layer**
   - Service requires reminder to be in `sent` state.
   - Service validates provider message binding against `communication.message_deliveries` (`delivery_status='sent'`) when message id is present.
   - On success, service marks reminder `status='acknowledged'` + `acknowledged_at`, returns accepted outcome `reason='acknowledged'`.
   - No booking status mutation is performed for `ack`.

5. **What patient sees after accepted `ack`**
   - Reminder keyboard is best-effort cleared.
   - Router calls `_handoff_reminder_action_to_booking_panel(...)`.
   - Patient receives a fresh message with localized acknowledgement header (`patient.reminder.action.outcome.acknowledged`, e.g., “Got it, thanks.”) plus canonical booking panel text and actions.
   - Flow state is normalized to `existing_booking_control` with a fresh bound session.

6. **State transitions / side effects / event records**
   - Reminder job: `sent -> acknowledged`.
   - Booking: unchanged by `ack`.
   - Reminder outbox event: infra transaction path appends `reminder.acknowledged` event when marking acknowledged in transaction repository.
   - No explicit reminder-plan rebuild/cancel is triggered by `ack`.

7. **Future reminder behavior after `ack`**
   - No direct `ack`-specific suppression logic is evidenced in `ReminderActionService`.
   - Future reminder behavior therefore remains policy/relevance driven by normal planning/delivery logic unless changed by other booking transitions.

8. **Stale/invalid safety**
   - If reminder is already terminal (`acknowledged/canceled/failed/expired`), callback returns stale outcome.
   - If provider message id mismatches, callback is invalid.
   - Router surfaces bounded stale/invalid localized alerts and does not hand off.

### 2.2 Target-state vs current-state

- Some narrative docs/report language can read as if reminder acknowledgement is broadly “implemented/closed.”
- Runtime is strong but still limited semantically: `ack` is currently “received/understood” acknowledgment and continuity handoff, **not** attendance confirmation and not explicit reminder-policy suppression.
- Therefore target-state closure for PAT-006 should explicitly define and test:
  - distinction from `confirm attendance`,
  - whether `ack` changes future reminder behavior,
  - post-ack UX rules (button state/visibility and copy clarity).

---

## 3. Evidence map

| Flow segment | Evidence in code | Evidence in tests | Evidence in docs | Status | Notes |
|---|---|---|---|---|---|
| reminder delivery entry | `app/application/communication/delivery.py` (`deliver_due_reminders`, `render_booking_reminder_message`) | `tests/test_reminder_actions_stack4b2.py` rendering assertions | `booking_docs/10_booking_flow_dental.md`, `booking_docs/50_booking_telegram_ui_contract.md` | Implemented | Reminder message + CTA entry is real runtime behavior. |
| ack action availability | `delivery.py::_build_actions` maps previsit/day-of/next_visit to `ack` | `test_rendering_actions_and_context_for_confirmation_and_ack` | scenario/docs describe reminder actions generally | Implemented | `ack` intentionally separated by reminder type from `confirm`. |
| ack callback handling | `app/interfaces/bots/patient/router.py::reminder_action_callback`; `app/application/communication/actions.py::handle_action` | `tests/test_reminder_actions_stack4b2.py::test_acknowledge_marks_reminder_and_duplicate_is_stale` | PAT-A3/PAT-A5 reports mention accepted reminder action matrix | Implemented | Real transactional callback path exists. |
| post-click patient feedback | router accepted path clears markup + handoff helper + localized outcome key | `tests/test_patient_reminder_handoff_pat_a3_1a.py` (`ack` in accepted matrix) | PAT-A3 reports describe canonical continuity | Implemented | No longer toast-only; shows canonical booking continuity. |
| canonical panel continuity after ack | `_handoff_reminder_action_to_booking_panel` starts existing booking control + renders booking panel | `tests/test_patient_reminder_handoff_pat_a3_1a.py` verifies `booking_mode` and active panel | PAT-A3 1A/1B reports | Implemented | PAT-A3 continuity behavior applies to `ack`. |
| booking state semantics | `actions.py` `ack` branch marks reminder only; no booking orchestration call | `tests/test_reminder_actions_stack4b2.py` ack test does not change booking status | PAT-003/PAT-005 audits distinguish booking-mutating actions | Implemented | `ack` is non-booking-mutating in current runtime. |
| reminder-side semantics | `mark_reminder_acknowledged_in_transaction`; no reschedule/cancel-plan call in `ack` branch | `tests/test_reminder_actions_stack4b2.py` status becomes `acknowledged` | docs mention acknowledgement but not strict suppression policy | Partial | Acknowledgement semantics are clear; downstream suppression policy is not explicitly codified as PAT-006 rule. |
| distinction from confirm-attendance | `actions.py`: `confirm` calls booking confirm orchestration; `ack` does not | `tests/test_reminder_actions_stack4b2.py` confirm mutates booking to confirmed, ack does not | booking docs list separate CTA concepts | Implemented | Runtime proves distinct behavior, not duplicate. |
| stale callback protection | terminal reminder stale check + message-id integrity check + router stale/invalid alerts | `tests/test_reminder_actions_stack4b2.py::test_invalid_or_stale_integrity_cases_are_safe` | `booking_docs/40_booking_state_machine.md` stale callback rule | Implemented | Strong bounded stale/manual safety. |
| human-readable patient-facing ack copy | locale keys: `reminder.action.ack`, `patient.reminder.action.outcome.acknowledged` | handoff tests validate user-facing headers | `docs/17_localization_and_i18n.md` i18n discipline | Partial | Copy exists/localized, but product-specific “ack vs confirm” wording policy is not formally frozen for PAT-006 closure. |

---

## 4. Gaps that block PAT-006 closure

### Gap 1 — Explicit product semantics for `ack` are not fully codified as acceptance contract
- **Severity:** blocker
- **Evidence:** runtime clearly treats `ack` as reminder acknowledgement only, but scenario-level closure criteria in docs do not explicitly lock this as product intent vs “weak attendance confirmation.”
- **Why it matters:** PAT-006 asks whether `ack` is distinct or duplicate. Runtime says distinct, but closure needs explicit product decision + acceptance criteria to prevent drift.
- **Type:** mixed (product-contract + runtime acceptance framing)

### Gap 2 — Reminder-side post-ack policy is implicit, not explicit
- **Severity:** major
- **Evidence:** `ack` branch only acknowledges reminder; no explicit suppression/adjustment contract for subsequent reminders is encoded as PAT-006 behavior.
- **Why it matters:** PAT-006 includes reminder-side effects. Current behavior is effectively “no direct extra suppression,” but this is inferred from code, not made an explicit accepted policy.
- **Type:** mixed

### Gap 3 — No PAT-006-focused acceptance-proof test slice explicitly locking all ack semantics together
- **Severity:** medium
- **Evidence:** relevant behavior is spread across existing reminder and handoff tests; no dedicated PAT-006 checklist-style test contract currently names/locks all required seams.
- **Why it matters:** scenario may regress silently (e.g., copy, continuity, or accidental booking mutation) without a focused closure test bundle.
- **Type:** runtime-only (test coverage shape)

---

## 5. Things that are already good enough

- Reminder `ack` callback exists and is production-wired through router + service.
- `ack` is transactionally safe and idempotent at user level (duplicate becomes stale).
- Provider message binding integrity is enforced (prevents arbitrary callback spoof/mismatch).
- `ack` is operationally distinct from `confirm attendance` in runtime semantics.
- Canonical patient booking continuity after accepted `ack` is present (PAT-A3 carryforward).
- Stale/invalid reminder callback handling is bounded and localized.
- Localized patient-facing ack labels and outcome headers are already present in `en` and `ru`.

---

## 6. Minimal implementation stack to close PAT-006

### PAT-A6-1 — Freeze and encode `ack` product semantics
- **Objective:** Make `ack` semantics explicit and non-ambiguous in scenario acceptance contract.
- **Exact scope:**
  - clarify PAT-006 acceptance text: `ack` = acknowledgement only, distinct from `confirm attendance`;
  - explicitly state whether `ack` should or should not alter future reminder chain.
- **Non-goals:** no reminder engine redesign; no booking state model changes.
- **Files likely touched:**
  - `docs/71_role_scenarios_and_acceptance.md`
  - `booking_docs/10_booking_flow_dental.md` (action-required wording)
  - `booking_docs/50_booking_telegram_ui_contract.md` (CTA semantics)
- **Tests likely touched/added:** none required in this PR if docs-only.
- **Migrations needed?** no
- **Acceptance criteria:** PAT-006 docs unambiguously define `ack` vs `confirm` and expected reminder-side policy.

### PAT-A6-2 — Targeted runtime hardening for post-ack policy (only if product decision requires)
- **Objective:** Implement only the decided post-ack reminder behavior (e.g., keep unaffected or suppress selected follow-up type).
- **Exact scope:**
  - if “unaffected” is chosen: codify via comments/guard tests only;
  - if suppression is chosen: add bounded rule in communication reminder action/relevance path.
- **Non-goals:** no broad planner redesign, no new reminder type taxonomy.
- **Files likely touched:**
  - `app/application/communication/actions.py`
  - possibly `app/application/communication/reminders.py` or runtime integrity evaluator (if suppression chosen)
- **Tests likely touched/added:**
  - `tests/test_reminder_actions_stack4b2.py`
  - possibly one reminder delivery/integrity test for suppression behavior.
- **Migrations needed?** no
- **Acceptance criteria:** runtime behavior after `ack` matches explicit product decision and is regression-tested.

### PAT-A6-3 — PAT-006 closure-proof regression bundle
- **Objective:** Add scenario-targeted tests that lock the full PAT-006 checklist.
- **Exact scope:** test-only, bounded to reminder ack semantics and continuity.
- **Non-goals:** no router redesign, no new flows.
- **Files likely touched:**
  - `tests/test_reminder_actions_stack4b2.py`
  - `tests/test_patient_reminder_handoff_pat_a3_1a.py`
  - optional tiny new `tests/test_patient_reminder_ack_pat_a6.py` if cleaner.
- **Tests likely touched/added:**
  - ack availability by reminder type
  - ack non-booking-mutating guarantee
  - ack accepted continuity to canonical panel
  - stale/mismatch rejection
  - post-ack policy assertion (as decided in A6-1)
- **Migrations needed?** no
- **Acceptance criteria:** one targeted test pack proves PAT-006 end-to-end behavior and protects from semantic regressions.

---

## 7. Product decisions requiring explicit human confirmation

1. Should `ack` remain strictly distinct from `confirm attendance` (recommended: **yes**)?
2. After `ack`, should future reminders remain unaffected (recommended default), or should any specific follow-up reminders be suppressed?
3. Should accepted `ack` always hand off to canonical booking panel continuity (recommended: **yes**, retain PAT-A3 behavior)?
4. Should `ack` remain one-tap with no intermediate prompt (recommended: **yes**, non-destructive)?
5. Should the original reminder `ack` button remain visible after tap, be cleared (current behavior), or be replaced by passive “acknowledged” state?

---

## 8. Final closure checklist

- [ ] Reminder for applicable types shows `ack` CTA.
- [ ] `ack` callback validates reminder status and provider message binding.
- [ ] `ack` marks reminder as acknowledged exactly once; duplicate taps are stale-safe.
- [ ] `ack` does **not** mutate booking status.
- [ ] Accepted `ack` gives explicit patient feedback and canonical booking-panel continuity.
- [ ] Stale/invalid/mismatched callbacks are bounded and localized.
- [ ] Reminder-side post-ack policy is explicitly documented and tested.
- [ ] `ack` semantics are explicitly distinct from `confirm attendance` in docs and tests.

---

## Audit execution note

Targeted tests were executable in this environment and were run for directly relevant seams:

- `pytest -q tests/test_reminder_actions_stack4b2.py tests/test_patient_reminder_handoff_pat_a3_1a.py tests/test_booking_patient_flow_stack3c1.py tests/test_booking_orchestration.py`
- Result: `61 passed`.
