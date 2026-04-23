# DOCTOR scenario audit — operational doctor surface readiness after PAT and ADMIN closure (2026-04-22)

## 1. Executive verdict

**Is the doctor group ready to become the next implementation target?** **yes**.

Doctor runtime has enough real surface to start immediately (queue open, booking open, in-service/completed actions, patient/chart/encounter commands, recommendation issuance command, linked recommendation/care-order panels). But continuity is not yet operationally smooth end-to-end for a busy clinician: key actions are split between queue text and callback cards, encounter progression is mostly command-driven rather than naturally embedded in booking flow, and recommendation issuance is present but ergonomically detached from the in-visit booking card path. In short: this is a solid base, not closure.

**What should be built first inside doctor and why?**

Build **DOC-A1 (doctor queue→current-booking→encounter continuity shell)** first. It removes the highest day-2 friction: fragmented entry paths and weak encounter-start continuity. If this seam is not tightened first, later note/recommendation/care improvements still sit on a shaky workflow spine.

---

## 2. Doctor scenario closure matrix

| Scenario | Status | Confidence | Docs match? | Notes |
|---|---|---|---|---|
| DOC-001 Open upcoming queue | Implemented | high | Yes (with nuance) | `/today_queue` + `/next_patient` exist and are tested; queue continuity is functional but split between command text and callback entry. |
| DOC-002 Open current booking | Implemented | high | Yes | `/booking_open` and doctor booking callback open path render booking shell + keyboard. |
| DOC-003 Mark in service / start encounter | Partial | high | **No** | Mark-in-service is implemented; “start encounter” is not naturally coupled from booking action path and remains separate command flow. |
| DOC-004 Add quick note / see relevant patient context | Partial | high | Yes | Patient quick card/chart/encounter/note are present; still thin and command-centric for active visit continuity. |
| DOC-005 Issue recommendation | Partial | high | **No** | Issuance works via `/recommend_issue` and service path (including proactive delivery), but booking-card flow does not provide an in-context issue action. |
| DOC-006 Open linked care-order | Implemented (bounded) | high | Yes | Linked care-order open from doctor booking callback is present with safe back-path; intentionally read/awareness only. |
| DOC-007 Complete encounter | Partial | medium-high | **No** | Booking completion action exists and triggers aftercare recommendation; encounter closure lifecycle is not integrated as a coherent booking-driven finish flow. |

---

## 3. Scenario-by-scenario commentary

### DOC-001 — Open upcoming queue
Implemented materially. Doctor has `/today_queue` and `/next_patient`, both backed by queue filtering (`LIVE_QUEUE_STATUSES`) and tested queue ordering/empty behavior. Operational nuance: `/today_queue` still returns command-led rows (`/booking_open ...`) while `/next_patient` gives callback open, so entry style is split.

### DOC-002 — Open current booking
Implemented materially. Doctor can open booking by command and via callback, receives expanded booking shell, and gets doctor action keyboard (in service / complete / open patient / chart / recommendation / care order). This is one of the stronger parts of doctor runtime.

### DOC-003 — Mark in service / start encounter
Partial. Booking action path clearly supports `checked_in`, `in_service`, `completed` and callback-based in-service transitions. However, “start encounter” itself is not coupled to that action; encounter lifecycle is a separate command (`/encounter_open`) instead of a natural in-card progression from the in-service action.

### DOC-004 — Add quick note / see relevant patient context
Partial. Context and note primitives are real (`/patient_open`, `/chart_open`, `/encounter_open`, `/encounter_note`, diagnosis/plan/imaging/odontogram commands), and clinical tests validate baseline encounter/chart behavior. But doctor active-visit flow remains command-heavy with limited one-tap continuity from booking card into encounter note capture.

### DOC-005 — Issue recommendation
Partial. Doctor recommendation issuance is implemented in application service and route (`/recommend_issue`) with guardrails, optional care target linking, and proactive patient delivery attempts; tests cover issue + booking-trigger behavior and fail-safe delivery. Operational gap: booking card “recommendation” action opens linked recommendation panel (read/open) rather than providing direct in-context issuance UX.

