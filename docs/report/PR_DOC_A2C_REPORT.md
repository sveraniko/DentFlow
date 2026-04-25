# PR DOC-A2C Report — Doctor pending text capture unification and contextual action hardening

## What changed
- Replaced competing doctor router generic text handlers with a single deterministic dispatcher:
  - `doctor_pending_text_capture` (`@router.message(F.text)`)
- Split quick-note and recommendation capture internals into focused helpers:
  - `_capture_pending_quick_note_text(...)`
  - `_capture_pending_recommendation_text(...)`
- Preserved existing callback entry points and command fallbacks:
  - `/encounter_note ...`
  - `/recommend_issue ...`
- Added slash-message safety in unified dispatcher (messages beginning with `/` are ignored).
- Added deterministic ambiguous-state handling when both pending contexts exist.

## Exact files changed
- `app/interfaces/bots/doctor/router.py`
- `tests/test_booking_linked_opens_12b1.py`
- `docs/report/PR_DOC_A2C_REPORT.md`

## How pending text dispatch is now modeled
Single dispatcher flow in deterministic order:
1. Resolve pending quick-note context.
2. Resolve pending recommendation context.
3. If both exist (ambiguous), apply bounded tie-break policy (newer context wins by `created_at`; older context is cleared).
4. If note context is active, capture as quick note.
5. Else if recommendation context is active, capture recommendation target/text.
6. Else do nothing (plain unrelated text is not hijacked).

This removes runtime ambiguity from two competing `@router.message(F.text)` handlers.

## How ambiguous pending state is handled
Policy implemented:
- If both pending note and pending recommendation contexts exist for one Telegram user:
  - compare `created_at`
  - keep the newer context
  - clear the older context
- If timestamps are equal, quick-note path wins (deterministic because comparison keeps recommendation only when it is strictly newer).

Safety guarantees:
- Text is never written into both flows.
- Cleanup avoids stale dual pending state surviving after dispatch.

## How quick-note and recommendation behavior were preserved
Quick-note behavior preserved:
- captures only with pending note context,
- calls `DoctorOperationsService.add_encounter_note(...)`,
- clears pending note context on success/failure and on cancel/TTL,
- returns to canonical encounter context panel on success,
- keeps `/encounter_note` command fallback unchanged.

Recommendation behavior preserved:
- target-code capture still works with `awaiting_target_code=True`,
- validates `product:<code>` / `category:<code>` through existing care-commerce seams,
- no-target path remains supported,
- `Title | Body` parsing preserved,
- calls `DoctorOperationsService.issue_recommendation(...)`,
- patient aftercare delivery path remains unchanged,
- clears pending recommendation context on success/failure and on cancel/TTL,
- returns to canonical encounter context panel on success,
- keeps `/recommend_issue` command fallback unchanged.

## Tests added/updated
Updated existing router-flow tests to use the real unified generic text capture handler:
- quick-note capture tests now invoke `doctor_pending_text_capture`
- recommendation capture tests now invoke `doctor_pending_text_capture`

Added focused tests:
- slash command text is not captured by pending dispatcher,
- ambiguous note+recommend pending state is handled deterministically (newer recommendation wins in tested path),
- no DOC-A2C migration artifacts are introduced.

## Environment / execution notes
- Targeted doctor router tests were executed in this environment.
- No migrations were created.

## DOC-A2 closure statement
**DOC-A2 is considered closed with this PR (DOC-A2C).**

Reasoning:
- runtime-risk from competing doctor generic text handlers is removed,
- quick-note and recommendation contextual captures both execute via one deterministic real router text path,
- command fallbacks remain intact,
- bounded ambiguous-state safety is now explicit and tested.
