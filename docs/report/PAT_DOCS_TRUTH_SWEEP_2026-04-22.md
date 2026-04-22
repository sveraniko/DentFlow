# PAT docs truth sweep report (2026-04-22)

## Scope
Minimal truth-alignment pass for:
- `docs/71_role_scenarios_and_acceptance.md`

Reference source of truth used:
- `docs/report/PAT_SCENARIO_CLOSURE_AUDIT_2026-04-22.md`
- PAT scenario audit reports for PAT-001 ... PAT-008 dated 2026-04-21/2026-04-22.

## What was corrected

1. Updated patient scenario statuses in `docs/71_role_scenarios_and_acceptance.md` to match PAT closure runtime truth:
   - PAT-001: `Partial` -> `Implemented`
   - PAT-002: `Partial` -> `Implemented`
   - PAT-007: `Partial` -> `Implemented`
   - PAT-008: verified as already `Implemented` (no status change needed)

2. Corrected PAT-001 narrative drift that contradicted runtime closure:
   - Replaced claim that runtime finalizes immediately after contact with explicit review/finalize panel truth.

3. Kept bounded caveats without reopening status:
   - PAT-002 caveat retained as heuristic/recent-booking-driven quick booking (not preference-model-driven).
   - PAT-007 caveat retained that patient-facing document delivery remains broader and tracked separately (PAT-DOC-001).

4. Updated summary/snapshot sections that were out of date:
   - Cross-role notification map row for recommendation/aftercare: `Partial` -> `Implemented`.
   - Coverage snapshot rows for PAT-001, PAT-002, PAT-007 set to `Implemented` with adjusted next-action notes.

5. Added one short factual closure note near Patient scenarios:
   - “PAT-001 ... PAT-008 are currently closure-aligned in runtime truth.”

## Exact sections/statuses changed
- `## 6. Patient scenarios`
  - Added one-line closure note.
  - PAT-001:
    - Main flow step 11 corrected to explicit review/finalize truth.
    - Status updated to `Implemented`.
    - Evidence line expanded to include `_render_review_finalize_panel`.
    - Known gaps trimmed to non-contradictory bounded gaps.
  - PAT-002:
    - Status updated to `Implemented`.
    - Evidence line expanded to include `_try_render_quick_book_suggestions`.
    - Known gap reframed to heuristic continuity caveat.
  - PAT-007:
    - Status updated to `Implemented`.

- `## 10. Cross-role notification map`
  - `Recommendation / aftercare` status updated to `Implemented`.

- `## 11. Current coverage snapshot`
  - PAT-001 status row updated to `Implemented`.
  - PAT-002 status row updated to `Implemented`.
  - PAT-007 status row updated to `Implemented`.
  - PAT-008 verified unchanged as `Implemented`.

## Confirmation of non-code scope
- No runtime code changed.
- No tests added or modified.
- No migrations added or modified.
- Only documentation files were touched for this truth sweep.

## Remaining truth ambiguities
- None that block PAT closure truth for PAT-001 ... PAT-008.
- Bounded caveat remains: PAT-002 quick booking continuity is heuristic/recent-booking driven rather than preference-model-driven.
