# PR PAT-A6-1 Report — Freeze reminder acknowledgement semantics and acceptance truth

## What changed
- Tightened PAT-006 acceptance text to freeze reminder acknowledgement semantics.
- Explicitly defined `ack` as “received/understood”, distinct from `confirm attendance`.
- Explicitly documented that `ack` does not mutate booking status.
- Explicitly documented that accepted `ack` hands off into canonical booking continuity.
- Explicitly documented that `ack` introduces no additional future-reminder suppression policy by default.

## Exact files changed
1. `docs/71_role_scenarios_and_acceptance.md`
2. `booking_docs/10_booking_flow_dental.md`
3. `booking_docs/50_booking_telegram_ui_contract.md`
4. `docs/report/PR_PAT_A6_1_REPORT.md`

## Frozen product semantics for `ack`
- `ack` means reminder acknowledgement only (“received/understood”).
- `ack` remains distinct from `confirm attendance`.
- `ack` remains one-tap because it is non-destructive.
- `ack` does not mutate booking status.
- Accepted `ack` continues into canonical patient booking continuity.
- `ack` does not add special future-reminder suppression policy by default.

## Runtime files touched
- None.
- This PR is docs-only by design to freeze product-contract truth without changing runtime behavior.

## Explicit non-goals intentionally left for PAT-A6-2
- No reminder suppression implementation.
- No booking status changes for `ack`.
- No reminder engine redesign.
- No patient-router redesign.
- No admin/doctor/owner flow changes.
- No calendar/sheets changes.
- No migrations.
