# PAT-002 audit — Returning patient quick booking flow (2026-04-22)

## 1) Executive verdict

**Verdict: Partial**

Current runtime does support a **returning patient identity continuity seam**, but it is not yet a fully realized **quick booking** path for PAT-002. In code reality, `/book` uses the same `service_first` booking journey as PAT-001 (service -> doctor preference -> slot -> contact -> review -> confirm). The major difference is that contact resolution can attach an existing patient instead of creating one. A trusted identity shortcut exists for `/my_booking` (existing-booking control), but that trust is not currently reused to shorten `/book` entry for returning rebooking.

**Final recommendation**

Treat PAT-002 as a narrow closure track focused on booking-entry friction only: (1) safely reuse trusted returning-patient identity for `/book` entry, (2) implement bounded continuity suggestions/prefill policy (at least optional recent service/doctor/branch suggestions), and (3) lock the shorter-path contract with targeted tests. Do not redesign booking orchestration, reminders, or non-booking role surfaces.

---

## 2) Current real flow

### 2.1 Current behavior (runtime truth)

1. **Returning patient enters booking via `/book` or `phome:book`**
   - Router calls `_enter_new_booking(...)` -> `booking_flow.start_or_resume_session(..., route_type="service_first")`.
   - This is the same route family used by new-patient PAT-001.

2. **Session resume logic is state-driven, not patient-history-driven**
   - `determine_resume_panel()` maps session state to service/doctor/slot/contact/review.
   - Resume can skip earlier panels only if an active in-progress booking session already has those fields, not because patient is historically returning.

3. **Identity handling in `/book` path is still contact-based at booking stage**
   - After slot selection, contact is requested (`patient.booking.contact.prompt`).
   - Contact submission triggers `resolve_patient_from_contact(...)`.
   - Outcomes:
     - exact match -> existing patient attached;
     - no match -> minimal patient created;
     - ambiguous -> admin escalation.

4. **Review/confirm and finalize are explicit (good), but not quick-book specific**
   - After identity resolution, flow marks `review_ready`, renders review panel, then waits for `book:confirm:<session_id>`.
   - On confirm callback, finalize creates booking (`pending_confirmation` by policy) and success panel is shown.

5. **No PAT-002-specific reuse of previous booking preferences in `/book`**
   - No runtime path that auto-prefills or explicitly suggests previous service/doctor/branch for returning patient quick booking.
   - Existing prefill behavior is implemented for **reschedule control** sessions, not for returning rebooking entry.

6. **Trusted identity shortcut exists, but in adjacent seam (`/my_booking`)**
   - `_enter_existing_booking_lookup(...)` tries `_try_resolve_existing_booking_shortcut(...)` using trusted patient-id resolution from recommendation repository.
   - If trust is unique + safe, it opens existing-booking controls directly (no contact prompt).
   - This shortcut targets existing booking control (`existing_booking_control`) and not new booking entry (`service_first`).

7. **Active booking/reschedule context interaction**
   - Booking entry checks `_resume_active_reschedule_context(...)` first.
   - If a reschedule control session is active, user is redirected back to reschedule panel instead of starting fresh quick booking.
   - Route-type isolation is enforced between `service_first`, `existing_booking_control`, and `reschedule_booking_control`.

8. **Stale/resume safety relevant to quick booking**
   - Confirm callbacks validate active session ownership and route-family freshness.
   - Stale or terminal callbacks are safely rejected.

### 2.2 Target-state behavior (if docs imply stronger PAT-002)

PAT-002 narrative expects a returning-patient path with materially less friction than PAT-001. Current runtime does **not** yet provide a dedicated quick-book branch in `/book` that reuses trusted identity and continuity preferences (service/doctor/branch) as first-class patient-visible shortcuts.

---

## 3) Evidence map

