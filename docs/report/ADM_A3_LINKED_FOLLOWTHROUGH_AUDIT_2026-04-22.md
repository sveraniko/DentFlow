# ADM-A3 audit — Admin linked recommendation / care follow-through continuity

Date: 2026-04-22  
Scope: bounded operational audit (admin booking-context linked recommendation / linked care-order continuity)

## 1. Executive verdict

**Verdict: Partial**

Admin linked opens are implemented and stable as bounded panels, but they are not equally actionable. From booking context, linked recommendation open is mostly read-only with only a Back path, so it does not provide a natural next operational step. Linked care-order open is also mostly read-only by itself, but the system does provide a separate actionable continuation via `/admin_care_pickups` (issue/fulfill actions), which makes care follow-through materially better than recommendation follow-through. So ADM-A3 is not missing, but it is not closed.

**Final recommendation:** treat ADM-A3 as a narrow continuity pass, not a redesign. First add explicit handoff actions from linked recommendation panel (patient/pickup/doc-adjacent where relevant), then add one-tap continuity from linked care-order panel to pickup queue/detail preserving context, and finish with shared stale/back continuity hardening for linked surfaces.

---

## 2. Current real flow

### A) Booking -> linked recommendation (current runtime)

1. Admin opens booking card (from queue or `/booking_open`), where booking keyboard includes **Recommendation** action (`open_recommendation`).
2. Callback branch `open_recommendation` renders `_render_linked_recommendation_panel(...)`.
3. Panel resolves latest booking-linked recommendation via `recommendation_service.list_for_booking(...)` and deterministic latest selection.
4. UI displays bounded recommendation text (id, title, type, status, snippet).
5. Keyboard is **Back-only** (`_admin_linked_back_keyboard`) to return to booking card.

**What admin can do next (actual):** only go back to booking card and choose another action manually (patient/chart/care-order/booking actions). There is no direct in-panel follow-through action (no “open patient”, no “continue care”, no “mark handled”).

### B) Booking -> linked care-order (current runtime)

1. Admin opens booking card and taps **Care order** (`open_care_order`).
2. Callback branch `open_care_order` renders `_render_linked_care_order_panel(...)`.
3. Panel resolves patient orders, filters by exact `booking_id`, picks newest deterministic order, builds care-order card panel with compact item/branch/reservation hints.
4. Keyboard is again **Back-only** to booking card.

**What admin can do next (actual):** from this panel itself, only Back. However, admin can separately continue operationally via `/admin_care_pickups`, where queue actions (`issue`, `fulfill`) are available and wired to `apply_admin_order_action(...)`.

### C) Where continuity is useful vs dead-end

- **Useful continuity:** booking card itself is operationally meaningful (confirm/check-in/reschedule/cancel/open patient/chart/linked objects), and care pickups queue supports concrete order lifecycle actions.
- **Dead-end continuity:** both linked panels are bounded inspector panels with Back-only navigation; recommendation panel is the clearest dead-end for admin operations.

### D) Docs-implied target vs current behavior

- Docs/reports describe linked opens as implemented and bounded, and the ADM-A3 recommendation explicitly calls for “operationally actionable enough” linked panels.
- Current runtime matches “bounded open works” but not “actionable follow-through from the linked panel itself.”

---

## 3. Evidence map

| Flow segment | Evidence in code | Evidence in tests | Evidence in docs | Status | Notes |
|---|---|---|---|---|---|
| booking -> linked recommendation open | Booking keyboard includes `open_recommendation`; callback branch renders `_render_linked_recommendation_panel` | `test_admin_linked_opens_render_panels_and_back_navigation` | PR 12B-1 report states bounded linked-open convergence | Implemented | Open itself is stable and non-placeholder |
| linked recommendation next-step actions | Linked recommendation panel uses Back-only keyboard (`_admin_linked_back_keyboard`) | Linked-open test validates Back presence only; no next-step CTA test | ADMIN scenario audit flags recommendation-linked admin actionability as partial | Partial | Operationally thin; mostly inspect + back |
| booking -> linked care-order open | Booking keyboard includes `open_care_order`; callback branch renders `_render_linked_care_order_panel` | `test_admin_linked_opens_render_panels_and_back_navigation` | PR 12B-1 report documents care-order linked open | Implemented | Open itself is stable |
| linked care-order next-step actions | Linked care-order panel also Back-only | Linked-open test checks Back only | ADMIN scenario audit states linked care operationally useful mainly via pickup queue | Partial | Panel itself is read-focused |
| continuity into pickup queue/order handling | `/admin_care_pickups` queue render + status filter + `issue/fulfill` actions call `apply_admin_order_action` | `test_admin_care_pickups_queue_and_action`, `test_admin_care_pickups_detail_has_back_to_queue` | Admin scenario docs/reports identify care pickups as operational admin surface | Implemented | Actionability exists, but not one-tap from linked booking panel |
| continuity into patient context (if relevant) | Booking keyboard has `open_patient`; patient continuity from admin patient search is implemented | AW4 tests cover patient->booking continuity and bounded stale handling | PR_ADM_A2A / A2B report continuity improvements | Partial | Possible via booking card, but not directly surfaced inside linked recommendation/care panels |
| document/export adjacency (already present?) | Admin docs flow is command-based (`/admin_doc_generate`, `/admin_doc_open`, etc.), not linked from linked panels | Doc registry tests exist separately (`test_document_registry_ui_12a4a`) | Role scenarios include admin doc flows, but as command entry points | Partial | Adjacent capability exists but not natural from linked panels |
| back navigation / stale safety | Linked panels provide Back to booking; queue callbacks include stale token checks | Linked-open back test + AW3/AW4 stale-token bounded tests for queues/callbacks | Prior ADM reports emphasize bounded stale safety | Implemented | Back is stable; linked panel callbacks are simple/back-only |
| human-readable admin continuity | Panels are human-readable localized summaries, no placeholder text | Linked-open tests assert non-placeholder outputs | PR 12B-1 describes bounded localized panel outputs | Partial | Readability good; action continuity weak |

