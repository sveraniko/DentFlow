# PR ADM-A3B Report — Linked care-order pickup bridge and linked continuity hardening

## What changed
- Added a dedicated linked care-order keyboard for admin booking-linked care-order panel (`_admin_linked_care_order_keyboard`).
- Replaced Back-only keyboard on linked care-order panel with bounded operational CTAs:
  - Open patient (always shown)
  - Open pickup handling (shown only when pickup handling is applicable)
  - Back (always shown)
- Reused canonical existing admin surfaces for both continuity actions:
  - Open patient uses canonical booking callback open-patient path.
  - Open pickup handling bridges into canonical AW4 care-pickups callback path (`aw4cp:open:*`) and existing pickup detail/queue handlers.
- Added bounded pickup applicability logic (`_linked_care_order_pickup_applicable`) so CTA is shown only for statuses where pickup handling is meaningful (`paid`, `ready_for_pickup`, `issued`).
- Added bounded queue-state bridge token helper (`_ensure_linked_pickup_bridge_token`) to preserve callback stale/token discipline when entering pickup detail from linked care-order panel.
- Preserved linked recommendation actionability from ADM-A3A unchanged.

## Exact files changed
- `app/interfaces/bots/admin/router.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_booking_linked_opens_12b1.py`
- `docs/report/PR_ADM_A3B_REPORT.md`

## How linked care-order actionability is wired now
- Booking-linked care-order open still renders the canonical linked care-order panel body.
- Keyboard now uses `_admin_linked_care_order_keyboard(...)`:
  - **Open patient** -> canonical `_encode_booking_callback(... page_or_index="open_patient")`.
  - **Open pickup handling** -> canonical AW4 pickup open callback (`aw4cp:open:<care_order_id>:<token>`), entering existing care pickup detail handler.
  - **Back** -> canonical `_encode_booking_callback(... page_or_index="open_booking")`.

## How pickup applicability is determined
- For the resolved latest booking-linked care order, pickup CTA appears only when:
  - care order exists with valid `care_order_id`, and
  - status is one of `{paid, ready_for_pickup, issued}`.
- If care order exists but status is not pickup-actionable yet (e.g. `created`), pickup CTA is intentionally hidden (operationally honest panel).

## How linked continuity parity was hardened
- Linked recommendation panel (ADM-A3A) and linked care-order panel now both present an operational first action (`Open patient`) plus bounded next-step CTA when applicable and deterministic Back to booking.
- Added explicit bridge-token state write before pickup open so canonical AW4 stale-token checks remain valid.
- Manual/unavailable pickup continuation remains bounded through existing AW4 callback safety (localized alert, no crash).

## Tests added/updated
Updated `tests/test_booking_linked_opens_12b1.py` with minimal targeted coverage for ADM-A3B:
1. linked care-order panel is no longer Back-only and includes `Open patient` + `Open pickup handling` + `Back` when applicable,
2. Open pickup handling CTA lands in canonical existing pickup detail continuity,
3. pickup CTA is hidden when linked care-order status is not pickup-applicable,
4. manual pickup open callback with missing order remains bounded,
5. linked recommendation continuity assertions from ADM-A3A remain intact.

## Environment / execution
- Focused linked-open tests were run for changed scope.
- Full repository suite was not run in this bounded continuity PR.
- No environment blocker prevented targeted execution.

## ADM-A3 closure statement
- **ADM-A3 is considered closed with this PR (ADM-A3B)**:
  - linked recommendation panel actionability delivered in ADM-A3A,
  - linked care-order -> pickup operational bridge delivered in ADM-A3B,
  - linked continuity parity and bounded stale/manual handling covered in targeted tests.
