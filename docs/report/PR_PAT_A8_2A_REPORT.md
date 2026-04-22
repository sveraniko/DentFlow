# PR PAT-A8-2A Report — Proactive pickup-ready Telegram notification for patient care orders

## What changed
- Added a bounded `PatientCareOrderDeliveryService.deliver_pickup_ready_if_possible(...)` for one job only: proactive pickup-ready delivery to the patient with safe skip/failure semantics.
- Hooked pickup-ready delivery at the narrow care-commerce transition seam (`CareCommerceService.apply_admin_order_action(...)`) when action `ready` transitions an order to `ready_for_pickup`.
- Wired both current admin order-action entry seams to pass locale hint and pickup branch label context into the same seam:
  - `/care_order_action ...`
  - admin pickups callback actions (`aw4cp:action:*`)
- Added Telegram sender implementation for patient care pickup-ready pushes.
- Added minimal EN/RU localized copy for pickup-ready proactive text and button.

## Exact files changed
- `app/application/care_commerce/delivery.py`
- `app/application/care_commerce/service.py`
- `app/application/care_commerce/__init__.py`
- `app/interfaces/bots/admin/router.py`
- `app/infrastructure/communication/telegram_delivery.py`
- `app/infrastructure/communication/__init__.py`
- `app/bootstrap/runtime.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_care_commerce_stack11a.py`
- `tests/test_patient_care_order_delivery_pat_a8_2a.py`
- `docs/report/PR_PAT_A8_2A_REPORT.md`

## Where the pickup-ready trigger is attached
- Trigger is attached in `CareCommerceService.apply_admin_order_action(...)` in the `action == "ready"` path, after successful status transition and reservation enforcement.
- This keeps delivery attached to the canonical domain transition seam and avoids scattering push logic.

## Trusted Telegram binding resolution
- Resolution is conservative and explicit:
  - load candidate Telegram ids for `(clinic_id, patient_id)`
  - normalize to digit-only ids
  - require exactly one trusted unique id
- Outcomes:
  - `delivered`
  - `skipped_no_binding`
  - `skipped_ambiguous_binding`
  - `skipped_unavailable`
  - `failed_safe`

## Safe skip/failure behavior
- Staff transition to `ready_for_pickup` still succeeds even when delivery is skipped or fails.
- Delivery exceptions are swallowed in a bounded fail-safe way.
- No technical failure details are pushed to patient chat.

## Tests added/updated
- Updated `tests/test_care_commerce_stack11a.py`:
  - asserts pickup-ready delivery is attempted on `ready`;
  - asserts non-`ready` action (`issue`) does not trigger another pickup-ready delivery attempt;
  - asserts skip result does not block `ready_for_pickup` transition.
- Added `tests/test_patient_care_order_delivery_pat_a8_2a.py`:
  - verifies proactive delivery uses canonical `careo:open:<care_order_id>` callback CTA;
  - verifies ambiguous binding is safely skipped.

## Environment / execution notes
- Targeted tests were run for changed modules.
- No migrations added.

## Explicit non-goals left for PAT-A8-2B
- No retry subsystem for pickup-ready notifications.
- No generic event notification framework.
- No payment/checkout changes.
- No reminder engine redesign.
- No recommendation engine redesign.
- No care-commerce state-machine redesign.
- No admin/doctor/owner flow redesign beyond narrow trigger wiring.
