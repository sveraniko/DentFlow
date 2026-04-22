# ADMIN scenario audit — operational control surface readiness after PAT closure (2026-04-22)

## 1) Executive verdict

**Is the admin group ready to become the next implementation target?** **Yes.**

The admin group should be the next target because DentFlow already has a real admin control surface (today/confirmations/reschedules/waitlist/patients/care-pickups/issues queues, booking card actions, and linked recommendation/care opens), but key operational seams are still partial in ways that now directly affect PAT-closed continuity. PAT closure means patient-driven confirmation, reschedule, cancel, recommendation, and care-order consequences are now real workload for admin; the runtime has enough foundation to iterate safely, but not enough closure to claim end-to-end reception readiness without a focused first PR stack.

**What should be built first inside admin and why?**

First, close the **reschedule + reminder-exception operational loop** from queue discovery to explicit operator resolution state, because this is the highest continuity risk in day-2 operations: admins can currently detect many issues and request transitions, but they have limited first-class completion/ownership controls for rescue outcomes. This is higher priority than calendar or broad UI polish.

---

## 2) Admin scenario closure matrix

| Scenario | Status | Confidence | Docs match? | Notes |
|---|---|---|---|---|
| ADM-001 Open today workdesk | Implemented | high | Yes (mostly) | `/admin_today` + filters + booking drill-in + stale token protection are implemented and tested. |
| ADM-002 Search/open patient | Partial | medium-high | **No** (docs overstate) | Patient search + patient card open exist; operational continuation from patient card is limited (mostly read/back), so “search/open patient” is true but “work from patient context” is thin. |
| ADM-003 Search/open booking | Implemented | high | Yes | `/booking_open`, queue rows, and runtime booking card opens are present with callback integrity checks. |
| ADM-004 Confirm/check-in booking | Implemented | high | Yes | Admin booking card supports confirm + checked_in transitions with orchestration wiring. |
| ADM-005 Reschedule handling | Partial | high | **No** (docs overstate) | Admin can open reschedule queue and trigger `reschedule_requested`, but no admin-first slot rescue/complete flow is evident in admin runtime surface. |
| ADM-006 Reminder exception / no-response handling | Partial | high | Yes | Confirmations/issues queues and failed-reminder retry exist, but issue lifecycle control (take/resolve from issues queue) is incomplete in primary admin workdesk UX. |
| ADM-007 Linked recommendation handling | Partial | medium | **No** (docs overstate) | Linked recommendation open from booking is present but bounded/read-only; actionable follow-through from admin panel remains minimal. |
| ADM-008 Linked care-order / pickup handling | Implemented (bounded) | medium-high | Yes (bounded) | Linked care-order open + care pickup queue + issue/fulfill actions are present; detail depth remains compact. |
| ADM-009 Calendar mirror awareness flow | Partial | high | Yes | Calendar projection backend exists, but admin Telegram workdesk has no first-class calendar mirror entry/action continuity. |

---

## 3) Scenario-by-scenario commentary

### ADM-001 — Open today workdesk
Implemented materially. Admin has `/admin_today`, branch/doctor/status filters, queue rendering, booking drill-in, and stale callback safeguards. This is backed by admin router paths and AW2 tests validating role guardrails, queue rendering, and back navigation behavior.

### ADM-002 — Search/open patient
Partial. `/admin_patients` and `/search_patient` exist and patient cards can be opened, but the patient panel is mostly a bounded summary card with limited operational continuation controls; runtime emphasis remains booking-queue-first rather than patient-card-driven operations.

### ADM-003 — Search/open booking
Implemented materially. Booking open from command and workdesk queues is wired through card callbacks with source-context/state-token checks, and booking panel rendering is coherent for admin role.

### ADM-004 — Confirm/check-in booking
Implemented materially. Booking action keyboard exposes confirm/check-in when eligible; callback handling calls booking orchestration/transition services and re-renders booking view.

### ADM-005 — Reschedule handling
Partial. Admin can detect and open reschedule items and can request `reschedule_requested`, but no admin slot-selection completion path comparable to patient reschedule completion is exposed in admin router; this leaves rescue continuity operator-heavy and externally dependent.

### ADM-006 — Reminder exception / no-response handling
Partial. Runtime includes confirmation/no-response visibility and issues queue, and retry of failed reminder exists (`aw4i:retry`). But the primary admin issues panel does not expose full issue ownership lifecycle actions (take/resolve/close) even though escalation primitives exist elsewhere (`booking_escalation_take`/`resolve` command surface).

