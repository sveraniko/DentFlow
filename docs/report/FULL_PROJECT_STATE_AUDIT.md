# 1. Executive Summary

> **Outdated claim notice (added 2026-04-20):** Some claims in this legacy audit are now outdated. For current convergence state, use `docs/report/CONVERGENCE_PACK_DELTA_AUDIT_2026-04-20.md` as the source of truth. Superseded categories include projector runtime integration status and card runtime/callback codec integration in real routes.

DentFlow has a **solid architectural skeleton** (bounded modules, repositories, events, projections, card runtime primitives), but the current runtime is **not fully converged** with the documented target state.

The biggest practical findings:
- Several “completed” waves are only partially complete in real runtime UX (especially linked object flows in Admin/Doctor booking cards).
- Projection architecture exists, but production runtime execution still depends heavily on manual scripts instead of an always-on projector worker path.
- Unified cards are real in multiple paths, but legacy callback/text paths are still active in key patient and operational flows.
- Google Calendar projection is integrated as one-way projection, but admin-side “calendar mirror” operational surface is still missing in interface layer.
- i18n baseline is strong for key-based strings, yet some user-facing hardcoded/status-origin/debug strings still leak.

Overall readiness: **pilot-capable in narrow controlled scope**, but not fully aligned with roadmap claims for end-to-end operational closure.

---

# 2. Method Used

1. Reviewed required authoritative docs in the requested precedence order (README, architecture/rules, UI/i18n/domain/state/data/events/search/analytics/care-commerce/admin/calendar/unified-card/test-launch docs).
2. Reviewed completed-wave reports in `docs/report/` (Stack, CC, UC, AW families) with special focus on claims of closure/hardening.
3. Inspected actual runtime code paths in:
   - bootstrap/runtime wiring,
   - bot routers (patient/admin/doctor/owner),
   - card callback/runtime modules,
   - application services,
   - repositories and projectors,
   - worker and scripts,
   - search/voice/calendar adapters.
4. Checked for adapter-only completion, runtime wiring gaps, legacy dominance, placeholders/stubs, source-of-truth drift, localization/timezone leaks, and test blind spots.

This report is based on **code reality over report claims** when conflicts existed.

---

# 3. Document/Code Alignment Assessment

## Strong alignment areas
- Layered architecture and bounded contexts are materially present.
- Booking state/orchestration and repository split follow documented structure.
- Search model baseline (strict + hybrid backend, projector, Meili fallback) is implemented.
- Card runtime token model and stale callback guard semantics are implemented.
- Admin workdesk read-model tables/services exist and are used by admin surfaces.

## Partial alignment areas
- Unified card “object-first linked navigation” is incomplete in admin/doctor linked opens.
- AW closure is partial: core queues exist, but full calendar/admin mirror surface and richer object drilldown are missing.
- Care-commerce object wave is close for patient journey but not equivalent across admin/doctor linked opens.
- Projection backbone is architected, but runtime processing is script-driven/manual rather than fully integrated into worker lifecycle.

## Drift areas
- Some “completed” report language is ahead of actual runtime behavior (notably linked-open fidelity and object depth).
- Owner analytics service mixes direct transactional/hot queries with projection reads, weakening read-model discipline.

---

# 4. Major Areas Audited

A. Core booking foundation  
B. Search / voice retrieval  
C. Doctor operational layer  
D. Clinical chart baseline  
E. Event / projector / analytics backbone  
F. Owner analytics baseline  
G. Recommendation engine  
H. Care-commerce / product-card wave  
I. Unified card system wave (UC)  
J. Admin operational workdesk wave (AW)  
K. Google Calendar projection  
L. Cross-cutting concerns (i18n, runtime state, stale callbacks, role guards, timezone semantics, legacy fallback paths, read model discipline, testing depth)

---

# 5. What Is Truly Production-Ready

- **Booking domain + orchestration core** (state transitions, typed outcomes, persistence boundaries).
- **Reminder planning/delivery/recovery baseline** with dedicated worker tasks.
- **Core patient search flow** with strict Postgres + optional Meili hybrid fallback.
- **Voice search envelope** (mode activation, size/duration/error handling, STT abstraction).
- **Card callback tokenization/stale decode framework** with compact callback transport and runtime token store abstraction.
- **Admin workdesk read services** for today/confirmations/reschedules/waitlist/care-pickups/issues.
- **Google Calendar projection service + real gateway option** (when enabled and configured).
- **Care-commerce core domain operations** (reserve/order lifecycle and repeat baseline).

---

# 6. What Exists But Is Only Partial / Adapter-Level / Stub-Level

