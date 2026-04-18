from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.application.care_commerce import CareCommerceService
from app.application.doctor.operations import DoctorOperationsService
from app.application.recommendation import RecommendationService
from app.common.i18n import I18nService
from app.domain.booking import Booking
from app.domain.care_commerce import CareOrder, CareOrderItem, CareProduct, CareReservation, RecommendationProductLink
from app.domain.recommendations import Recommendation


class InMemoryCareRepo:
    def __init__(self) -> None:
        self.products: dict[str, CareProduct] = {}
        self.links: dict[str, list[RecommendationProductLink]] = {}
        self.orders: dict[str, CareOrder] = {}
        self.order_items: dict[str, list[CareOrderItem]] = {}
        self.reservations: dict[str, list[CareReservation]] = {}

    async def upsert_product(self, product: CareProduct) -> CareProduct:
        self.products[product.care_product_id] = product
        return product

    async def get_product(self, care_product_id: str) -> CareProduct | None:
        return self.products.get(care_product_id)

    async def list_active_products_by_clinic(self, *, clinic_id: str) -> list[CareProduct]:
        return [row for row in self.products.values() if row.clinic_id == clinic_id and row.status == "active"]

    async def link_product_to_recommendation(self, link: RecommendationProductLink) -> RecommendationProductLink:
        self.links.setdefault(link.recommendation_id, [])
        self.links[link.recommendation_id] = [row for row in self.links[link.recommendation_id] if row.care_product_id != link.care_product_id] + [link]
        return link

    async def list_products_by_recommendation(self, *, recommendation_id: str) -> list[tuple[RecommendationProductLink, CareProduct]]:
        rows = sorted(self.links.get(recommendation_id, []), key=lambda x: x.relevance_rank)
        return [(row, self.products[row.care_product_id]) for row in rows]

    async def create_order(self, order: CareOrder, items: list[CareOrderItem]) -> CareOrder:
        self.orders[order.care_order_id] = order
        self.order_items[order.care_order_id] = items
        return order

    async def get_order(self, care_order_id: str) -> CareOrder | None:
        return self.orders.get(care_order_id)

    async def list_order_items(self, care_order_id: str) -> list[CareOrderItem]:
        return self.order_items.get(care_order_id, [])

    async def save_order(self, order: CareOrder) -> CareOrder:
        self.orders[order.care_order_id] = order
        return order

    async def list_orders_for_patient(self, *, patient_id: str, clinic_id: str) -> list[CareOrder]:
        return [row for row in self.orders.values() if row.patient_id == patient_id and row.clinic_id == clinic_id]

    async def list_orders_for_admin(self, *, clinic_id: str, statuses: tuple[str, ...], limit: int = 30) -> list[CareOrder]:
        return [row for row in self.orders.values() if row.clinic_id == clinic_id and row.status in statuses][:limit]

    async def create_reservation(self, reservation: CareReservation) -> CareReservation:
        self.reservations.setdefault(reservation.care_order_id, []).append(reservation)
        return reservation

    async def save_reservation(self, reservation: CareReservation) -> CareReservation:
        rows = self.reservations.get(reservation.care_order_id, [])
        self.reservations[reservation.care_order_id] = [reservation if x.care_reservation_id == reservation.care_reservation_id else x for x in rows]
        return reservation

    async def list_reservations_for_order(self, *, care_order_id: str) -> list[CareReservation]:
        return self.reservations.get(care_order_id, [])


class InMemoryRecommendationRepository:
    def __init__(self) -> None:
        self.rows: dict[str, Recommendation] = {}

    async def get(self, recommendation_id: str) -> Recommendation | None:
        return self.rows.get(recommendation_id)

    async def save(self, item: Recommendation) -> None:
        self.rows[item.recommendation_id] = item

    async def list_for_patient(self, *, patient_id: str, include_terminal: bool = False) -> list[Recommendation]:
        return [x for x in self.rows.values() if x.patient_id == patient_id]

    async def list_for_booking(self, *, booking_id: str) -> list[Recommendation]:
        return [x for x in self.rows.values() if x.booking_id == booking_id]

    async def list_for_chart(self, *, chart_id: str) -> list[Recommendation]:
        return [x for x in self.rows.values() if x.chart_id == chart_id]


