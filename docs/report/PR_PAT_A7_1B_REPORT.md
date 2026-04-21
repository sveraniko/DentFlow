# PR_PAT_A7_1B Report

## What changed after PAT-A7-1A
- Hardened patient recommendation callbacks (`prec:open`, `prec:act`, `prec:products`) with explicit payload validation so malformed/manual callback data fails safely with a bounded user message.
- Kept recommendation ownership checks aligned with existing patient-resolution logic and enforced them consistently in open/action/products callbacks.
- Preserved coherent lifecycle continuity for `ack`, `accept`, and `decline`: successful actions re-render recommendation detail; invalid transitions now also re-render detail before returning a safe alert (no toast-only dead-end).
- Added optional recommendation→care CTA gating in recommendation detail: **Open recommended products** is shown only when recommendation targets resolve to at least one product through existing care-commerce resolution logic.
- Reused existing care-commerce resolution path (`resolve_recommendation_target_result`) for both CTA visibility and products callback behavior; unresolved targets keep bounded fallback messaging.

## Exact files changed
- `app/interfaces/bots/patient/router.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `locales/en.json`
- `locales/ru.json`
- `docs/report/PR_PAT_A7_1B_REPORT.md`

## Care-link continuity integration
- Recommendation detail panel now resolves target availability through existing care-commerce target resolution.
- CTA is rendered only when `resolution.products` is non-empty.
- Clicking CTA continues to use existing recommendation products callback flow and existing bounded fallback behavior when targets are unavailable.

## Stale/ownership hardening coverage
- Malformed/manual callback payloads for recommendation callbacks are now rejected safely with a non-technical message.
- Cross-patient recommendation open/action access remains blocked and covered by targeted tests.
- Callback handlers do not expose stack traces or technical internals to patients.

## Latest/history coherency
- Existing latest/history panel semantics from PAT-A7-1A were preserved.
- Lifecycle actions update recommendation status and detail immediately; panel re-entry reflects updated state consistently through existing list ordering semantics.

## Tests added/updated
Updated `tests/test_patient_home_surface_pat_a1_2.py` with focused regression coverage for:
1. malformed recommendation callback rejection,
2. cross-patient ownership protection for open/action,
3. `ack` / `accept` / `decline` continuity detail re-render,
4. CTA visibility only with resolvable targets,
5. recommendation products callback fallback via existing resolution path,
6. no new migration artifacts contract check.

## Environment / execution notes
- Targeted pytest subset was executed in this environment.
- No migrations were added in this PR.

## Closure statement
- **PAT-A7-1 is considered closed with this PR (PAT-A7-1B)** for bounded hardening scope: stale safety, ownership safety, lifecycle continuity, and optional recommendation→care continuity are now covered.

## Explicit non-goals left for PAT-A7-2 and PAT-A7-3
- No proactive push delivery (PAT-A7-2).
- No patient-facing document/export delivery.
- No recommendation-engine redesign.
- No care-commerce subsystem redesign.
- No migrations.
