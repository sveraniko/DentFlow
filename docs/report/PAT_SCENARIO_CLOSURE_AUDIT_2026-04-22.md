# PAT closure audit — PAT-001 through PAT-008 readiness, hidden gaps, and next-group recommendation (2026-04-22)

## 1. Executive verdict

**Is the PAT branch ready to stop feature work and move on?** **Yes** (with one bounded caveat: PAT-002 remains intentionally heuristic rather than preference-model-driven).

Current runtime code and targeted PAT regression tests now support the full patient branch across booking, existing-booking continuity, reminders, post-visit recommendation interaction, and care reserve/pickup continuity. The largest earlier gaps (first-run panel, explicit review before finalize, reminder-to-canonical-booking handoff, reschedule completion flow, recommendation and care proactive-open seams) are now implemented in runtime paths and covered by scenario-focused tests. Remaining tails are mostly product-polish/organization concerns rather than closure blockers.

**Are any PAT polish/fix PRs still justified before moving on?** **No mandatory PRs.** A tiny optional cleanup PR is defensible only for test discoverability, not runtime correctness.

**Which next group should be tackled first and why?** **admin** first. Patient flows now generate and mutate exactly the operational workload admins must absorb (confirmation discipline, reschedule rescue, cancellation handling, pickup-ready operations, issue queues). Stabilizing admin next gives immediate operational value and de-risks day-2 clinic behavior; owner should not be first, and doctor can proceed after admin convergence for strongest cross-role continuity.

---

## 2. PAT scenario closure matrix

| Scenario | Status | Confidence | Docs match? | Notes |
|---|---|---|---|---|
| PAT-001 new visitor first booking | Implemented | high | **No** (docs/71 still says Partial) | `/start` home panel, guided booking callbacks, explicit review panel, then finalize; no forced immediate finalize after contact.
| PAT-002 returning patient quick booking | Implemented (heuristic) | medium-high | **No** (docs/71 still says Partial) | Trusted identity shortcut + quick-book suggestion panel + bounded recent-booking prefill/same-doctor paths are live.
| PAT-003 booked patient confirmation flow | Implemented | high | Yes | `/my_booking` and reminder handoff converge to canonical booking panel and proper status mutation rules.
| PAT-004 reschedule flow | Implemented | high | Yes | Patient reschedule start, slot reselection, completion, and continuity handoff are implemented with route-type guards.
| PAT-005 cancel flow | Implemented | high | Yes | Cancel prompt/confirm flow exists in both booking-panel and reminder-derived continuity seams.
| PAT-006 reminder acknowledgement flow | Implemented | high | Yes | `ack` updates reminder acknowledgement without pretending booking-state mutation; accepted actions hand off to canonical booking continuity.
| PAT-007 post-visit recommendation / aftercare | Implemented (bounded) | medium-high | **No** (docs/71 still says Partial) | Patient recommendation list/open/action/products and proactive delivery callback seam are implemented; rich document-delivery program remains out of PAT scope.
| PAT-008 care reserve / pickup | Implemented | high | Yes | Care catalog → reserve/order → current/history orders + proactive pickup-ready `careo:open:*` continuity are implemented with ownership checks.

---

## 3. Scenario-by-scenario commentary

### PAT-001 — New visitor first booking
Runtime now follows proper patient-first booking UX with explicit review before finalize: slot selection leads to contact capture, `mark_review_ready`, then `_render_review_finalize_panel` with confirm CTA before `finalize`. Targeted tests confirm review gate behavior and `/start` inline home panel parity.

### PAT-002 — Returning patient quick booking
Runtime includes trusted returning identity resolution (telegram→patient mapping + trusted phone), then quick-book suggestion callbacks (`repeat`, `same_doctor`, `other`) with stale/session guards and bounded fallback to canonical service selection. This is functional closure for PAT-002, though still based on recent-booking heuristics, not a richer preference model.

### PAT-003 — Booked patient confirmation flow
Existing booking control via `/my_booking` and reminder action handoff correctly lands users on canonical booking panels with proper state-token/session handling. Confirmation actions enforce eligible statuses and stale callback protection.

### PAT-004 — Reschedule flow
Patient-triggered reschedule is now coherent end-to-end: request reschedule, open dedicated reschedule control session, slot reselection under reschedule route-type guards, and completion via `complete_patient_reschedule` with conflict/unavailable handling and final existing-booking control handoff.

