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
from app.domain.care_commerce import BranchProductAvailability, CareOrder, CareOrderItem, CareProduct, CareReservation, RecommendationProductLink
from app.domain.recommendations import Recommendation


class InMemoryCareRepo:
    def __init__(self) -> None:
        self.products: dict[str, CareProduct] = {}
        self.product_i18n: dict[tuple[str, str], dict[str, str | None]] = {}
        self.catalog_settings: dict[str, str] = {}
        self.links: dict[str, list[RecommendationProductLink]] = {}
        self.orders: dict[str, CareOrder] = {}
        self.order_items: dict[str, list[CareOrderItem]] = {}
        self.reservations: dict[str, list[CareReservation]] = {}
        self.availability: dict[tuple[str, str], BranchProductAvailability] = {}

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

    async def list_catalog_products_by_recommendation_type(self, *, clinic_id: str, recommendation_type: str) -> list[tuple[RecommendationProductLink, CareProduct]]:
        return []

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

    async def get_branch_product_availability(self, *, branch_id: str, care_product_id: str) -> BranchProductAvailability | None:
        return self.availability.get((branch_id, care_product_id))

    async def upsert_branch_product_availability(self, availability: BranchProductAvailability) -> BranchProductAvailability:
        self.availability[(availability.branch_id, availability.care_product_id)] = availability
        return availability

    async def get_product_i18n_content(self, *, care_product_id: str, locale: str) -> dict[str, str | None] | None:
        return self.product_i18n.get((care_product_id, locale))

    async def get_catalog_setting(self, *, clinic_id: str, key: str) -> str | None:
        return self.catalog_settings.get(f"{clinic_id}:{key}")


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


def test_branch_product_availability_create_update_and_free_qty() -> None:
    repo = InMemoryCareRepo()
    service = CareCommerceService(repo)
    product = asyncio.run(service.create_or_update_product(clinic_id="c1", sku="SKU-1", title_key="care.product.aftercare_brush.title", description_key=None, category="hygiene", price_amount=1000, currency_code="RUB", status="active"))

    initial = asyncio.run(service.set_branch_product_availability(clinic_id="c1", branch_id="b1", care_product_id=product.care_product_id, available_qty=5, reserved_qty=1))
    assert initial.free_qty == 4

    updated = asyncio.run(service.set_branch_product_availability(clinic_id="c1", branch_id="b1", care_product_id=product.care_product_id, available_qty=8, reserved_qty=3))
    free_qty = asyncio.run(service.compute_free_qty(branch_id="b1", care_product_id=product.care_product_id))
    assert updated.free_qty == 5
    assert free_qty == 5


def test_reservation_fails_when_insufficient_stock_and_succeeds_when_enough() -> None:
    repo = InMemoryCareRepo()
    service = CareCommerceService(repo)
    product = asyncio.run(service.create_or_update_product(clinic_id="c1", sku="SKU-1", title_key="care.product.aftercare_brush.title", description_key=None, category="hygiene", price_amount=1000, currency_code="RUB", status="active"))
    asyncio.run(service.set_branch_product_availability(clinic_id="c1", branch_id="b1", care_product_id=product.care_product_id, available_qty=2, reserved_qty=0))

    fail = asyncio.run(service.reserve_if_available(care_order_id="co_fail", care_product_id=product.care_product_id, branch_id="b1", reserved_qty=3))
    assert not fail.ok
    assert fail.reason == "insufficient_stock"

    ok = asyncio.run(service.reserve_if_available(care_order_id="co_ok", care_product_id=product.care_product_id, branch_id="b1", reserved_qty=2))
    assert ok.ok and ok.reservation is not None
    assert ok.availability is not None and ok.availability.reserved_qty == 2