### DOC-006 — Open linked care-order
Implemented (bounded). Doctor booking callback can open linked care-order panel, using latest booking-linked order resolution and safe back navigation to booking card. This is operationally useful awareness and intentionally not a fulfillment console.

### DOC-007 — Complete encounter
Partial. Doctor can complete booking from callback/command path; completion path also creates/dispatches aftercare recommendation, which correctly supports PAT-007 continuity. But completion is booking-state completion, not a coherent encounter-finalization sequence (no explicit encounter close step tied to the same interaction path).

---

## 4. Hidden operational gaps

1. **Fragmented doctor entry path (queue text list vs callback card flow)**  
   - **severity:** major  
   - **evidence:** `/today_queue` outputs text rows with `/booking_open` command hints, while `/next_patient` uses callback open button; continuity style differs inside same doctor queue surface.  
   - **why it matters operationally:** clinicians in fast mobile context need one consistent tap path; mixed command/callback UX raises friction and context switching.  
   - **timing:** address early.

2. **In-service action does not naturally start/open encounter context**  
   - **severity:** blocker  
   - **evidence:** booking callback handles `in_service` by status transition only; encounter work is separate `/encounter_open` command.  
   - **why it matters operationally:** “patient is in chair” should transition directly into clinical working context; otherwise start-of-visit flow is brittle and easy to skip.  
   - **timing:** address early.

3. **Recommendation issuance is command-only from doctor perspective**  
   - **severity:** major  
   - **evidence:** issuance exists via `/recommend_issue`; booking-card recommendation action only opens linked recommendation panel.  
   - **why it matters operationally:** recommendation is a core doctor post-visit action; command-only issuance in active visit reduces adoption and increases workflow breakage.  
   - **timing:** address early.

4. **Encounter completion semantics are weaker than booking completion semantics**  
   - **severity:** medium  
   - **evidence:** booking completion is wired and aftercare recommendation trigger exists; encounter close lifecycle is not coupled to booking completion path in doctor router.  
   - **why it matters operationally:** clinicians can finish booking state without clearly finishing encounter artifact lifecycle, creating documentation drift risk.  
   - **timing:** early-mid (after DOC-A1 spine).

5. **Doctor linked recommendation/care panels are useful but thin dead-end awareness panels**  
   - **severity:** medium  
   - **evidence:** linked panels open and support Back; doctor panel does not offer richer next-step action from those opens (e.g., issue follow-up from same context).  
   - **why it matters operationally:** surfaces are visible but not strongly action-driving; continuity to completion tasks depends on manual command recall.  
   - **timing:** can follow initial continuity fixes.

6. **Document/export capabilities exist but are detached from core doctor booking flow**  
   - **severity:** minor  
   - **evidence:** doctor has command family (`/doc_generate`, `/doc_registry_booking`, `/doc_open`, `/doc_download`, `/doc_regenerate`) rather than booking-card-first contextual bridge.  
   - **why it matters operationally:** features exist yet are less likely to be used during real-time visits unless doctors remember command syntax.  
   - **timing:** can wait.

---

## 5. Things already good enough

- Doctor queue retrieval and next-patient selection logic are materially good enough for first doctor wave; keep and iterate, do not rewrite.
- Doctor booking card shell and callback discipline are good enough baseline (stale-safe coded callback, bounded linked opens).
- Doctor booking state transitions (`checked_in` / `in_service` / `completed`) are good enough baseline; focus on continuity around them, not state-machine redesign.
- Recommendation domain/service and proactive patient delivery plumbing are good enough for first doctor wave; improve doctor UX entry, not recommendation core semantics.
- Linked care-order bounded read panel is good enough for doctor awareness; do not turn doctor into pickup operator in the first wave.

---

## 6. Recommended first doctor PR stack

