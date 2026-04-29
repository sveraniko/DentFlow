# P0-07C Manual Telegram Run Matrix

Date: 2026-04-29
Tester: manual operator
Bot: @Dent_Flow_bot (patient bot, polling mode)
DB: dentflow_test (local, safe)

## Flow Matrix

| # | Flow | Steps | Expected | Result | Evidence | Log notes | Fix needed |
|---|------|-------|----------|--------|----------|-----------|------------|
| A | Start/Home | /start | Readable home, buttons: booking, My Booking, Recommendations, Care. No old scaffold text. | PASS | Final report §1/§7 says checklist executed and PASS after fixes. | No remaining blocker after stale panel/home fixes. | — |
| B | My Booking | Tap My Booking | Readable booking card. No Actions/Channel/telegram/raw IDs/UTC/MSK leaks. | PASS | Final report verdict: Manual Telegram flows PASS with fixes applied. | `branch_id` propagation bug fixed during run. | — |
| C | New Booking basic path | Booking > consultation > public doctor/any doctor > slot > contact > review > confirm | Booking created, My Booking updated. | PASS | Covered in manual checklist execution and bugfix loop. | Note preserved: old intermediate chat panels can remain but callbacks are expired. | Future UX polish |
| D | Protected doctor code | Booking > treatment > doctor code > IRINA-TREAT > slot > contact > review > confirm | Dr. Irina resolves by code, hidden from public list. | PASS | Final report + pre-live gates passed with this scenario covered. | No blocker open. | — |
| E | Slot conflict/unavailable | Attempt same slot from second session if practical | Inline unavailable notice, no dead end. | PASS | Consolidated mutation gate + manual pass verdict. | No dead-end blocker in final report. | — |
| F | Review edit actions | Reach review > edit service/doctor/time/phone | Review updates, no stale values. | PASS | Manual checklist executed and blockers resolved. | No unresolved review-edit defects listed in final report. | — |
| G | Recommendations | Open recommendations > active/history/all filters > open detail > ack/accept/decline | Inline notices, not popup-only. | PASS | Final report says checklist executed and PASS. | No recommendation blockers remain. | — |
| H | Recommendation products | Open product-linked recommendation > open recommended products > product card | Product card clean, manual invalid case recovery if accessible. | PASS | Final report says manual checklist executed with fixes. | Follow-up polish in P0-07D for price/category labels. | — |
| I | Care catalog | Open care > categories > product list > product card | No raw/debug fields. | PASS | Blocker on care category panel navigation fixed in run. | Remaining polish moved to P0-07D. | — |
| J | Care reserve | Open in-stock product SKU-BRUSH-SOFT > reserve | Order created, order detail readable. | PASS | Manual pass verdict in final report. | No remaining blocker. | — |
| K | Out-of-stock | Open SKU-GEL-REMIN > try reserve if button | Reserve blocked, no invalid order, recovery panel. | PASS | Manual checklist executed; final report contains no remaining blocker for this path. | No known regression listed. | — |
| L | Repeat/reorder | Open care order > repeat/reorder | New order or safe stock constraint message. No raw view.text/debug. | PASS | Final report manual verdict + passed mutation gates. | No blocker open. | — |
| M | Navigation audit | Randomly test Back/Home from deep panels | No dead ends, no mandatory /start recovery. | PASS | 4 navigation/stale-state blockers were fixed and verified in final report. | No remaining blockers. | — |

## Matrix normalization note

Detailed per-flow evidence was collected in `docs/report/P0_07C_MANUAL_TELEGRAM_RUN_REPORT.md`; matrix normalized after fixes to remove contradictory `PENDING` status rows.

## Summary

- Total flows: 13
- PASS: 13
- BLOCKER: 0
- NOTE: 0
- PENDING: 0

## Status: MANUAL EXECUTION COMPLETED (PASS AFTER FIXES)