def test_reservation_stock_changes_on_release_and_consume() -> None:
    repo = InMemoryCareRepo()
    service = CareCommerceService(repo)
    product = asyncio.run(service.create_or_update_product(clinic_id="c1", sku="SKU-1", title_key="care.product.aftercare_brush.title", description_key=None, category="hygiene", price_amount=1000, currency_code="RUB", status="active"))
    asyncio.run(service.set_branch_product_availability(clinic_id="c1", branch_id="b1", care_product_id=product.care_product_id, available_qty=4, reserved_qty=0))

    reservation = asyncio.run(service.create_reservation(care_order_id="co_1", care_product_id=product.care_product_id, branch_id="b1", reserved_qty=2))
    after_reserve = asyncio.run(service.get_branch_product_availability(branch_id="b1", care_product_id=product.care_product_id))
    assert after_reserve and after_reserve.reserved_qty == 2 and after_reserve.available_qty == 4

    asyncio.run(service.release_reservation(care_reservation_id=reservation.care_reservation_id, care_order_id="co_1"))
    after_release = asyncio.run(service.get_branch_product_availability(branch_id="b1", care_product_id=product.care_product_id))
    assert after_release and after_release.reserved_qty == 0 and after_release.available_qty == 4

    reservation2 = asyncio.run(service.create_reservation(care_order_id="co_2", care_product_id=product.care_product_id, branch_id="b1", reserved_qty=1))
    asyncio.run(service.consume_reservation(care_reservation_id=reservation2.care_reservation_id, care_order_id="co_2"))
    after_consume = asyncio.run(service.get_branch_product_availability(branch_id="b1", care_product_id=product.care_product_id))
    assert after_consume and after_consume.reserved_qty == 0 and after_consume.available_qty == 3


def test_ready_issue_cancel_admin_flow_is_branch_aware_and_stock_backed() -> None:
    repo = InMemoryCareRepo()
    service = CareCommerceService(repo)
    product = asyncio.run(service.create_or_update_product(clinic_id="c1", sku="SKU-1", title_key="care.product.aftercare_brush.title", description_key=None, category="hygiene", price_amount=1000, currency_code="RUB", status="active"))
    asyncio.run(service.set_branch_product_availability(clinic_id="c1", branch_id="b1", care_product_id=product.care_product_id, available_qty=2, reserved_qty=0))

    order = asyncio.run(service.create_order(clinic_id="c1", patient_id="p1", payment_mode="pay_at_pickup", currency_code="RUB", pickup_branch_id="b1", recommendation_id="r1", booking_id=None, items=[(product, 2)]))
    asyncio.run(service.transition_order(care_order_id=order.care_order_id, to_status="confirmed"))

    ready = asyncio.run(service.apply_admin_order_action(care_order_id=order.care_order_id, action="ready"))
    reservations = asyncio.run(service.repository.list_reservations_for_order(care_order_id=order.care_order_id))
    assert ready and ready.status == "ready_for_pickup"
    assert reservations and reservations[0].branch_id == "b1"

    issued = asyncio.run(service.apply_admin_order_action(care_order_id=order.care_order_id, action="issue"))
    consumed = asyncio.run(service.repository.list_reservations_for_order(care_order_id=order.care_order_id))
    availability = asyncio.run(service.get_branch_product_availability(branch_id="b1", care_product_id=product.care_product_id))
    assert issued and issued.status == "issued"
    assert all(row.status == "consumed" for row in consumed)
    assert availability and availability.available_qty == 0 and availability.reserved_qty == 0


def test_ready_action_fails_when_stock_is_insufficient() -> None:
    repo = InMemoryCareRepo()
    service = CareCommerceService(repo)
    product = asyncio.run(service.create_or_update_product(clinic_id="c1", sku="SKU-1", title_key="care.product.aftercare_brush.title", description_key=None, category="hygiene", price_amount=1000, currency_code="RUB", status="active"))
    asyncio.run(service.set_branch_product_availability(clinic_id="c1", branch_id="b1", care_product_id=product.care_product_id, available_qty=0, reserved_qty=0))
    order = asyncio.run(service.create_order(clinic_id="c1", patient_id="p1", payment_mode="pay_at_pickup", currency_code="RUB", pickup_branch_id="b1", recommendation_id="r1", booking_id=None, items=[(product, 1)]))
    asyncio.run(service.transition_order(care_order_id=order.care_order_id, to_status="confirmed"))

    with pytest.raises(ValueError, match="insufficient_stock"):
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


def test_product_content_resolution_prefers_synced_i18n_and_fallback_locale() -> None:
    repo = InMemoryCareRepo()
    service = CareCommerceService(repo)
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
    repo.product_i18n[(product.care_product_id, "en")] = {
        "title": "Synced Brush",
        "description": "Synced description",
        "short_label": "Brush",
        "justification_text": None,
        "usage_hint": None,
    }
    repo.catalog_settings["c1:care.default_locale"] = "en"

    exact = asyncio.run(service.resolve_product_content(clinic_id="c1", product=product, locale="en"))
    assert exact.title == "Synced Brush"
    assert exact.locale == "en"

    fallback = asyncio.run(service.resolve_product_content(clinic_id="c1", product=product, locale="ru"))
    assert fallback.title == "Synced Brush"
    assert fallback.locale == "en"