## Issue 1 — Booking linked opens still contain placeholder/stub targets
- **Classification:** MAJOR GAP  
- **Area/Wave:** UC / AW / Doctor ops  
- **Evidence:**
  - Admin booking callbacks still render placeholder text for recommendation/care order (`"recommendation :: patient=..."`, `"care_order :: patient=..."`).
  - Doctor booking callbacks still render placeholder care-order text and minimal recommendation title-only panel.
- **Why it matters:** Breaks “object-first linked flow” contract and undermines card-wave closure.
- **Suggested next PR:** Completion PR to replace admin/doctor linked-open stubs with real recommendation and care-order object cards.

## Issue 2 — Calendar integration exists, but admin calendar UI surface is not actually present
- **Classification:** MAJOR GAP  
- **Area/Wave:** AW / Google Calendar  
- **Evidence:** No admin router calendar command/panel path for mirror browsing; calendar integration is projector-side only.
- **Why it matters:** Docs/UI contracts call for operational calendar visibility; current runtime offers sync without admin-facing mirror UX.
- **Suggested next PR:** Integration PR adding explicit admin calendar mirror panel backed by projection tables.

## Issue 3 — Projector stack implemented but not integrated into main worker runtime loop
- **Classification:** BLOCKER  
- **Area/Wave:** Events/Projections backbone  
- **Evidence:** `app/worker.py` runs reminder tasks only; outbox projector processing is script-based (`scripts/process_outbox_events.py`) not first-class worker task.
- **Why it matters:** Projection freshness and eventual consistency depend on manual/cron discipline, increasing production drift risk.
- **Suggested next PR:** Hardening PR to register projector runner as managed worker task with checkpoint/observability semantics.

## Issue 4 — Some unified-card profile claims are adapter-level outside patient flow
- **Classification:** MAJOR GAP  
- **Area/Wave:** UC / CC / AW  
- **Evidence:** Product and care-order card richness is concentrated in patient flow; admin/doctor linked opens still often map to text summaries/back buttons rather than equivalent card-profile runtime.
- **Why it matters:** Cross-role contract consistency is not achieved; card system behaves as role-fragmented implementation.
- **Suggested next PR:** Completion PR to standardize linked object rendering across admin/doctor with same shell/profile principles.

## Issue 5 — Voice path is operationally real but production defaults favor disabled/fake behavior
- **Classification:** MEDIUM TAIL  
- **Area/Wave:** Search / voice  
- **Evidence:** STT config defaults are `enabled=False`, `provider=fake`; disabled provider returns failure path.
- **Why it matters:** Real voice retrieval can be perceived “implemented” while default deployment path is inert unless explicit config hardening is done.
- **Suggested next PR:** Hardening PR for deployment profile presets + startup validation for pilot/prod voice expectations.

---

# 7. What Still Depends On Legacy Paths

## Issue 6 — Patient router still maintains broad legacy callback families alongside runtime card callbacks
- **Classification:** MEDIUM TAIL  
- **Area/Wave:** UC / Booking / Care-commerce  
- **Evidence:** Active callback handlers for `book:*`, `mybk:*`, `care:*`, `rem:*` coexist with `c2|` runtime callback path.
- **Why it matters:** Increases behavioral divergence and maintenance risk; “legacy tail” still significant, not purely inert.
- **Suggested next PR:** Completion/hardening PR to formally demote legacy routes and gate them to stale-compatibility only.

## Issue 7 — Owner surfaces remain command/text-panel centric rather than card/object-centric
- **Classification:** MEDIUM TAIL  
- **Area/Wave:** Owner analytics / UC consistency  
- **Evidence:** owner router exposes command-based textual cards and alert open text details, no unified card-style object navigation.
- **Why it matters:** Product interaction model diverges by role and weakens unified UI contracts.
- **Suggested next PR:** Defer unless owner-card wave is accepted scope; otherwise integration PR.

## Issue 8 — Legacy callback decode support remains open-ended
- **Classification:** MINOR POLISH  
- **Area/Wave:** UC callback contract  
- **Evidence:** callback codec still decodes legacy `c1` payload format.
- **Why it matters:** Not harmful by itself, but without sunset policy it prevents true closure.
- **Suggested next PR:** Define deprecation gate/date and telemetry-driven removal plan.

---

# 8. What Is Missing Entirely

## Issue 9 — No integrated projector daemon task in worker lifecycle
- **Classification:** BLOCKER  
- **Area/Wave:** Events/analytics/search/admin projections  
- **Evidence:** Worker registers heartbeat/reminder tasks only; projector runner invoked by scripts.
- **Why it matters:** Core architecture depends on projections for multiple surfaces; without automated loop, freshness is fragile.
- **Suggested next PR:** Worker integration PR (projector task scheduling + backoff + metrics).