| Flow segment | Evidence in code | Evidence in tests | Evidence in docs | Status | Notes |
|---|---|---|---|---|---|
| returning-patient entry seam | `router._enter_new_booking()` always uses `start_or_resume_session(... route_type="service_first")`; `/book` and `phome:book` share this path | PAT-A1 tests show `/book`/home-book parity and review flow continuity | PAT-002 in `docs/71` expects returning quick booking | Partial | Returning patient enters same base route as PAT-001. |
| trusted identity reuse | Trusted shortcut implemented in `_try_resolve_existing_booking_shortcut()` + `_resolve_patient_id_for_user()` for existing booking lookup | `test_patient_existing_booking_shortcut_pat_a3_2.py` covers unique trusted id, fallback paths | PAT-A3 reports describe trusted `/my_booking` shortcut | Partial | Trust exists, but scoped to `/my_booking`-style existing control, not `/book` quick rebook. |
| contact-step behavior | New booking path requests contact after slot (`_render_resume_panel` contact panel; `_handle_contact_submission`) | `test_patient_first_booking_review_pat_a1_1.py` verifies contact->review, no auto-finalize | Booking UI contract includes contact confirmation panel | Partial | Returning patients still pass contact unless an active resumed session already has it. |
| service/doctor/branch reuse or suggestions | No `/book` logic preloading previous booking preferences; prefill exists for `start_patient_reschedule_session()` only | `test_start_patient_reschedule_session_creates_prefilled_reschedule_session` (reschedule only) | PAT-002 and product docs imply continuity-first potential | Missing | No explicit returning quick-book preference reuse in rebooking path. |
| repeat/recent booking semantics | No booking repeat/recent shortcut in booking flow; only `list_recent_bookings_by_statuses` for admin-facing listings and care-order repeat in care domain | No tests for one-tap repeat previous booking/service in booking path | docs mention continuity ideas; not evidenced in runtime for PAT-002 | Missing | Care repeat exists but out of PAT-002 booking scope. |
| review/confirm path | `_render_review_finalize_panel()` + `book:confirm` callback + finalize | PAT-A1 review/confirm tests verify explicit confirm and stale rejection | booking docs require review/final confirm | Implemented | Solid and should be retained. |
| success continuity | `_render_finalize_outcome()` shows humanized success labels | PAT-A1 tests assert human-readable doctor/service/branch labels | PAT-A1 reports indicate success UX hardening | Implemented | Works equally for new and returning booking once finalized. |
| active-booking/reschedule interaction | `_resume_active_reschedule_context()` intercepts booking entry and resumes/guards reschedule path | route isolation + reschedule tests in stack3c1 and PAT-A3-2 | docs describe no stale panels and coherent state | Implemented | Protects against conflicting active contexts. |
| stale/resume safety | `validate_active_session_callback(...)` checks and explicit stale handling in confirm callbacks | tests cover stale confirm callback and route isolation | booking test scenarios include stale callback handling | Implemented | Safety seam is strong. |
| actual step-count reduction vs PAT-001 | `/book` route remains same service-first path; no special returning shortcut/prefill for rebooking | no tests asserting reduced step count for returning booking | PAT-002 intent expects lower friction | Missing | Current reduction is mostly “existing patient may match on contact,” not a materially shorter UX path. |

---

## 4) Gaps that block PAT-002 closure

1. **No dedicated quick-book entry branch for returning patients in `/book`**
   - **Severity:** blocker
   - **Evidence:** `/book` always starts/resumes `service_first`; trusted identity fast path exists only in `/my_booking` seam.
   - **Why it matters:** PAT-002 requires a meaningfully shorter returning-booking path than PAT-001.
   - **Type:** mixed

2. **Contact friction is not reliably reduced for returning rebooking**
   - **Severity:** major
   - **Evidence:** contact still requested in normal `/book` path after slot unless resumed session already includes contact+resolved patient.
   - **Why it matters:** if returning user still repeats contact most times, “quick booking” is not truly closed.
   - **Type:** mixed

3. **No continuity-first reuse/suggestions of recent service/doctor/branch in `/book`**
   - **Severity:** major
   - **Evidence:** no prefill/suggestion logic in new booking route; only reschedule prefill exists.
   - **Why it matters:** core PAT-002 value is continuity speed; absent this, flow is essentially PAT-001 with known identity resolution.
   - **Type:** mixed

4. **No explicit acceptance metric/test for shorter path vs PAT-001**
   - **Severity:** medium
   - **Evidence:** test suites validate correctness/safety but not a reduced-step returning quick path contract.
   - **Why it matters:** closure can be overstated without measurable friction reduction proof.
   - **Type:** runtime/test

---

## 5) Things that are already good enough

- Explicit review/confirm before finalize is implemented and regression-covered.
- Contact-based patient resolution quality is strong (exact/no-match-create/ambiguous-escalate).
- Trusted identity shortcut for `/my_booking` is conservative and safety-bounded.
- Route-family isolation and stale callback protection are strong and should be preserved.
- Success panel rendering is human-readable and localized-ready.

These pieces should be reused, not redesigned.

---

## 6) Minimal implementation stack to close PAT-002

