from __future__ import annotations

import asyncio

from app.application.care_commerce import CareCommerceService
from tests.test_care_commerce_stack11a import InMemoryCareRepo, _FakePickupReadyDelivery


def test_ready_delivery_skip_does_not_block_ready_transition() -> None:
    repo = InMemoryCareRepo()
    delivery = _FakePickupReadyDelivery(status="skipped_no_binding")
    service = CareCommerceService(repo, patient_order_delivery=delivery)
    product = asyncio.run(
        service.create_or_update_product(
            clinic_id="c1",
            sku="SKU-1",
            title_key="care.product.aftercare_brush.title",
            description_key=None,
            category="hygiene",
            price_amount=1000,
            currency_code="RUB",
            status="active",
        )
    )
    asyncio.run(
        service.set_branch_product_availability(
            clinic_id="c1",
            branch_id="b1",
            care_product_id=product.care_product_id,
            available_qty=1,
            reserved_qty=0,
        )
    )
    order = asyncio.run(
        service.create_order(
            clinic_id="c1",
            patient_id="p1",
            payment_mode="pay_at_pickup",
            currency_code="RUB",
            pickup_branch_id="b1",
            recommendation_id="r1",
            booking_id=None,
            items=[(product, 1)],
        )
    )
    asyncio.run(service.transition_order(care_order_id=order.care_order_id, to_status="confirmed"))

    ready = asyncio.run(service.apply_admin_order_action(care_order_id=order.care_order_id, action="ready", locale_hint="ru"))

    assert ready is not None and ready.status == "ready_for_pickup"
    assert delivery.calls is not None and delivery.calls[0]["locale"] == "ru"