### DOC-A1 — Queue-to-encounter continuity spine
- **objective:** provide one coherent doctor operational path from upcoming queue -> current booking -> in-service -> encounter working context.
- **exact scope:**
  - unify doctor queue interaction style around callback-first continuity for opening booking;
  - when doctor marks `in_service`, provide immediate bounded handoff into encounter open/summary context;
  - preserve stale/back behavior across queue and booking contexts.
- **non-goals:**
  - no deep EMR redesign;
  - no owner/admin feature expansion;
  - no booking state-machine rewrite.
- **files likely touched:**
  - `app/interfaces/bots/doctor/router.py`
  - `app/application/doctor/operations.py` (only minimal helper additions if needed)
  - possibly `app/interfaces/cards/*` doctor booking action seed/labels if needed
- **tests likely touched/added:**
  - `tests/test_doctor_operational_stack6a.py`
  - `tests/test_booking_linked_opens_12b1.py` (if callback continuity shape changes)
  - add focused doctor continuity test module for in-service->encounter handoff
- **migrations needed?** no
- **acceptance criteria:**
  - doctor can open booking from queue in a consistent tap flow;
  - in-service action leads naturally into encounter context (without command memorization);
  - back/stale behavior remains deterministic and bounded.

### DOC-A2 — In-context clinical note/recommendation actionability
- **objective:** make active-visit doctor actions (quick note + recommendation issue) reachable from current booking/encounter context without command-only fallback.
- **exact scope:**
  - add bounded “add quick note” and “issue recommendation” action entry from doctor booking/encounter context;
  - keep recommendation target linking optional/compact;
  - keep command routes as fallback but no longer primary path.
- **non-goals:**
  - no broad chart UI expansion;
  - no recommendation analytics;
  - no patient aftercare redesign.
- **files likely touched:**
  - `app/interfaces/bots/doctor/router.py`
  - `app/application/doctor/operations.py`
  - possibly small glue in `app/application/recommendation/services.py` only if needed for compact flow support
- **tests likely touched/added:**
  - `tests/test_doctor_operational_stack6a.py`
  - `tests/test_recommendation_stack10a.py`
  - add callback-driven doctor issue/note continuity tests
- **migrations needed?** no
- **acceptance criteria:**
  - doctor can add at least one structured quick note path from active booking context;
  - doctor can issue recommendation from active booking/encounter context in <=2 steps;
  - recommendation still feeds patient-facing PAT-007 path via existing delivery seams.

### DOC-A3 — Encounter completion coherence + bounded linked-panel polish
- **objective:** ensure doctor finish path is operationally coherent (encounter + booking completion) and linked panels are not dead awareness views.
- **exact scope:**
  - tighten complete flow so encounter completion semantics are explicit when doctor marks visit done;
  - add minimal actionable continuation from linked recommendation/care panels back to relevant current context;
  - preserve existing aftercare auto-issue behavior on booking completion.
- **non-goals:**
  - no full clinical record workflow expansion;
  - no care pickup operator tooling for doctor;
  - no export/document subsystem redesign.
- **files likely touched:**
  - `app/interfaces/bots/doctor/router.py`
  - `app/application/doctor/operations.py`
  - potentially narrow touch in `app/application/clinical/*` service interfaces only if explicit encounter-close hook is needed
- **tests likely touched/added:**
  - `tests/test_clinical_stack7a.py`
  - `tests/test_doctor_operational_stack6a.py`
  - `tests/test_booking_linked_opens_12b1.py`
- **migrations needed?** no
- **acceptance criteria:**
  - doctor completion path explicitly reflects encounter/visit finalization semantics;
  - linked opens offer at least one practical next step beyond Back;
  - no regressions in aftercare recommendation auto-delivery trigger on completion.

---

## 7. Final recommendation

Start doctor now. Begin with **DOC-A1** first to establish a coherent doctor continuity spine (queue -> booking -> in-service -> encounter). Do **not** start with document/export UX enrichment or broad chart-depth expansion; those are secondary until the core operational visit path is friction-light and reliable.
