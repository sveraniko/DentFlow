# PR PAT-A8-2B Report — Pickup-ready notification hardening, continuity parity, and closure-proof tests

## What changed
- Hardened proactive `careo:open:*` callback handling in patient router by introducing one shared open helper used by both proactive open and manual order-open callbacks.
- Tightened malformed callback handling for proactive open (`careo:open:*`) by requiring a valid 3-part payload and bounded deny behavior.
- Canonicalized open continuity by routing both proactive open and manual order-open actions through the same render path (`_render_care_order_card`) and same ownership checks.
- Bounded duplicate/noisy trigger behavior in `CareCommerceService.apply_admin_order_action(...)` by preventing re-delivery when order is already in `ready_for_pickup` and `ready` is replayed.
- Extended focused tests for continuity parity, ownership/stale safety, safe skip behavior, unrelated action trigger discipline, and repeated-ready non-duplication.
- Updated acceptance truth for PAT-008 status to **Implemented** after hardening and tests.

## Exact files changed
- `app/interfaces/bots/patient/router.py`
- `app/application/care_commerce/service.py`
- `tests/test_patient_home_surface_pat_a1_2.py`
- `tests/test_care_commerce_stack11a.py`
- `tests/test_patient_care_order_delivery_pat_a8_2a.py`
- `docs/71_role_scenarios_and_acceptance.md`
- `docs/report/PR_PAT_A8_2B_REPORT.md`

## Continuity parity hardening
- Added `_open_patient_care_order_from_callback(...)` in patient router and used it from:
  - proactive callback `careo:open:*`
  - runtime card callback open/open_expand branches for care orders
- This removes tiny path drift and ensures push-open and manual-open resolve patient, validate ownership, and render the exact same canonical current-order surface family.

## Duplicate/incorrect trigger hardening
- In `CareCommerceService.apply_admin_order_action(...)`, the `ready` action now returns early when the order is already `ready_for_pickup`.
- This preserves status while preventing obvious duplicate proactive sends on repeated/incorrect ready-path attempts.
- Non-ready actions still do not trigger pickup-ready delivery.

## Safety/fallback coverage now locked by tests
1. proactive pickup-ready CTA opens same canonical surface as manual open
2. proactive open remains ownership-safe
3. malformed/stale proactive callback is safely rejected
4. no-binding/ambiguous binding delivery is safely skipped without blocking ready transition
5. unrelated admin actions do not trigger pickup-ready delivery
6. repeated ready on already-ready order does not duplicate proactive send
7. no migrations introduced for PAT-A8-2B

## PAT-008 closure position
- **PAT-008 is considered closed in this PR scope** (reserve/pickup continuity + proactive pickup-ready safe open hardening).

## Docs truth update
- Yes. Minimal update performed in `docs/71_role_scenarios_and_acceptance.md`:
  - PAT-008 status changed from `Partial` to `Implemented`
  - PAT-008 comment narrowed to closure-scope truth.

## Tests added/updated
- Updated `tests/test_patient_home_surface_pat_a1_2.py`
  - parity test: proactive open vs manual open same canonical detail
  - malformed/stale proactive callback safety test
  - PAT-A8-2B no migration artifact check
- Updated `tests/test_care_commerce_stack11a.py`
  - non-ready admin actions do not trigger pickup-ready delivery
  - repeated `ready` on already-ready order does not duplicate proactive delivery
- Updated `tests/test_patient_care_order_delivery_pat_a8_2a.py`
  - no-binding safe skip test

## Environment and execution
- Targeted pytest runs were executed for changed modules.
- No environment limitation blocked targeted execution.