### PAT-005 — Cancel flow
Cancellation works in both direct booking control and reminder-derived continuity paths, with explicit confirm/abort prompts and canonical booking refresh after success. Runtime behavior aligns with bounded PAT cancellation expectations.

### PAT-006 — Reminder acknowledgement flow
Reminder callbacks parse/validate action payloads, enforce message-binding checks in action service, and separate `ack` semantics from booking mutation semantics. Accepted outcomes converge to canonical booking continuity while stale/invalid paths are safely rejected.

### PAT-007 — Post-visit recommendation / aftercare flow
Patient can list recommendations, open details, perform actions (ack/accept/decline), and transition into recommendation-linked product resolution. Doctor-side recommendation issuance and booking completion aftercare both include proactive patient delivery attempts with safe skip/failure behavior.

### PAT-008 — Care reserve / pickup flow
Patient care flow supports catalog/recommendation entry, product open, branch selection, reserve creation, order open/repeat/current-history presentation, and proactive pickup-ready deep link (`careo:open:*`). Callback ownership checks enforce patient-safety before opening order details.

---

## 4. Cross-scenario hidden gaps

Only evidence-backed cross-scenario issues are listed.

1. **Recent-booking heuristic as PAT-002 continuity truth**
   - **Severity:** medium
   - **Evidence:** quick-book prefill is derived from latest eligible booking (`get_recent_booking_prefill`) and applied via bounded callback options; no independent learned/stored preference object is consulted.
   - **Why it matters:** continuity can feel “mostly right” but may not represent patient intent across changed clinical contexts.
   - **Fix now or defer:** **defer** (not a closure blocker for patient branch).

2. **Scenario tests are functionally strong but physically scattered**
   - **Severity:** minor
   - **Evidence:** PAT-focused tests are spread across many root-level files (`test_patient_*`, `test_booking_*`, `test_recommendation_*`, `test_care_*`) rather than a single discoverable PAT suite tree.
   - **Why it matters:** maintainability/discoverability risk increases as staff-side scenarios expand.
   - **Fix now or defer:** **defer** (or tiny non-blocking cleanup if desired).

3. **Docs/71 lag for PAT-001, PAT-002, PAT-007**
   - **Severity:** minor
   - **Evidence:** docs/71 still marks these as Partial while runtime now supports closure-level behavior.
   - **Why it matters:** planning confusion, false “still open” narrative, wasted re-audit cycles.
   - **Fix now or defer:** **worth doing now** as documentation hygiene, but not a runtime blocker.

No blocker-grade cross-scenario contradiction/regression was found in current runtime truth.

---

## 5. Known tails assessment

### Tail 1: test organization / scattered test placement
- **Classification:** **safe to defer**
- **Rationale:** coverage quality for PAT flows is already substantial and targeted; layout is imperfect but not currently causing runtime closure risk. Re-org can be done opportunistically when opening admin/doctor scenario test packs.

### Tail 2: PAT-002 recent-pattern truth vs richer preference model
- **Classification:** **safe to defer**
- **Rationale:** current quick-book implementation is truthful about being recent-booking-driven and has fallback safety. A richer preference model is product-evolution work, not required to claim PAT closure.

---

## 6. If any PAT work remains, minimal residual PR stack

No residual PAT runtime PR is justified as a precondition to move on.

(If desired, one optional documentation-only PR to align docs/71 scenario statuses with current runtime truth is acceptable, but not required for PAT closure.)

---

## 7. Next-group recommendation

**Recommended first next group: `admin`**

### Why first
- Patient branch now generates real operational events that admins must manage next: confirmation load, reschedules, cancellations, reminder exceptions, and pickup execution.
- Admin-first gives the fastest real-clinic value unlock and risk reduction after PAT closure.

### What becomes easier because PAT is now ready
- Admin workdesk flows can rely on stable patient-triggered states/events instead of speculative interfaces.
- Cross-role continuity (patient action → admin queue/open panel/action) can be validated against stable PAT callbacks and state-token behavior.

### What should definitely NOT be tackled first
- **owner** should not be first: owner surfaces depend on trustworthy operational data/flows from admin+doctor and are less critical than front-line operational handling.

---

## 8. Final recommendation

**Move on now.** PAT-001 through PAT-008 are closure-ready in runtime truth for bounded patient-scenario scope; remaining tails are non-blocking and can be handled later or as lightweight documentation hygiene.