def test_product_link_order_and_metadata() -> None:
    repo = InMemoryCareRepo()
    service = CareCommerceService(repo)
    p1 = asyncio.run(service.create_or_update_product(clinic_id="c1", sku="SKU-1", title_key="care.product.aftercare_brush.title", description_key=None, category="hygiene", price_amount=1500, currency_code="RUB", status="active"))
    p2 = asyncio.run(service.create_or_update_product(clinic_id="c1", sku="SKU-2", title_key="care.product.aftercare_irrigator.title", description_key=None, category="hygiene", price_amount=7000, currency_code="RUB", status="active"))
    asyncio.run(service.link_product_to_recommendation(recommendation_id="r1", care_product_id=p2.care_product_id, relevance_rank=2, justification_key="clinical", justification_text_key="just.2"))
    asyncio.run(service.link_product_to_recommendation(recommendation_id="r1", care_product_id=p1.care_product_id, relevance_rank=1, justification_key="clinical", justification_text_key="just.1"))

    rows = asyncio.run(service.list_products_by_recommendation(recommendation_id="r1"))
    assert [product.care_product_id for _, product in rows] == [p1.care_product_id, p2.care_product_id]
    assert rows[0][0].justification_text_key == "just.1"


def test_care_order_and_reservation_lifecycle_and_invalid_transition() -> None:
    repo = InMemoryCareRepo()
    service = CareCommerceService(repo)
    product = asyncio.run(service.create_or_update_product(clinic_id="c1", sku="SKU-1", title_key="care.product.aftercare_brush.title", description_key=None, category="hygiene", price_amount=1000, currency_code="RUB", status="active"))

    order = asyncio.run(service.create_order(clinic_id="c1", patient_id="p1", payment_mode="pay_at_pickup", currency_code="RUB", pickup_branch_id="b1", recommendation_id="r1", booking_id=None, items=[(product, 2)]))
    assert order.total_amount == 2000
    confirmed = asyncio.run(service.transition_order(care_order_id=order.care_order_id, to_status="confirmed"))
    ready = asyncio.run(service.transition_order(care_order_id=order.care_order_id, to_status="ready_for_pickup"))
    issued = asyncio.run(service.transition_order(care_order_id=order.care_order_id, to_status="issued"))
    fulfilled = asyncio.run(service.transition_order(care_order_id=order.care_order_id, to_status="fulfilled"))
    assert confirmed and ready and issued and fulfilled
    assert fulfilled.status == "fulfilled"

    with pytest.raises(ValueError):
        asyncio.run(service.transition_order(care_order_id=order.care_order_id, to_status="paid"))

    reservation = asyncio.run(service.create_reservation(care_order_id=order.care_order_id, care_product_id=product.care_product_id, branch_id="b1", reserved_qty=1))
    consumed = asyncio.run(service.consume_reservation(care_reservation_id=reservation.care_reservation_id, care_order_id=order.care_order_id))
    assert consumed and consumed.status == "consumed"


def test_reservation_is_integrated_into_ready_issue_cancel_admin_flow() -> None:
    repo = InMemoryCareRepo()
    service = CareCommerceService(repo)
    product = asyncio.run(service.create_or_update_product(clinic_id="c1", sku="SKU-1", title_key="care.product.aftercare_brush.title", description_key=None, category="hygiene", price_amount=1000, currency_code="RUB", status="active"))
    order = asyncio.run(service.create_order(clinic_id="c1", patient_id="p1", payment_mode="pay_at_pickup", currency_code="RUB", pickup_branch_id="b1", recommendation_id="r1", booking_id=None, items=[(product, 2)]))
    asyncio.run(service.transition_order(care_order_id=order.care_order_id, to_status="confirmed"))

    ready = asyncio.run(service.apply_admin_order_action(care_order_id=order.care_order_id, action="ready"))
    reservations = asyncio.run(service.repository.list_reservations_for_order(care_order_id=order.care_order_id))
    assert ready and ready.status == "ready_for_pickup"
    assert len(reservations) == 1
    assert reservations[0].status == "created"
    assert reservations[0].reserved_qty == 2

    issued = asyncio.run(service.apply_admin_order_action(care_order_id=order.care_order_id, action="issue"))
    consumed = asyncio.run(service.repository.list_reservations_for_order(care_order_id=order.care_order_id))
    assert issued and issued.status == "issued"
    assert all(row.status == "consumed" for row in consumed)

    order2 = asyncio.run(service.create_order(clinic_id="c1", patient_id="p1", payment_mode="pay_at_pickup", currency_code="RUB", pickup_branch_id="b1", recommendation_id="r1", booking_id=None, items=[(product, 1)]))
    asyncio.run(service.transition_order(care_order_id=order2.care_order_id, to_status="confirmed"))
    asyncio.run(service.apply_admin_order_action(care_order_id=order2.care_order_id, action="ready"))
    canceled = asyncio.run(service.apply_admin_order_action(care_order_id=order2.care_order_id, action="cancel"))
    released = asyncio.run(service.repository.list_reservations_for_order(care_order_id=order2.care_order_id))
    assert canceled and canceled.status == "canceled"
    assert all(row.status == "released" for row in released)


