# PAT-005 audit — Patient cancel flow (2026-04-21)

## 1. Executive verdict

**Verdict: Implemented (with bounded UX gaps).**

PAT-005 is currently implemented as a **real patient self-service cancellation path**, not only a cancel-request capture. From both `/my_booking` booking controls and reminder CTA actions, patient cancel can drive canonical booking status transition to `canceled` via booking orchestration, with reminder plan cancellation, stale/session ownership guards, and patient-visible follow-up panel continuity. The runtime evidence shows cancellation mutates canonical booking state and records lifecycle artifacts (status history + outbox event), rather than only filing intent.

**Final recommendation.**
Treat PAT-005 as functionally closed at runtime semantics level, and run a narrowly scoped hardening wave only for UX/guard consistency and closure-proof coverage. Keep existing orchestration/reminder stack unchanged, and focus on: (a) consistent explicit confirm prompt behavior across all cancel entries, (b) compact patient copy polish for post-cancel clarity, and (c) targeted regression tests that lock current guarantees (true cancellation, reminder cancellation, continuity from reminder and `/my_booking`) without broad redesign.

---

## 2. Current real flow

### Current behavior (runtime truth)

1. **Patient enters existing booking context**
   - Entry points:
     - `/my_booking` command
     - `phome:my_booking` home callback
     - accepted reminder callbacks (`rem:cancel:<reminder_id>`)
   - `/my_booking` path can open directly through trusted patient identity shortcut, otherwise asks for contact lookup.

2. **Cancel action availability**
   - Existing-booking panel includes a cancel action button (`patient.booking.my.cancel`) that routes to runtime callback page `cancel_prompt`.
   - Reminder messages for `booking_confirmation`/`booking_no_response_followup` include `cancel` action button (`rem:cancel:<id>`).

3. **Confirmation prompt behavior**
   - `/my_booking` cancel path (including runtime-card callback path) shows explicit yes/no cancel prompt (`patient.booking.cancel.confirm`) before destructive action.
   - Reminder `cancel` action currently executes immediately through reminder action service; no extra in-router confirm prompt is shown in that path.

4. **What callback/service handles cancel**
   - `/my_booking`/booking-card path:
     - callback handlers route to `booking_flow.cancel_booking(...)`.
     - `BookingPatientFlowService.cancel_booking(...)` validates ownership, active session token, resolved patient match, and status eligibility.
   - Reminder path:
     - `reminder_action_callback` -> `ReminderActionService.handle_action(..., action="cancel")`.
     - service validates reminder actionability + optional provider message id + booking existence, then calls orchestration cancel in-transaction.

5. **What the system does after click**
   - On success, booking orchestration transitions booking -> `canceled` and cancels scheduled reminders for that booking (`booking_canceled` reason).
   - This records booking status history and emits `booking.canceled` outbox event via state transition service.

6. **What patient sees next**
   - `/my_booking` cancel: panel re-renders booking card text for now-canceled booking (same session context).
   - Reminder cancel: accepted reminder callback handoff renders a fresh canonical booking panel with a localized header (e.g., “Booking canceled.”) and current booking card context.

7. **Is booking really canceled?**
   - Yes. This is canonical booking cancellation (status mutation + lifecycle recording), not only intent capture.

8. **State changes/events recorded**
   - Booking status transition to `canceled`.
   - `canceled_at` timestamp set.
   - Booking status history row appended.
   - Outbox event `booking.canceled` emitted.
   - Reminder jobs for booking canceled (scheduled jobs canceled; already terminal reminders handled by relevance rules).

9. **Canonical booking-panel continuity**
   - Preserved after accepted reminder actions (including cancel) through explicit handoff to booking panel.
   - Preserved after `/my_booking` cancel through in-place panel re-render.

### Target-state behavior (if docs imply nicer flow)

- Narrative docs commonly imply a unified “cancel prompt -> confirm/abort -> update panel” model for cancel flow. Runtime currently provides this explicitly for `/my_booking`, but reminder cancel is **one-tap transactional cancel + handoff**, without a second in-router confirm prompt. If product wants strict destructive-confirm parity for reminder cancel, that is a target-state refinement, not current behavior.

---

## 3. Evidence map