---

## 4. Gaps that block ADM-A3 closure

1. **No direct operational CTA from linked recommendation panel**  
   - **Severity:** blocker  
   - **Evidence:** linked recommendation callback renders summary + Back-only keyboard.  
   - **Why it matters:** admin can inspect recommendation but cannot continue naturally to handling steps; this is a classic inspect dead-end in booking-context continuity.  
   - **Type:** mixed (UX + runtime)

2. **Linked care-order panel lacks direct handoff to pickup operations**  
   - **Severity:** major  
   - **Evidence:** linked care-order panel is Back-only even though actionable care queue exists elsewhere.  
   - **Why it matters:** admin must remember and manually switch entrypoint (`/admin_care_pickups`) instead of continuing in-panel; friction during front-desk multitask flow.  
   - **Type:** mixed (UX + runtime)

3. **No unified “next step” continuity contract across linked panels**  
   - **Severity:** medium  
   - **Evidence:** both linked panels use shared Back-only keyboard, with no role-appropriate next action buttons.  
   - **Why it matters:** inconsistency between “open linked object” and “continue operational work” causes extra navigation hops and operator uncertainty.  
   - **Type:** UX-only (with minor runtime wiring)

4. **Document/export follow-through is not context-adjacent from linked panels**  
   - **Severity:** minor  
   - **Evidence:** admin document flows are command-led, not linked panel actions.  
   - **Why it matters:** not core blocker for ADM-A3 closure, but prevents natural same-thread continuation when documentation is needed right after linked object review.  
   - **Type:** mixed

---

## 5. Things already good enough

- Linked recommendation and linked care-order opens are no longer placeholders; they render bounded localized panels.
- Deterministic latest selection logic exists for linked recommendation/care-order entities.
- Admin booking card is operationally meaningful and should remain the central context hub.
- Admin care pickups queue already provides concrete lifecycle actions (`issue`, `fulfill`) and should be reused, not rebuilt.
- Existing stale/back safety patterns in AW3/AW4 queue flows are good and should be extended, not redesigned.

---

## 6. Minimal implementation stack to close ADM-A3

### ADM-A3A — Recommendation linked-panel continuity CTA

- **Objective:** make booking-linked recommendation panel operationally actionable in 1–2 taps.
- **Exact scope:**
  - Add bounded action row(s) from linked recommendation panel (e.g., open patient panel and/or open booking-linked care order/pickup continuation).
  - Preserve Back path and source context/state token behavior.
- **Non-goals:**
  - No recommendation-engine redesign.
  - No doctor/owner workflow expansion.
- **Files likely touched:**
  - `app/interfaces/bots/admin/router.py`
  - `locales/en.json`, `locales/ru.json` (if new button labels/copy needed)
- **Tests likely touched/added:**
  - `tests/test_booking_linked_opens_12b1.py`
  - `tests/test_admin_aw4_surfaces.py` (continuity assertion from linked recommendation)
- **Migrations needed?** no
- **Acceptance criteria:**
  - From booking-linked recommendation panel, admin can continue to at least one concrete operational next step without command fallback.
  - Back path still returns to the originating booking panel safely.

### ADM-A3B — Care-order linked-panel -> pickup continuity bridge

- **Objective:** make linked care-order open a direct bridge into pickup handling.
- **Exact scope:**
  - Add explicit CTA from linked care-order panel to related pickup detail or filtered pickup queue.
  - Reuse existing AW4 pickup callbacks and action handlers; do not duplicate order action logic.
- **Non-goals:**
  - No care-commerce model or status-machine redesign.
  - No broad pickup queue redesign.
- **Files likely touched:**
  - `app/interfaces/bots/admin/router.py`
- **Tests likely touched/added:**
  - `tests/test_booking_linked_opens_12b1.py`
  - `tests/test_admin_aw4_surfaces.py`
- **Migrations needed?** no
- **Acceptance criteria:**
  - From booking-linked care-order panel, admin can jump directly into actionable pickup handling for that order.
  - Existing queue filter/status/stale protections remain intact.

### ADM-A3C — Linked-panel continuity hardening (stale/back/human-readable next-step copy)

- **Objective:** harden linked continuity behavior to be operationally safe and self-explanatory.
- **Exact scope:**
  - Add/update localized copy for next-step buttons and bounded stale/invalid linked continuation paths.
  - Add targeted callback tests for stale token / missing linked entity handling on new continuity buttons.
- **Non-goals:**
  - No full i18n overhaul.
  - No broad card-runtime refactor.
- **Files likely touched:**
  - `app/interfaces/bots/admin/router.py`
  - `locales/en.json`, `locales/ru.json`
- **Tests likely touched/added:**
  - `tests/test_booking_linked_opens_12b1.py`
  - `tests/test_admin_aw4_surfaces.py`
- **Migrations needed?** no
- **Acceptance criteria:**
  - New linked continuity controls are bounded and stale-safe.
  - Admin-visible next-step wording is clear and consistent across recommendation/care linked panels.

---

## 7. Final recommendation

Yes — ADM-A3 should be the next implementation target now, but only as a narrow continuity closure pass. Build **ADM-A3A first** (recommendation-panel actionability), then **ADM-A3B** (care-order to pickup bridge). Do **not** start with broad admin UX redesign, care-commerce redesign, or document workflow expansion; those are outside this bounded closure objective.