def test_ready_action_requires_pickup_branch_for_reservation_creation() -> None:
    repo = InMemoryCareRepo()
    service = CareCommerceService(repo)
    product = asyncio.run(service.create_or_update_product(clinic_id="c1", sku="SKU-1", title_key="care.product.aftercare_brush.title", description_key=None, category="hygiene", price_amount=1000, currency_code="RUB", status="active"))
    order = asyncio.run(service.create_order(clinic_id="c1", patient_id="p1", payment_mode="pay_at_pickup", currency_code="RUB", pickup_branch_id=None, recommendation_id="r1", booking_id=None, items=[(product, 1)]))
    asyncio.run(service.transition_order(care_order_id=order.care_order_id, to_status="confirmed"))

    with pytest.raises(ValueError):
        asyncio.run(service.apply_admin_order_action(care_order_id=order.care_order_id, action="ready"))


@dataclass
class _BookingRepo:
    booking: Booking

    async def load_booking(self, booking_id: str):
        return self.booking if booking_id == self.booking.booking_id else None

    async def list_by_patient(self, *, patient_id: str):
        return [self.booking] if self.booking.patient_id == patient_id else []

    async def list_by_doctor_time_window(self, *, doctor_id: str, start_at, end_at):
        return []


class _BookState:
    async def transition_booking(self, **kwargs):
        raise AssertionError("unused")


class _Orch:
    async def complete_booking(self, *, booking_id: str, reason_code: str | None = None):
        raise AssertionError("unused")


class _Reference:
    def __init__(self, locale: str):
        self._locale = locale

    def get_clinic(self, _clinic_id: str):
        class _Clinic:
            def __init__(self, locale: str):
                self.default_locale = locale

        return _Clinic(self._locale)


def test_aftercare_trigger_uses_localized_template_not_hardcoded_english() -> None:
    now = datetime.now(timezone.utc)
    booking = Booking(
        booking_id="b1",
        clinic_id="c1",
        branch_id="br1",
        patient_id="p1",
        service_id="s1",
        doctor_id="d1",
        slot_id="sl1",
        booking_mode="manual",
        source_channel="doctor",
        status="completed",
        scheduled_start_at=now,
        scheduled_end_at=now,
        confirmation_required=True,
        completed_at=now,
        canceled_at=None,
        no_show_at=None,
        checked_in_at=now,
        in_service_at=now,
        reason_for_visit_short=None,
        patient_note=None,
        confirmed_at=now,
        created_at=now,
        updated_at=now,
    )
    rec_repo = InMemoryRecommendationRepository()
    ops = DoctorOperationsService(
        access_resolver=None,
        booking_service=_BookingRepo(booking),
        booking_state_service=_BookState(),
        booking_orchestration=_Orch(),
        reference_service=_Reference("ru"),
        patient_reader=None,
        recommendation_service=RecommendationService(rec_repo),
        i18n=I18nService(locales_path=Path("locales")),
    )
    asyncio.run(ops._create_completion_aftercare(booking=booking))
    created = next(iter(rec_repo.rows.values()))
    assert "Рекомендации" in created.title
    assert "Please follow" not in created.body_text


def test_aftercare_trigger_localization_resolves_for_en_and_ru() -> None:
    now = datetime.now(timezone.utc)
    booking = Booking(
        booking_id="b1",
        clinic_id="c1",
        branch_id="br1",
        patient_id="p1",
        service_id="s1",
        doctor_id="d1",
        slot_id="sl1",
        booking_mode="manual",
        source_channel="doctor",
        status="completed",
        scheduled_start_at=now,
        scheduled_end_at=now,
        confirmation_required=True,
        completed_at=now,
        canceled_at=None,
        no_show_at=None,
        checked_in_at=now,
        in_service_at=now,
        reason_for_visit_short=None,
        patient_note=None,
        confirmed_at=now,
        created_at=now,
        updated_at=now,
    )

    ru_repo = InMemoryRecommendationRepository()
    ru_ops = DoctorOperationsService(
        access_resolver=None,
        booking_service=_BookingRepo(booking),
        booking_state_service=_BookState(),
        booking_orchestration=_Orch(),
        reference_service=_Reference("ru"),
        patient_reader=None,
        recommendation_service=RecommendationService(ru_repo),
        i18n=I18nService(locales_path=Path("locales")),
    )
    asyncio.run(ru_ops._create_completion_aftercare(booking=booking))

    en_repo = InMemoryRecommendationRepository()
    en_ops = DoctorOperationsService(
        access_resolver=None,
        booking_service=_BookingRepo(booking),
        booking_state_service=_BookState(),
        booking_orchestration=_Orch(),
        reference_service=_Reference("en"),
        patient_reader=None,
        recommendation_service=RecommendationService(en_repo),
        i18n=I18nService(locales_path=Path("locales")),
    )
    asyncio.run(en_ops._create_completion_aftercare(booking=booking))

    ru_created = next(iter(ru_repo.rows.values()))
    en_created = next(iter(en_repo.rows.values()))
    assert ru_created.title != en_created.title
    assert "Рекомендации" in ru_created.title
    assert "Aftercare" in en_created.title