| Flow segment | Evidence in code | Evidence in tests | Evidence in docs | Status | Notes |
|---|---|---|---|---|---|
| existing-booking cancel entry | `patient/router.py`: `/my_booking`, `phome:my_booking`, existing-booking lookup + panel render | `test_patient_existing_booking_shortcut_pat_a3_2.py` covers `/my_booking` + home callback parity/shortcut behavior | `docs/71...` PAT-005 entry | Implemented | Cancel path starts from real existing-booking context. |
| `/my_booking` cancel availability | `_build_patient_booking_controls_keyboard` always includes cancel action -> `cancel_prompt` | reminder handoff + flow tests exercise booking controls panel continuity; booking-flow tests cover cancel API | booking UI contracts include cancel action | Implemented | Button exists on patient booking control keyboard. |
| reminder cancel availability | `communication/delivery.py` action map includes cancel for confirmation/followup reminder types; callback format `rem:cancel:*` | `test_reminder_actions_stack4b2.py` verifies rendered actions include cancel and action acceptance mutates booking | booking docs reminder-action pattern includes cancel | Implemented | Reminder cancel exists and is wired transactionally. |
| cancel confirmation prompt | `cancel_prompt_by_runtime` + yes/no callbacks for booking-list runtime callbacks and legacy `mybk:*` callbacks | no dedicated PAT-005 test file for prompt branch itself found; indirect coverage through callback matrix | scenario docs expect prompt/confirm/abort | Partial | Prompt exists for `/my_booking`; reminder cancel has no extra confirm step. |
| cancel callback handling | router handlers call `booking_flow.cancel_booking`; reminder callback uses `ReminderActionService.handle_action(action="cancel")` | `test_booking_patient_flow_stack3c1.py` cancel returns `OrchestrationSuccess`; `test_reminder_actions_stack4b2.py` cancel accepted path | PAT/A3 reports describe reminder accepted handoff | Implemented | Two entry paths converge on orchestration cancel semantics. |
| post-click patient feedback | `/my_booking`: re-render canceled booking panel; reminder: accepted header + fresh booking panel handoff | `test_patient_reminder_handoff_pat_a3_1a.py` asserts cancel -> “Booking canceled.” + panel | PAT-A3 reports describe canonical handoff | Implemented | Patient sees explicit outcome and booking context continuity. |
| canonical panel continuity after cancel | reminder accepted path calls `_handoff_reminder_action_to_booking_panel`; `/my_booking` re-renders same panel family | `test_patient_reminder_handoff_pat_a3_1a.py` checks panel binding; A3 reports emphasize canonical continuity | PAT-A3 docs | Implemented | Continuity objective from PAT-A3 is retained for cancel. |
| actual booking cancellation semantics | `BookingPatientFlowService.cancel_booking` -> orchestration cancel with allowed statuses and guards | `test_booking_patient_flow_stack3c1.py` asserts canceled status | booking state machine docs define canonical canceled state | Implemented | Real state mutation, not intent-only capture. |
| slot release semantics | Cancel path updates booking state; no explicit slot-status mutation/release in cancel path evidenced | No dedicated test proving slot returns to `open` on cancel found in scoped files | docs discuss canceled state but no explicit runtime slot-release proof in scoped evidence | Unknown | Likely booking conflict checks rely on booking status, but explicit slot release guarantee is not directly evidenced here. |
| reminder cancellation/update semantics | orchestration cancel calls `_cancel_reminders_for_booking_in_transaction`; reminder service cancels scheduled reminders | `test_booking_orchestration.py` includes cancellation of scheduled reminders on cancel lifecycle paths | architecture/docs place reminder truth in communication layer | Implemented | Scheduled reminder jobs are canceled on booking cancel. |
| stale callback protection | existing-booking validation checks latest session id, resolved patient, booking ownership; reminder service checks stale/invalid/message mismatch | `test_booking_patient_flow_stack3c1.py` rejects stale/foreign actions; `test_reminder_actions_stack4b2.py` validates stale/invalid safety | PAT-A3/PAT-A4 hardening reports | Implemented | Strong bounded stale safety in both entry types. |
| human-readable patient-facing cancel copy | i18n keys for prompt/aborted/outcomes; reminder default labels include `❌ Cancel` | `test_patient_reminder_handoff_pat_a3_1a.py` asserts readable “Booking canceled.” header | i18n docs/product UX rules | Implemented | Copy is present and localized baseline exists. |

---

## 4. Gaps that block PAT-005 closure

> Strictly blocker-grade gaps that would prevent “truly closed” status were **not found** in scoped runtime evidence.

### Gap 1: Reminder cancel path lacks explicit second-step confirmation parity
- **Severity:** medium
- **Evidence:** reminder cancel executes directly via `rem:cancel:*` -> `ReminderActionService.handle_action(... action="cancel")` and then handoff.
- **Why it matters:** if product requires destructive-action parity with `/my_booking` yes/no prompt, reminder path currently differs.
- **Type:** mixed (UX + flow-policy)

### Gap 2: Explicit slot release semantics on cancellation not directly evidenced in patient cancel scope
- **Severity:** major (only if product acceptance requires explicit slot entity release proof)
- **Evidence:** cancel path clearly sets booking to `canceled`, but scoped code/tests here do not directly assert slot state flips to `open`.
- **Why it matters:** PAT-005 acceptance asks whether old slot becomes free; current proof is indirect (booking no longer live), not explicit slot-state assertion.
- **Type:** runtime-verification/documentation gap

---

## 5. Things that are already good enough

