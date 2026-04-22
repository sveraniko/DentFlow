# PR ADM-A2B Report — Admin patient-search harmonization and patient-origin continuity hardening

## What changed
- Harmonized `/search_patient` to use the same canonical admin patient list renderer as `/admin_patients` (`_render_admin_patients`) instead of the legacy plain-text search output.
- Reused the same queue state scope (`admin_patients_state`) for `/search_patient`, so callback stale-token and continuity behavior matches `/admin_patients`.
- Preserved explicit source context metadata for harmonized search by carrying `SourceContext.ADMIN_PATIENTS` with `source_ref="search_patient:<query>"` (query retained) through patient open and booking open callbacks.
- Preserved and verified patient-origin continuity chain through booking open/back/actions:
  - search/list -> patient card -> active booking -> booking actions -> booking back -> patient card -> patient back -> patient search/list.
- Kept bounded no-active-booking and stale/manual callback safety intact.
- Narrowly updated `/search_patient` usage copy to match new operational behavior.

## Exact files changed
- `app/interfaces/bots/admin/router.py`
- `tests/test_admin_aw4_surfaces.py`
- `tests/test_search_ui_stack5a1a.py`
- `locales/en.json`
- `locales/ru.json`
- `docs/report/PR_ADM_A2B_REPORT.md`

## How `/search_patient` was harmonized with canonical search/list continuity
- Replaced `/search_patient` command runtime output from `run_patient_search(...)` plain text to canonical patient-list rendering:
  1. parse query from command text,
  2. load/save same `admin_patients_state`,
  3. call `_render_admin_patients(...)`,
  4. answer with canonical panel text + callback keyboard.
- Added `source_ref_prefix` support to `_render_admin_patients(...)` so source stays meaningful by entrypoint:
  - `/admin_patients <query>` => `source_ref="admin_patients:<query>"`
  - `/search_patient <query>` => `source_ref="search_patient:<query>"`

## How patient-origin continuity through booking actions/back was hardened
- Confirmed continuity under patient-origin context (`SourceContext.ADMIN_PATIENTS`) with preserved `source_ref` and state token.
- Covered booking actions reached from patient-origin booking card (confirm, checked-in/arrived, cancel, reschedule) and asserted continuity metadata remains patient-origin.
- Confirmed booking back from patient-origin booking (`page_or_index="patients_open:<patient_id>"`) returns to patient card.
- Confirmed patient card back returns to canonical patients list continuity.
- Confirmed stale/manual patient-origin booking back callback remains bounded.

## Tests added/updated
- Updated `tests/test_admin_aw4_surfaces.py` with focused continuity coverage:
  - `/search_patient <query>` harmonized to canonical patient list continuity
  - harmonized search -> patient card open
  - patient card -> active booking open
  - patient-origin booking actions preserve continuity metadata
  - patient-origin booking back -> patient card
  - patient card back -> canonical patients list
  - stale/manual patient-origin booking back bounded safety
- Updated `tests/test_search_ui_stack5a1a.py` message test double to accept `reply_markup` for command outputs that now include inline keyboards.

## Environment / execution
- Ran focused changed-area tests.
- Full repository suite was not run in this bounded PR.
- No environment blocker prevented targeted execution.

## ADM-A2 closure statement
- **ADM-A2 is considered closed with this PR (ADM-A2B)**.

## ADM-A2C follow-up statement
- **ADM-A2C can be skipped** as a separate implementation PR because the planned harmonization/regression net scope was completed here in bounded form.