## Issue 10 — Admin calendar mirror operational panel/flow absent
- **Classification:** MAJOR GAP  
- **Area/Wave:** AW / Google Calendar  
- **Evidence:** No `/admin_calendar` equivalent, no calendar panel callbacks in admin router.
- **Why it matters:** Documented AW surface is not available to users.
- **Suggested next PR:** New feature/integration PR scoped to read-only mirror first.

## Issue 11 — Full recommendation/care-order linked object drilldown from booking card is absent for admin/doctor
- **Classification:** MAJOR GAP  
- **Area/Wave:** UC/CC/AW/Doctor ops  
- **Evidence:** Linked-open fallback texts/minimal panels instead of object cards.
- **Why it matters:** Breaks fidelity requirement for linked object flow and prevents end-to-end card behavior claims.
- **Suggested next PR:** Completion PR with dedicated adapters/builders + callbacks for these linked objects.

## Issue 12 — No explicit projection-health/readiness gate in runtime start
- **Classification:** MEDIUM TAIL  
- **Area/Wave:** Launch hardening  
- **Evidence:** Runtime bootstrap does not validate projector lag/checkpoint health for projection-dependent features.
- **Why it matters:** System may appear healthy while operational read models are stale.
- **Suggested next PR:** Hardening PR introducing projection lag checks in health endpoints/startup diagnostics.

---

# 9. Localization / Timezone / Runtime-State Issues

## Issue 13 — Hardcoded user-facing English/debug text leaks remain
- **Classification:** MAJOR GAP  
- **Area/Wave:** i18n / UC linked flows  
- **Evidence:** Literal text outputs such as `"recommendation :: patient=..."`, `"care_order :: patient=..."`, and some adapter-derived English phrases.
- **Why it matters:** Violates localization discipline and degrades multilingual UX.
- **Suggested next PR:** Completion PR replacing hardcoded text with localized object panels.

## Issue 14 — Search result lines expose raw status/origin codes to users
- **Classification:** MEDIUM TAIL  
- **Area/Wave:** Search UI/i18n  
- **Evidence:** search handlers append `row.status` and `row.origin.value` directly.
- **Why it matters:** Operational/debug internals leak into user surfaces and are not localized/humanized.
- **Suggested next PR:** Polish PR to map status/origin to localized labels and optionally hide origin outside debug mode.

## Issue 15 — Runtime state storage falls back to process-local memory in non-prod environments
- **Classification:** INTENTIONAL NON-GOAL (with risk note)  
- **Area/Wave:** UC runtime/Redis  
- **Evidence:** runtime Redis builder uses in-memory adapter unless app env is prod/production.
- **Why it matters:** Acceptable for local/test, but can mask multi-worker issues in staging-like envs.
- **Suggested next PR:** Optional hardening to allow explicit redis-in-dev toggle and warn on non-shared runtime when multiple workers run.

## Issue 16 — Timezone semantics are mostly correct in booking/admin flows but uneven in some textual summaries
- **Classification:** MEDIUM TAIL  
- **Area/Wave:** Timezone/local-day correctness  
- **Evidence:** Local-day aware admin and booking snapshot paths exist; some textual fallback panels still bypass richer localized/timezone-aware card fields.
- **Why it matters:** Inconsistent visible-time behavior across surfaces may confuse staff.
- **Suggested next PR:** Completion pass to route linked/text fallback panels through same snapshot/local-time formatters.

---

# 10. Cross-Wave Architecture Risks

## Risk A — Projection-dependent surfaces without continuously managed projector runtime
- **Severity:** BLOCKER
- **Impact:** Admin/owner/search/calendar surfaces can silently diverge from transactional truth.

## Risk B — Wave “completion” labels can obscure object-flow incompleteness
- **Severity:** MAJOR GAP
- **Impact:** Planning may prematurely shift to new waves while current role-critical linked flows are still stub-level.

## Risk C — Dual-path UX (legacy callbacks + card callbacks) increases regression surface
- **Severity:** MEDIUM TAIL
- **Impact:** Harder QA, stale behavior drift, and inconsistent callbacks across chat histories.

## Risk D — Mixed read-model discipline in owner analytics services
- **Severity:** MEDIUM TAIL
- **Impact:** Architectural drift from projection-first intent and potential query-cost unpredictability.

---

# 11. Testing Gaps