### PAT-A2-1 — Trusted returning-patient quick entry for `/book`
- **Objective:** allow safe trusted identity reuse on `/book` entry to reduce repeated contact friction.
- **Exact scope:** add a bounded trust lookup step in new-booking entry path, analogous to `/my_booking` trust gating, with strict fallback to current flow.
- **Non-goals:** no admin/doctor/owner changes; no reminder engine changes; no profile-governance redesign.
- **Files likely touched:**
  - `app/interfaces/bots/patient/router.py`
  - `app/application/booking/telegram_flow.py` (if helper reuse needed)
- **Tests likely touched/added:**
  - new targeted router tests for trusted `/book` quick-entry + unsafe fallback
- **Migrations needed?** no
- **Acceptance criteria:**
  - trusted unique returning patient can enter `/book` without mandatory contact step in safe cases;
  - unsafe/missing trust falls back to current contact path;
  - stale/session safety remains intact.

### PAT-A2-2 — Continuity suggestions/prefill for returning rebooking
- **Objective:** make path materially shorter by leveraging prior booking context.
- **Exact scope:** add bounded continuity layer at booking start/review (e.g., suggested recent service/doctor/branch; optional one-tap apply).
- **Non-goals:** no broad recommendation engine; no auto-book without user confirmation.
- **Files likely touched:**
  - `app/application/booking/telegram_flow.py`
  - `app/interfaces/bots/patient/router.py`
  - locale keys (`locales/en.json`, `locales/ru.json`) as needed
- **Tests likely touched/added:**
  - targeted booking flow tests for continuity suggestion/prefill behavior and fallback
- **Migrations needed?** no
- **Acceptance criteria:**
  - returning patient sees continuity shortcuts derived from prior booking context;
  - accepted shortcut reduces at least one explicit selection step vs baseline PAT-001;
  - user can still change selections before final confirm.

### PAT-A2-3 — PAT-002 closure hardening and acceptance proof
- **Objective:** lock scenario truth with explicit reduced-friction tests and doc alignment.
- **Exact scope:** add focused PAT-002 tests and update scenario acceptance note once runtime closure is real.
- **Non-goals:** no platform-wide test overhaul.
- **Files likely touched:**
  - `tests/test_booking_patient_flow_stack3c1.py` (or focused PAT-A2 test file)
  - `tests/test_patient_*` targeted additions
  - `docs/71_role_scenarios_and_acceptance.md` (PAT-002 status only, after runtime closure)
- **Tests likely touched/added:**
  - explicit “returning quick booking is shorter than PAT-001 baseline” assertion set
  - safety regressions for stale callbacks / mixed active contexts
- **Migrations needed?** no
- **Acceptance criteria:**
  - deterministic tests prove reduced steps for returning path;
  - trust/fallback safety preserved;
  - PAT-002 status can move to Implemented with evidence.

---

## 7) Product decisions requiring explicit human confirmation

1. Is trusted returning-patient identity alone sufficient to skip contact on `/book`, or must contact still be reconfirmed periodically?
2. For PAT-002 closure, should recent service/doctor/branch be auto-applied or only offered as explicit suggestions?
3. Is one-tap “repeat previous booking/service” required for PAT-002, or optional beyond closure?
4. When active booking/reschedule context exists, should `/book` always redirect to that context or allow parallel quick-book start?
5. Should returning quick booking still always pass explicit review/confirm before finalize? (recommended: yes)

---

## 8) Final closure checklist

- [ ] Returning patient `/book` entry has a safe trust-based shortcut (with strict fallback).
- [ ] Returning path is measurably shorter than PAT-001 in normal trusted cases.
- [ ] Contact step is skipped or reduced in approved trusted scenarios.
- [ ] Continuity reuse exists for at least one of: recent service, doctor, branch.
- [ ] No unsafe identity shortcuts (ambiguous/missing trust must fallback).
- [ ] Active reschedule/existing contexts do not create conflicting quick-book state.
- [ ] Stale callback/session protections remain intact after quick-book enhancements.
- [ ] Explicit review/confirm remains before finalize.
- [ ] Success continuity remains human-readable/localized.
- [ ] PAT-002 marked Implemented only after all above are true in runtime + tests.

---

## Execution notes

- Scope was intentionally bounded to PAT-002 and adjacent booking seams only.
- Targeted tests executed in this environment:
  - `pytest -q tests/test_patient_first_booking_review_pat_a1_1.py tests/test_patient_existing_booking_shortcut_pat_a3_2.py tests/test_booking_patient_flow_stack3c1.py tests/test_booking_orchestration.py`
- Result: **59 passed**.