- Existing-booking entry continuity via `/my_booking` and home callback is in place and hardened.
- Trusted identity shortcut for `/my_booking` already reduces friction and still falls back safely.
- Cancel from booking panel is real and guarded (session ownership + patient ownership + status eligibility).
- Reminder cancel is transactional and not a fake intent capture.
- Accepted reminder actions (including cancel) maintain canonical booking-panel continuity.
- Booking lifecycle recording (`status history`, outbox event, timestamps) is integrated for cancellation.
- Reminder plan cancellation on booking cancel is integrated in orchestration/reminder layer.
- Stale/invalid callback safety is already materially strong for both reminder and booking-control callbacks.

---

## 6. Minimal implementation stack to close PAT-005

### PAT-A5-1 — Cancel parity hardening across entry seams
- **Objective:** Decide and enforce one cancel-confirm policy across `/my_booking` and reminder cancel.
- **Exact scope:**
  - If confirm-required: add reminder cancel confirm step and callbacks, then execute cancel.
  - If one-tap allowed: explicitly codify and document one-tap reminder cancel as intended behavior.
- **Non-goals:** booking engine redesign, reminder scheduling redesign.
- **Files likely touched:**
  - `app/interfaces/bots/patient/router.py`
  - localization keys in `locales/*` as needed
  - `booking_docs/50_booking_telegram_ui_contract.md` / scenario docs for policy alignment
- **Tests likely touched/added:**
  - `tests/test_patient_reminder_handoff_pat_a3_1a.py`
  - new focused PAT-A5 reminder-cancel-confirm callback tests (if confirm step adopted)
- **Migrations needed?:** no
- **Acceptance criteria:** Reminder cancel behavior matches explicit product decision and is regression-tested.

### PAT-A5-2 — Explicit cancel semantics proof (slot + reminders)
- **Objective:** lock acceptance-proof tests for true cancellation downstream effects.
- **Exact scope:**
  - add targeted tests proving cancellation semantics required by PAT-005 checklist:
    - booking status/history/event
    - reminder cancellation/update
    - slot availability behavior (explicitly asserted according to intended model)
- **Non-goals:** introducing new slot model or queue redesign.
- **Files likely touched:**
  - `tests/test_booking_orchestration.py`
  - `tests/test_booking_patient_flow_stack3c1.py`
  - optionally `tests/test_reminder_delivery_stack4b1.py` for relevance/cancel interplay
- **Tests likely touched/added:** PAT-A5 scoped regression tests only.
- **Migrations needed?:** no
- **Acceptance criteria:** PAT-005 closure claims are backed by explicit automated tests, not indirect inference.

### PAT-A5-3 — Patient-facing cancel copy + panel polish
- **Objective:** ensure post-cancel patient message is compact, unambiguous, and consistent across entry seams.
- **Exact scope:**
  - unify outcome header/body style for cancel from `/my_booking` and reminder;
  - keep canonical booking-panel continuity unchanged.
- **Non-goals:** broad card redesign, admin/owner copy changes.
- **Files likely touched:**
  - `app/interfaces/bots/patient/router.py`
  - `locales/en.json`, `locales/ru.json` (or equivalent locale files)
- **Tests likely touched/added:**
  - targeted router-level assertions for visible text continuity after cancel.
- **Migrations needed?:** no
- **Acceptance criteria:** patient sees clear canceled outcome and next-step message in both paths, with stable tests.

---

## 7. Product decisions requiring explicit human confirmation

1. Should patient cancel be **true self-service cancellation** (current runtime) or downgraded to cancel-request intent capture?
2. Must reminder-driven cancel include an explicit yes/no confirm prompt (parity with `/my_booking`) or remain one-tap?
3. Must `/my_booking` and reminder cancel always converge to one canonical cancel flow contract (same prompt policy + same post-action panel style)?
4. After cancellation, should canceled booking remain visible as historical canceled card in patient flow (current behavior) or be hidden from active patient surface?
5. Should reminder jobs be canceled immediately on patient cancellation (current behavior), and should any cancellation acknowledgment reminder be sent as separate policy?

---

## 8. Final closure checklist

- [ ] Patient can enter cancel from existing booking context (`/my_booking` and home shortcut parity).
- [ ] Reminder action path exposes cancel where intended.
- [ ] Cancel policy is explicit and consistent (confirm prompt or one-tap) across entry seams.
- [ ] Cancel action is ownership/staleness guarded.
- [ ] Cancel performs canonical booking status transition to `canceled` (not intent-only).
- [ ] Booking status history and outbox event are recorded.
- [ ] Patient receives clear post-cancel feedback and canonical booking-panel continuity.
- [ ] Reminder jobs for canceled booking are canceled/updated correctly.
- [ ] Slot availability semantics after cancellation are explicitly verified and documented.
- [ ] Regression tests cover `/my_booking` and reminder cancel paths.