### ADM-007 — Linked recommendation handling
Partial. Booking linked recommendation panel opens and displays latest recommendation details, but this is read-focused. There is no strong admin recommendation action workflow from this panel, so operational handling is present but thin.

### ADM-008 — Linked care-order / pickup handling
Implemented, bounded. Admin can open linked care order and work care pickups with status filtering and action buttons (`issue`, `fulfill`), which is operationally useful for front-desk pickup flow. It is compact rather than comprehensive, but materially usable.

### ADM-009 — Calendar mirror awareness flow
Partial. DentFlow→Google Calendar projection stack exists and is intentionally one-way, but admin Telegram runtime does not provide a first-class mirror entry panel/deep link flow; calendar remains infrastructure capability rather than integrated admin UX.

---

## 4) Hidden operational gaps

1) **Admin reschedule rescue is detection-heavy but completion-light**  
- **Severity:** blocker  
- **Evidence:** admin has `/admin_reschedules` queue and booking-level `reschedule` request action, but no admin UI path for selecting a replacement slot and completing reschedule in admin surface. Patient flow has explicit completion (`complete_patient_reschedule`) but admin router does not mirror that completion pattern.  
- **Why it matters operationally:** reception teams need to *finish* rescue, not only flag/request it; otherwise reschedule backlog accumulates or moves to ad-hoc/manual channels.  
- **Address timing:** early (ADM-A1).

2) **Issue queue lacks first-class ownership lifecycle controls**  
- **Severity:** major  
- **Evidence:** `/admin_issues` supports listing/open/retry reminder; explicit escalation take/resolve exists mainly via command endpoints (`/booking_escalation_take`, `/booking_escalation_resolve`) rather than integrated issues queue controls.  
- **Why it matters operationally:** unresolved ownership leads to duplicated effort and poor shift handoff for reminder/no-response fallout.  
- **Address timing:** early (ADM-A1/ADM-A2).

3) **Patient search/open does not naturally continue to booking-focused admin action**  
- **Severity:** medium  
- **Evidence:** patient search and panel open exist, but patient card continuity is mostly summary/back pattern; there is no strong patient-card action bridge into active booking/case handling inside the same flow.  
- **Why it matters operationally:** admins often start from patient identity lookup during calls/front desk; weak continuation increases command fallback and interaction friction.  
- **Address timing:** early (ADM-A2).

4) **Linked recommendation panel is present but operationally thin**  
- **Severity:** medium  
- **Evidence:** admin linked recommendation open shows bounded content; lacks explicit operational actions in-panel for follow-through/escalation from admin side.  
- **Why it matters operationally:** recommendation follow-through can stall when reception needs to coordinate patient action after no-response/call handling.  
- **Address timing:** can wait until after core rescue continuity (ADM-A3).

5) **Calendar mirror remains infra-first, not admin-workdesk integrated**  
- **Severity:** minor  
- **Evidence:** projection backend and docs exist, but admin contract itself treats calendar panel as optional/future entry; no strong admin Telegram flow tie-in.  
- **Why it matters operationally:** awareness exists externally but action continuity is fragmented.  
- **Address timing:** can wait (post initial admin continuity PRs).

6) **Document/export surfaces are command-centric and detached from admin workdesk context**  
- **Severity:** minor  
- **Evidence:** admin document flows exist via commands (`admin_doc_*`) but are not naturally linked from patient/booking cards in main admin workdesk flow.  
- **Why it matters operationally:** useful capability may be underused because it is not context-native in day-to-day queue actions.  
- **Address timing:** later, after core operational continuity.

---

## 5) Things already good enough (do not rework in first admin wave)

- **Admin queue skeleton and role guardrails are good enough**: today/confirmations/reschedules/waitlist/care-pickups/issues sections exist with stale-safe callback handling.
- **Booking quick-card action baseline is good enough**: confirm/check-in/reschedule/cancel/open patient/chart/linked opens are already wired and should be iterated, not rebuilt.
- **Care pickup operational baseline is good enough**: listing + open + issue/fulfill actions are materially useful now.
- **Reminder no-response signal plumbing is good enough for first wave**: projection and queue signalization exist; priority is operational lifecycle controls, not rebuilding signal detection.
- **Calendar projection backend is good enough for now**: keep one-way truth boundary and avoid reopening projection architecture in first admin wave.

