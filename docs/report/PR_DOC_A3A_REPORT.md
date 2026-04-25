# PR DOC-A3A Report — Doctor encounter completion from canonical encounter context

## What changed
- Added explicit **Complete encounter** CTA to canonical doctor encounter context keyboard.
- Added bounded two-step completion flow:
  - `denc:complete:<encounter_id>:<booking_id|->` opens confirmation prompt.
  - `denc:complete_confirm:<encounter_id>:<booking_id|->` confirms completion.
  - `denc:complete_abort:<encounter_id>:<booking_id|->` aborts and returns to encounter context.
- Added a small bounded service seam `DoctorOperationsService.complete_encounter(...)` to close encounters through existing clinical service truth (`ClinicalChartService.close_encounter`) with ownership checks.
- Encounter completion and contextual actions are now status-aware:
  - active encounter shows complete + DOC-A2 CTAs;
  - terminal encounter hides completion and contextual mutation CTAs.
- Added coherent post-completion continuity:
  - if booking context exists and is accessible, doctor is returned to canonical booking panel with concise success prefix;
  - otherwise doctor sees updated completed encounter context.
- Added bounded safety for stale/manual/terminal completion callbacks via compact localized unavailable alerts.

## Exact files changed
- `app/interfaces/bots/doctor/router.py`
- `app/application/doctor/operations.py`
- `tests/test_booking_linked_opens_12b1.py`
- `tests/test_doctor_operational_stack6a.py`
- `locales/en.json`
- `locales/ru.json`
- `docs/report/PR_DOC_A3A_REPORT.md`

## How encounter completion is performed
1. Router resolves doctor context and ownership (`_resolve_owned_encounter`).
2. Router enforces active-only completion eligibility.
3. On confirm callback, router calls `DoctorOperationsService.complete_encounter(...)`.
4. Service validates doctor ownership and delegates status transition to `clinical_service.close_encounter(encounter_id)` for non-terminal encounters.
5. Router renders success continuity (booking panel preferred; encounter panel fallback).

## How post-completion continuity works
- **With booking id**: success message + canonical booking panel (same runtime card rendering and keyboard discipline).
- **Without booking id**: success message + canonical encounter panel in completed state.
- No text-only dead-end branch is introduced.

## Tests added/updated
- Encounter panel now includes **Complete encounter** CTA for active context.
- Completed encounter context hides completion + DOC-A2 mutation CTAs.
- Completion click opens explicit confirmation prompt.
- Confirm completion invokes service/domain close path and returns coherent booking continuity.
- Abort completion keeps encounter unchanged and returns canonical encounter context.
- Stale/manual and terminal completion callbacks are bounded.
- DOC-A2 quick note/recommendation contextual actions remain present on active encounter and hidden on terminal encounter.
- Added DOC-A3A no-migrations guard test.
- Added service-level ownership + close behavior test for `complete_encounter`.

## Environment / execution limitations
- No environment limitation prevented running the targeted tests in this PR scope.

## Explicit non-goals left for DOC-A3B and DOC-A3C
- No broad booking final-state hardening beyond continuity handoff.
- No booking state machine redesign.
- No admin/owner surface changes.
- No redesign of quick-note/recommendation domain semantics.
- No patient aftercare redesign.
- No migrations.