## Issue 17 — Heavy test focus on adapters/helpers/service units vs role-level conversational end-to-end flows
- **Classification:** MAJOR GAP  
- **Area/Wave:** Test strategy  
- **Evidence:** Strong unit/integration slices exist, but limited full-flow tests for admin/doctor linked object journeys and mixed callback staleness paths.
- **Why it matters:** Critical UX regressions can pass while helper-level tests remain green.
- **Suggested next PR:** Hardening PR adding high-value role flow scenario tests (admin booking card linked opens, doctor booking linked opens, calendar mirror navigation once added).

## Issue 18 — Projection processing reliability not covered as a continuous-runtime test concern
- **Classification:** MAJOR GAP  
- **Area/Wave:** Event/projector backbone  
- **Evidence:** Tests validate projector logic, but not worker-level continuous processing guarantees.
- **Why it matters:** Real lag/failure behavior can remain untested in deployment topology.
- **Suggested next PR:** Hardening PR with worker integration tests and failure/recovery checkpoint behavior.

## Issue 19 — Limited explicit regression tests for localization leakage in linked fallback panels
- **Classification:** MEDIUM TAIL  
- **Area/Wave:** i18n  
- **Evidence:** Core locale key coverage is strong, but hardcoded linked-open placeholders persisted.
- **Why it matters:** Locale quality regressions can remain unnoticed.
- **Suggested next PR:** Add assertion coverage for zero raw placeholder/debug text in user-facing outputs.

---

# 12. Priority Gap List

1. **[BLOCKER]** Integrate projector runner into worker lifecycle (continuous outbox processing).
2. **[MAJOR GAP]** Replace admin/doctor booking linked-open stubs with real recommendation/care-order object cards.
3. **[MAJOR GAP]** Implement admin calendar mirror panel/flow using projection data.
4. **[MAJOR GAP]** Add role-level end-to-end tests for linked object navigation and stale callback handling.
5. **[MEDIUM TAIL]** Converge/remediate legacy callback paths and enforce explicit compatibility-only scope.
6. **[MEDIUM TAIL]** Remove raw status/origin/user-facing debug strings from search/linked flows.
7. **[MEDIUM TAIL]** Tighten owner read-model discipline (projection-first where intended).

---

# 13. Recommended Next 5 PRs

## PR-1: Projector Worker Integration
- **Type:** integration + hardening
- **Why first:** Projection freshness underpins admin/search/owner/calendar surfaces.
- **Scope boundary:** worker task registration, scheduling/backoff/checkpoints/metrics only; no schema redesign.

## PR-2: Admin/Doctor Linked Object Card Completion
- **Type:** completion
- **Why second:** Eliminates prominent stub behavior in operational booking card flows.
- **Scope boundary:** `open_recommendation` and `open_care_order` callbacks to real object cards + back navigation; no major new domain behavior.

## PR-3: Admin Calendar Mirror UI Surface
- **Type:** integration + new feature
- **Why third:** closes AW calendar contract gap after projection reliability is stabilized.
- **Scope boundary:** read-only operational panel/list/detail from projection data; avoid two-way calendar edits.

## PR-4: Legacy Callback Demotion + Compatibility Gate
- **Type:** completion + hardening
- **Why fourth:** reduces dual-path drift and callback inconsistency.
- **Scope boundary:** annotate legacy handlers as compatibility-only, telemetry and expiry policy, route new actions exclusively through `c2|`.

## PR-5: Pilot QA Hardening Pack
- **Type:** hardening
- **Why fifth:** converts implemented behavior into launch confidence.
- **Scope boundary:** role-level flow tests, localization-leak checks, projection lag checks, no product-scope expansion.

---

# 14. Recommended Do-Not-Touch / Stable Areas

- Booking state machine core and orchestration transition guards.
- Reminder planning/delivery/recovery baseline behavior.
- Card callback tokenization contract (`c2|`) and stale callback decode semantics.
- Care-commerce core reservation/order lifecycle rules already validated by existing tests.

These areas should be changed only via tightly scoped PRs with explicit regression coverage.

---

# 15. Final Readiness Assessment

DentFlow is **not yet fully wave-closed** across UC/AW/CC in strict product-contract terms.

Current state is best described as:
- **Foundation-strong** (architecture, domains, repositories, adapters, baseline flows),
- **Operationally partial** (notably linked object fidelity and projection runtime integration),
- **Pilot-possible with controlled scope** but with meaningful risks if treated as fully complete.

If the top 3 gaps (projector worker integration, linked object card completion, admin calendar mirror) are closed in order, readiness would move from “partial pilot” to “credible production baseline” much more convincingly.