---

## 6) Recommended first admin PR stack

### ADM-A1 — Reschedule + reminder-exception closure loop
- **Objective:** make admin able to complete the two highest-friction rescue loops (reschedule fallout and reminder exception) within the primary admin workdesk flow.
- **Exact scope:**
  - add admin-first reschedule completion path from `admin_reschedules` / booking card to slot selection + completion handoff;
  - expose issue ownership lifecycle actions in `/admin_issues` flow (take/in-progress/resolve) for booking-linked reminder/no-response cases;
  - keep stale-token/back behavior consistent with existing AW2/AW3/AW4 patterns.
- **Non-goals:**
  - no doctor/owner redesign;
  - no broad new analytics surfaces;
  - no calendar bidirectional editing.
- **Files likely touched:**
  - `app/interfaces/bots/admin/router.py`
  - `app/application/booking/telegram_flow.py` (if admin-specific completion helpers are needed)
  - `app/application/communication/recovery.py` (only if queue-facing status transitions require app-level methods)
  - `tests/test_admin_queues_aw3.py`, `tests/test_admin_aw4_surfaces.py`, plus new admin reschedule rescue tests.
- **Tests likely touched/added:** targeted admin queue/rescue callback tests and issue lifecycle tests.
- **Migrations needed?** no.
- **Acceptance criteria:**
  - admin can start and complete reschedule rescue from admin surface for eligible bookings;
  - admin can claim/resolve reminder/no-response issues from issues queue without command-only fallback;
  - stale callbacks fail safe and back navigation remains coherent.

### ADM-A2 — Patient/booking continuity bridge in admin search flows
- **Objective:** make patient lookup operationally useful as a first-class admin entry path.
- **Exact scope:**
  - strengthen `/admin_patients` result→patient panel→active booking open/action path;
  - ensure from patient panel admin can quickly open current booking and jump into booking actions;
  - align wording/hints with workdesk-first operations.
- **Non-goals:**
  - not a full CRM;
  - no deep chart expansion;
  - no owner reporting features.
- **Files likely touched:**
  - `app/interfaces/bots/admin/router.py`
  - patient card adapter/runtime seed files only if strictly needed for action button exposure;
  - `tests/test_admin_today_aw2.py` and/or a dedicated admin patient-continuity test module.
- **Tests likely touched/added:** callback continuity tests from patient search to booking action panel.
- **Migrations needed?** no.
- **Acceptance criteria:**
  - admin can search patient, open patient card, open active booking, and perform confirm/check-in/reschedule/cancel without command fallback;
  - stale/back behavior remains deterministic.

### ADM-A3 — Linked recommendation/care handling polish (bounded)
- **Objective:** make linked recommendation/care panels operationally actionable enough for reception follow-through without broad subsystem expansion.
- **Exact scope:**
  - add bounded admin actions/handoffs from linked recommendation panel (e.g., open patient/contact-context or mark follow-up path);
  - improve linkage between booking-linked care panel and care pickup queue for fast continuation;
  - optional context hints for document/export where relevant, without full doc workflow redesign.
- **Non-goals:**
  - no recommendation domain rewrite;
  - no care catalog governance expansion;
  - no generalized workflow engine.
- **Files likely touched:**
  - `app/interfaces/bots/admin/router.py`
  - possibly small helper methods in recommendation/care application services if needed for read-side convenience;
  - `tests/test_booking_linked_opens_12b1.py` and `tests/test_admin_aw4_surfaces.py`.
- **Tests likely touched/added:** linked-open admin continuity tests validating actionable handoffs and back paths.
- **Migrations needed?** no.
- **Acceptance criteria:**
  - linked recommendation/care opens are no longer read dead-ends for admin;
  - admin can continue into practical next action in 1–2 taps;
  - no regression in existing linked-open stale protection.

---

## 7) Final recommendation

Start admin now. Begin with **ADM-A1** first, because reschedule rescue and reminder exception ownership are the most immediate operational risk after PAT closure. Do **not** start with calendar UX expansion, owner/doctor broadening, or architecture rewrites; those would dilute the highest-value admin continuity work.

---

## Evidence basis and method notes

- This audit is based on runtime code and test inspection first, with scenario docs treated as secondary narrative.
- No runtime code, migrations, or tests were added in this audit task.
- Where docs claim stronger closure than runtime actionability, runtime truth was prioritized.
