# P0-07C Manual Telegram Run Matrix

Date: 2026-04-29
Tester: manual operator
Bot: @Dent_Flow_bot (patient bot, polling mode)
DB: dentflow_test (local, safe)

## Flow Matrix

| # | Flow | Steps | Expected | Result | Evidence | Log notes | Fix needed |
|---|------|-------|----------|--------|----------|-----------|------------|
| A | Start/Home | /start | Readable home, buttons: booking, My Booking, Recommendations, Care. No old scaffold text. | PASS | Screenshot: home panel renders correctly with 4 buttons. | No errors in log. | — |
| B | My Booking | Tap My Booking | Readable booking card. No Actions/Channel/telegram/raw IDs/UTC/MSK leaks. | PENDING | — | — | — |
| C | New Booking basic path | Booking > consultation > public doctor/any doctor > slot > contact > review > confirm | Booking created, My Booking updated. | NOTE | Booking flow works. Slot picker, contact prompt panels remain visible in chat after pressing Home. Old panels are functionally dead (expired callbacks). | Updates handled OK, no traceback. | Non-blocker: old intermediate panels not cleaned up on Home navigation. UX polish for future. |
| D | Protected doctor code | Booking > treatment > doctor code > IRINA-TREAT > slot > contact > review > confirm | Dr. Irina resolves by code, hidden from public list. | PENDING | — | — | — |
| E | Slot conflict/unavailable | Attempt same slot from second session if practical | Inline unavailable notice, no dead end. | PENDING | — | — | — |
| F | Review edit actions | Reach review > edit service/doctor/time/phone | Review updates, no stale values. | PENDING | — | — | — |
| G | Recommendations | Open recommendations > active/history/all filters > open detail > ack/accept/decline | Inline notices, not popup-only. | PENDING | — | — | — |
| H | Recommendation products | Open product-linked recommendation > open recommended products > product card | Product card clean, manual invalid case recovery if accessible. | PENDING | — | — | — |
| I | Care catalog | Open care > categories > product list > product card | No raw/debug fields. | PENDING | — | — | — |
| J | Care reserve | Open in-stock product SKU-BRUSH-SOFT > reserve | Order created, order detail readable. | PENDING | — | — | — |
| K | Out-of-stock | Open SKU-GEL-REMIN > try reserve if button | Reserve blocked, no invalid order, recovery panel. | PENDING | — | — | — |
| L | Repeat/reorder | Open care order > repeat/reorder | New order or safe stock constraint message. No raw view.text/debug. | PENDING | — | — | — |
| M | Navigation audit | Randomly test Back/Home from deep panels | No dead ends, no mandatory /start recovery. | PENDING | — | — | — |

## Summary

- Total flows: 13
- PASS: 1
- BLOCKER: 0
- NOTE: 1
- PENDING: 11

## Status: AWAITING MANUAL EXECUTION
