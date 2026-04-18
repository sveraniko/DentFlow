from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar, Protocol
from uuid import uuid4

from app.domain.care_commerce import (
    BranchProductAvailability,
    CareOrder,
    CareOrderItem,
    CareProduct,
    CareReservation,
    RecommendationProductLink,
)

_ORDER_TRANSITIONS: dict[str, set[str]] = {
    "created": {"awaiting_confirmation", "confirmed", "awaiting_payment", "canceled", "expired"},
    "awaiting_confirmation": {"confirmed", "canceled", "expired"},
    "confirmed": {"awaiting_payment", "paid", "ready_for_pickup", "canceled", "expired"},
    "awaiting_payment": {"paid", "canceled", "expired"},
    "paid": {"ready_for_pickup", "issued", "fulfilled", "canceled", "expired"},
    "ready_for_pickup": {"issued", "fulfilled", "canceled", "expired"},
    "issued": {"fulfilled"},
    "fulfilled": set(),
    "canceled": set(),
    "expired": set(),
}


class CareCommerceRepository(Protocol):
    async def upsert_product(self, product: CareProduct) -> CareProduct: ...
    async def get_product(self, care_product_id: str) -> CareProduct | None: ...
    async def list_active_products_by_clinic(self, *, clinic_id: str) -> list[CareProduct]: ...
    async def link_product_to_recommendation(self, link: RecommendationProductLink) -> RecommendationProductLink: ...
    async def list_products_by_recommendation(self, *, recommendation_id: str) -> list[tuple[RecommendationProductLink, CareProduct]]: ...
    async def list_catalog_products_by_recommendation_type(self, *, clinic_id: str, recommendation_type: str) -> list[tuple[RecommendationProductLink, CareProduct]]: ...
    async def create_order(self, order: CareOrder, items: list[CareOrderItem]) -> CareOrder: ...
    async def get_order(self, care_order_id: str) -> CareOrder | None: ...
    async def list_order_items(self, care_order_id: str) -> list[CareOrderItem]: ...
    async def save_order(self, order: CareOrder) -> CareOrder: ...
    async def list_orders_for_patient(self, *, patient_id: str, clinic_id: str) -> list[CareOrder]: ...
    async def list_orders_for_admin(self, *, clinic_id: str, statuses: tuple[str, ...], limit: int = 30) -> list[CareOrder]: ...
    async def create_reservation(self, reservation: CareReservation) -> CareReservation: ...
    async def save_reservation(self, reservation: CareReservation) -> CareReservation: ...
    async def list_reservations_for_order(self, *, care_order_id: str) -> list[CareReservation]: ...
    async def get_branch_product_availability(self, *, branch_id: str, care_product_id: str) -> BranchProductAvailability | None: ...
    async def upsert_branch_product_availability(self, availability: BranchProductAvailability) -> BranchProductAvailability: ...
    async def get_product_i18n_content(self, *, care_product_id: str, locale: str) -> dict[str, str | None] | None: ...
    async def get_catalog_setting(self, *, clinic_id: str, key: str) -> str | None: ...
    async def get_product_by_code(self, *, clinic_id: str, target_code: str) -> CareProduct | None: ...
    async def list_recommendation_links_by_type(self, *, clinic_id: str, recommendation_type: str) -> list[dict[str, object]]: ...
    async def get_recommendation_set(self, *, clinic_id: str, set_code: str) -> dict[str, object] | None: ...
    async def list_recommendation_set_items(self, *, clinic_id: str, set_code: str) -> list[dict[str, object]]: ...
    async def upsert_manual_recommendation_target(
        self,
        *,
        recommendation_id: str,
        target_kind: str,
        target_code: str,
        justification_text: str | None,
    ) -> None: ...
    async def get_manual_recommendation_target(self, *, recommendation_id: str) -> dict[str, object] | None: ...


@dataclass(frozen=True)
class ReservationOutcome:
    ok: bool
    reason: str | None
    reservation: CareReservation | None
    availability: BranchProductAvailability | None


@dataclass(frozen=True)
class CareProductContent:
    locale: str | None
    title: str | None
    description: str | None
    short_label: str | None
    justification_text: str | None
    usage_hint: str | None


@dataclass(frozen=True)
class ResolvedRecommendationProduct:
    recommendation_id: str
    care_product_id: str
    product: CareProduct
    relevance_rank: int
    quantity: int
    explanation_text: str | None
    source_kind: str


@dataclass(frozen=True)
class RecommendationTargetResolution:
    status: str
    products: list[ResolvedRecommendationProduct]
    manual_target_present: bool
    manual_target_invalid: bool
    manual_target_kind: str | None = None
    manual_target_code: str | None = None


@dataclass(slots=True)
class CareCommerceService:
    repository: CareCommerceRepository

    _ADMIN_ACTION_TARGETS: ClassVar[dict[str, str]] = {
        "ready": "ready_for_pickup",
        "issue": "issued",
        "fulfill": "fulfilled",
        "cancel": "canceled",
        "pay_required": "awaiting_payment",
        "paid": "paid",
    }

    async def create_or_update_product(self, **kwargs) -> CareProduct:
        now = datetime.now(timezone.utc)
        existing = await self.repository.get_product(kwargs["care_product_id"]) if kwargs.get("care_product_id") else None
        payload = {
            "care_product_id": kwargs.get("care_product_id") or f"cp_{uuid4().hex[:16]}",
            "clinic_id": kwargs["clinic_id"],
            "sku": kwargs["sku"],
            "title_key": kwargs["title_key"],
            "description_key": kwargs.get("description_key"),
            "category": kwargs["category"],
            "use_case_tag": kwargs.get("use_case_tag"),
            "price_amount": kwargs["price_amount"],
            "currency_code": kwargs["currency_code"],
            "status": kwargs.get("status", "active"),
            "pickup_supported": kwargs.get("pickup_supported", True),
            "delivery_supported": kwargs.get("delivery_supported", False),
            "sort_order": kwargs.get("sort_order"),
            "available_qty": kwargs.get("available_qty"),
            "created_at": existing.created_at if existing else now,
            "updated_at": now,
        }
        return await self.repository.upsert_product(CareProduct(**payload))

    async def list_active_products_by_clinic(self, *, clinic_id: str) -> list[CareProduct]:
        return await self.repository.list_active_products_by_clinic(clinic_id=clinic_id)

    async def list_catalog_categories(self, *, clinic_id: str) -> list[str]:
        rows = await self.repository.list_active_products_by_clinic(clinic_id=clinic_id)
        categories = sorted({str(row.category).strip() for row in rows if str(row.category).strip()})
        return categories

    async def list_catalog_products_by_category(self, *, clinic_id: str, category: str) -> list[CareProduct]:
        rows = await self.repository.list_active_products_by_clinic(clinic_id=clinic_id)
        return [row for row in rows if row.category == category]

    async def link_product_to_recommendation(
        self,
        *,
        recommendation_id: str,
        care_product_id: str,
        relevance_rank: int,
        justification_key: str | None = None,
        justification_text_key: str | None = None,
    ) -> RecommendationProductLink:
        link = RecommendationProductLink(
            recommendation_product_link_id=f"rpl_{uuid4().hex[:16]}",
            recommendation_id=recommendation_id,
            care_product_id=care_product_id,
            relevance_rank=relevance_rank,
            justification_key=justification_key,
            justification_text_key=justification_text_key,
            created_at=datetime.now(timezone.utc),
        )
        return await self.repository.link_product_to_recommendation(link)

    async def list_products_by_recommendation(self, *, recommendation_id: str) -> list[tuple[RecommendationProductLink, CareProduct]]:
        return await self.repository.list_products_by_recommendation(recommendation_id=recommendation_id)

    async def list_products_for_recommendation_context(
        self,
        *,
        clinic_id: str,
        recommendation_id: str,
        recommendation_type: str,
    ) -> list[tuple[RecommendationProductLink, CareProduct]]:
        resolved = await self.resolve_recommendation_targets(
            clinic_id=clinic_id,
            recommendation_id=recommendation_id,
            recommendation_type=recommendation_type,
        )
        rows: list[tuple[RecommendationProductLink, CareProduct]] = []
        for item in resolved:
            rows.append(
                (
                    RecommendationProductLink(
                        recommendation_product_link_id=f"resolved_{recommendation_id}_{item.care_product_id}_{item.relevance_rank}",
                        recommendation_id=recommendation_id,
                        care_product_id=item.care_product_id,
                        relevance_rank=item.relevance_rank,
                        justification_key=item.source_kind,
                        justification_text_key=item.explanation_text,
                        created_at=item.product.updated_at,
                    ),
                    item.product,
                )
            )
        return rows

    async def set_manual_recommendation_target(
        self,
        *,
        recommendation_id: str,
        target_kind: str,
        target_code: str,
        justification_text: str | None = None,
    ) -> None:
        if target_kind not in {"product", "set"}:
            raise ValueError("unsupported_target_kind")
        await self.repository.upsert_manual_recommendation_target(
            recommendation_id=recommendation_id,
            target_kind=target_kind,
            target_code=target_code,
            justification_text=justification_text,
        )

    async def resolve_recommendation_targets(
        self,
        *,
        clinic_id: str,
        recommendation_id: str,
        recommendation_type: str,
        locale: str = "en",
    ) -> list[ResolvedRecommendationProduct]:
        resolution = await self.resolve_recommendation_target_result(
            clinic_id=clinic_id,
            recommendation_id=recommendation_id,
            recommendation_type=recommendation_type,
            locale=locale,
        )
        return resolution.products

    async def resolve_recommendation_target_result(
        self,
        *,
        clinic_id: str,
        recommendation_id: str,
        recommendation_type: str,
        locale: str = "en",
    ) -> RecommendationTargetResolution:
        manual = await self.repository.get_manual_recommendation_target(recommendation_id=recommendation_id)
        if manual:
            manual_target_kind = str(manual.get("target_kind", ""))
            manual_target_code = str(manual.get("target_code", ""))
            resolved = await self._resolve_target(
                clinic_id=clinic_id,
                recommendation_id=recommendation_id,
                target_kind=manual_target_kind,
                target_code=manual_target_code,
                relevance_rank=0,
                source_kind="manual_explicit_target",
                locale=locale,
                link_justification=self._clean_text(manual.get("justification_text")),
            )
            if resolved:
                return RecommendationTargetResolution(
                    status="manual_target_resolved",
                    products=resolved,
                    manual_target_present=True,
                    manual_target_invalid=False,
                    manual_target_kind=manual_target_kind,
                    manual_target_code=manual_target_code,
                )
            return RecommendationTargetResolution(
                status="manual_target_invalid",
                products=[],
                manual_target_present=True,
                manual_target_invalid=True,
                manual_target_kind=manual_target_kind,
                manual_target_code=manual_target_code,
            )

        direct = await self.repository.list_products_by_recommendation(recommendation_id=recommendation_id)
        direct_rows = [
            ResolvedRecommendationProduct(
                recommendation_id=recommendation_id,
                care_product_id=product.care_product_id,
                product=product,
                relevance_rank=link.relevance_rank,
                quantity=1,
                explanation_text=self._clean_text(link.justification_text_key),
                source_kind="manual_product_links",
            )
            for link, product in direct
            if product.status == "active"
        ]
        if direct_rows:
            return RecommendationTargetResolution(
                status="direct_links_resolved",
                products=sorted(direct_rows, key=lambda row: row.relevance_rank),
                manual_target_present=False,
                manual_target_invalid=False,
            )

        links = await self.repository.list_recommendation_links_by_type(
            clinic_id=clinic_id,
            recommendation_type=recommendation_type,
        )
        resolved: list[ResolvedRecommendationProduct] = []
        for row in links:
            if not bool(row.get("active", True)):
                continue
            resolved.extend(
                await self._resolve_target(
                    clinic_id=clinic_id,
                    recommendation_id=recommendation_id,
                    target_kind=str(row.get("target_kind", "")),
                    target_code=str(row.get("target_code", "")),
                    relevance_rank=int(row.get("relevance_rank", 100)),
                    source_kind="rule_recommendation_link",
                    locale=locale,
                    link_justification=self._pick_justification_text(row=row, locale=locale),
                )
            )
        return RecommendationTargetResolution(
            status="rule_links_resolved",
            products=self._dedupe_preserving_priority(sorted(resolved, key=lambda row: row.relevance_rank)),
            manual_target_present=False,
            manual_target_invalid=False,
        )

    async def _resolve_target(
        self,
        *,
        clinic_id: str,
        recommendation_id: str,
        target_kind: str,
        target_code: str,
        relevance_rank: int,
        source_kind: str,
        locale: str,
        link_justification: str | None,
    ) -> list[ResolvedRecommendationProduct]:
        if target_kind == "product":
            product = await self.repository.get_product_by_code(clinic_id=clinic_id, target_code=target_code)
            if product is None or product.status != "active":
                return []
            return [
                ResolvedRecommendationProduct(
                    recommendation_id=recommendation_id,
                    care_product_id=product.care_product_id,
                    product=product,
                    relevance_rank=relevance_rank,
                    quantity=1,
                    explanation_text=link_justification,
                    source_kind=source_kind,
                )
            ]
        if target_kind != "set":
            return []
        rec_set = await self.repository.get_recommendation_set(clinic_id=clinic_id, set_code=target_code)
        if not rec_set or rec_set.get("status") != "active":
            return []
        set_description = self._set_description(rec_set=rec_set, locale=locale)
        items = await self.repository.list_recommendation_set_items(clinic_id=clinic_id, set_code=target_code)
        resolved: list[ResolvedRecommendationProduct] = []
        for item in items:
            product = item.get("product")
            if not isinstance(product, CareProduct) or product.status != "active":
                continue
            rank = relevance_rank + int(item.get("position", 0))
            explanation = link_justification or set_description
            resolved.append(
                ResolvedRecommendationProduct(
                    recommendation_id=recommendation_id,
                    care_product_id=product.care_product_id,
                    product=product,
                    relevance_rank=rank,
                    quantity=max(1, int(item.get("quantity", 1))),
                    explanation_text=explanation,
                    source_kind=source_kind,
                )
            )
        return resolved

    def _pick_justification_text(self, *, row: dict[str, object], locale: str) -> str | None:
        lang = locale.lower()
        if lang.startswith("ru"):
            return self._clean_text(row.get("justification_text_ru")) or self._clean_text(row.get("justification_text_en"))
        return self._clean_text(row.get("justification_text_en")) or self._clean_text(row.get("justification_text_ru"))

    def _set_description(self, *, rec_set: dict[str, object], locale: str) -> str | None:
        lang = locale.lower()
        if lang.startswith("ru"):
            return self._clean_text(rec_set.get("description_ru")) or self._clean_text(rec_set.get("description_en"))
        return self._clean_text(rec_set.get("description_en")) or self._clean_text(rec_set.get("description_ru"))

    def _dedupe_preserving_priority(self, rows: list[ResolvedRecommendationProduct]) -> list[ResolvedRecommendationProduct]:
        seen: set[str] = set()
        out: list[ResolvedRecommendationProduct] = []
        for row in rows:
            if row.care_product_id in seen:
                continue
            seen.add(row.care_product_id)
            out.append(row)
        return out

    def _clean_text(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    async def resolve_product_content(
        self,
        *,
        clinic_id: str,
        product: CareProduct,
        locale: str,
        fallback_locale: str | None = None,
    ) -> CareProductContent:
        fetcher = getattr(self.repository, "get_product_i18n_content", None)
        if not callable(fetcher):
            return CareProductContent(locale=None, title=None, description=None, short_label=None, justification_text=None, usage_hint=None)
        exact = await fetcher(care_product_id=product.care_product_id, locale=locale)
        if exact:
            return CareProductContent(
                locale=locale,
                title=_content_str(exact, "title"),
                description=_content_str(exact, "description"),
                short_label=_content_str(exact, "short_label"),
                justification_text=_content_str(exact, "justification_text"),
                usage_hint=_content_str(exact, "usage_hint"),
            )
        fallback = await self._resolve_catalog_fallback_locale(clinic_id=clinic_id, preferred=fallback_locale)
        if fallback and fallback != locale:
            fallback_row = await fetcher(care_product_id=product.care_product_id, locale=fallback)
            if fallback_row:
                return CareProductContent(
                    locale=fallback,
                    title=_content_str(fallback_row, "title"),
                    description=_content_str(fallback_row, "description"),
                    short_label=_content_str(fallback_row, "short_label"),
                    justification_text=_content_str(fallback_row, "justification_text"),
                    usage_hint=_content_str(fallback_row, "usage_hint"),
                )
        return CareProductContent(locale=None, title=None, description=None, short_label=None, justification_text=None, usage_hint=None)

    async def _resolve_catalog_fallback_locale(self, *, clinic_id: str, preferred: str | None) -> str | None:
        if preferred:
            return preferred
        getter = getattr(self.repository, "get_catalog_setting", None)
        if not callable(getter):
            return None
        for key in ("care.catalog_fallback_locale", "care.default_locale"):
            value = await getter(clinic_id=clinic_id, key=key)
            if value:
                return value.strip().lower()
        return None

    async def create_order(
        self,
        *,
        clinic_id: str,
        patient_id: str,
        payment_mode: str,
        currency_code: str,
        pickup_branch_id: str | None,
        recommendation_id: str | None,
        booking_id: str | None,
        items: list[tuple[CareProduct, int]],
    ) -> CareOrder:
        now = datetime.now(timezone.utc)
        order_id = f"co_{uuid4().hex[:16]}"
        order_items: list[CareOrderItem] = []
        total = 0
        for product, qty in items:
            line_total = product.price_amount * qty
            total += line_total
            order_items.append(
                CareOrderItem(
                    care_order_item_id=f"coi_{uuid4().hex[:16]}",
                    care_order_id=order_id,
                    care_product_id=product.care_product_id,
                    quantity=qty,
                    unit_price=product.price_amount,
                    line_total=line_total,
                    created_at=now,
                )
            )
        order = CareOrder(
            care_order_id=order_id,
            clinic_id=clinic_id,
            patient_id=patient_id,
            booking_id=booking_id,
            recommendation_id=recommendation_id,
            status="created",
            payment_mode=payment_mode,
            pickup_branch_id=pickup_branch_id,
            total_amount=total,
            currency_code=currency_code,
            created_at=now,
            updated_at=now,
            confirmed_at=None,
            paid_at=None,
            ready_for_pickup_at=None,
            issued_at=None,
            fulfilled_at=None,
            canceled_at=None,
            expired_at=None,
        )
        return await self.repository.create_order(order, order_items)

    async def transition_order(self, *, care_order_id: str, to_status: str) -> CareOrder | None:
        order = await self.repository.get_order(care_order_id)
        if order is None:
            return None
        allowed = _ORDER_TRANSITIONS.get(order.status, set())
        if to_status not in allowed and to_status != order.status:
            raise ValueError(f"invalid care order transition: {order.status} -> {to_status}")
        now = datetime.now(timezone.utc)
        payload = {**order.__dict__, "status": to_status, "updated_at": now}
        if to_status == "confirmed" and order.confirmed_at is None:
            payload["confirmed_at"] = now
        if to_status == "paid" and order.paid_at is None:
            payload["paid_at"] = now
        if to_status == "ready_for_pickup" and order.ready_for_pickup_at is None:
            payload["ready_for_pickup_at"] = now
        if to_status == "issued" and order.issued_at is None:
            payload["issued_at"] = now
        if to_status == "fulfilled" and order.fulfilled_at is None:
            payload["fulfilled_at"] = now
        if to_status == "canceled" and order.canceled_at is None:
            payload["canceled_at"] = now
        if to_status == "expired" and order.expired_at is None:
            payload["expired_at"] = now
        return await self.repository.save_order(CareOrder(**payload))

    async def get_order(self, care_order_id: str) -> CareOrder | None:
        return await self.repository.get_order(care_order_id)

    async def list_patient_orders(self, *, clinic_id: str, patient_id: str) -> list[CareOrder]:
        return await self.repository.list_orders_for_patient(clinic_id=clinic_id, patient_id=patient_id)

    async def list_admin_orders(self, *, clinic_id: str, statuses: tuple[str, ...], limit: int = 30) -> list[CareOrder]:
        return await self.repository.list_orders_for_admin(clinic_id=clinic_id, statuses=statuses, limit=limit)

    async def set_branch_product_availability(
        self,
        *,
        clinic_id: str,
        branch_id: str,
        care_product_id: str,
        available_qty: int,
        reserved_qty: int = 0,
        status: str = "active",
    ) -> BranchProductAvailability:
        existing = await self.repository.get_branch_product_availability(branch_id=branch_id, care_product_id=care_product_id)
        now = datetime.now(timezone.utc)
        availability = BranchProductAvailability(
            branch_product_availability_id=(existing.branch_product_availability_id if existing else f"bpa_{uuid4().hex[:16]}"),
            clinic_id=clinic_id,
            branch_id=branch_id,
            care_product_id=care_product_id,
            available_qty=max(0, available_qty),
            reserved_qty=max(0, reserved_qty),
            status=status,
            created_at=(existing.created_at if existing else now),
            updated_at=now,
        )
        return await self.repository.upsert_branch_product_availability(availability)

    async def get_branch_product_availability(self, *, branch_id: str, care_product_id: str) -> BranchProductAvailability | None:
        return await self.repository.get_branch_product_availability(branch_id=branch_id, care_product_id=care_product_id)

    async def compute_free_qty(self, *, branch_id: str, care_product_id: str) -> int:
        row = await self.repository.get_branch_product_availability(branch_id=branch_id, care_product_id=care_product_id)
        if row is None or row.status != "active":
            return 0
        return row.free_qty

    async def create_reservation(
        self,
        *,
        care_order_id: str,
        care_product_id: str,
        branch_id: str,
        reserved_qty: int,
        expires_at: datetime | None = None,
    ) -> CareReservation:
        outcome = await self.reserve_if_available(
            care_order_id=care_order_id,
            care_product_id=care_product_id,
            branch_id=branch_id,
            reserved_qty=reserved_qty,
            expires_at=expires_at,
        )
        if not outcome.ok or outcome.reservation is None:
            raise ValueError(outcome.reason or "reservation_failed")
        return outcome.reservation

    async def reserve_if_available(
        self,
        *,
        care_order_id: str,
        care_product_id: str,
        branch_id: str,
        reserved_qty: int,
        expires_at: datetime | None = None,
    ) -> ReservationOutcome:
        row = await self.repository.get_branch_product_availability(branch_id=branch_id, care_product_id=care_product_id)
        if row is None:
            return ReservationOutcome(ok=False, reason="availability_missing", reservation=None, availability=None)
        if row.status != "active":
            return ReservationOutcome(ok=False, reason="availability_inactive", reservation=None, availability=row)
        if row.free_qty < reserved_qty:
            return ReservationOutcome(ok=False, reason="insufficient_stock", reservation=None, availability=row)

        now = datetime.now(timezone.utc)
        reservation = CareReservation(
            care_reservation_id=f"cres_{uuid4().hex[:16]}",
            care_order_id=care_order_id,
            care_product_id=care_product_id,
            branch_id=branch_id,
            status="created",
            reserved_qty=reserved_qty,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
            released_at=None,
            consumed_at=None,
        )
        updated = BranchProductAvailability(**{**row.__dict__, "reserved_qty": row.reserved_qty + reserved_qty, "updated_at": now})
        saved_reservation = await self.repository.create_reservation(reservation)
        saved_availability = await self.repository.upsert_branch_product_availability(updated)
        return ReservationOutcome(ok=True, reason=None, reservation=saved_reservation, availability=saved_availability)

    async def release_reservation(self, *, care_reservation_id: str, care_order_id: str) -> CareReservation | None:
        rows = await self.repository.list_reservations_for_order(care_order_id=care_order_id)
        current = next((row for row in rows if row.care_reservation_id == care_reservation_id), None)
        if current is None:
            return None
        now = datetime.now(timezone.utc)
        released = await self.repository.save_reservation(
            CareReservation(**{**current.__dict__, "status": "released", "updated_at": now, "released_at": now})
        )
        await self._adjust_reservation_stock(branch_id=current.branch_id, care_product_id=current.care_product_id, qty=current.reserved_qty, consume=False)
        return released

    async def consume_reservation(self, *, care_reservation_id: str, care_order_id: str) -> CareReservation | None:
        rows = await self.repository.list_reservations_for_order(care_order_id=care_order_id)
        current = next((row for row in rows if row.care_reservation_id == care_reservation_id), None)
        if current is None:
            return None
        now = datetime.now(timezone.utc)
        consumed = await self.repository.save_reservation(
            CareReservation(**{**current.__dict__, "status": "consumed", "updated_at": now, "consumed_at": now})
        )
        await self._adjust_reservation_stock(branch_id=current.branch_id, care_product_id=current.care_product_id, qty=current.reserved_qty, consume=True)
        return consumed

    async def apply_admin_order_action(self, *, care_order_id: str, action: str) -> CareOrder | None:
        target = self._ADMIN_ACTION_TARGETS.get(action)
        if target is None:
            raise ValueError(f"unsupported admin care action: {action}")
        order = await self.repository.get_order(care_order_id)
        if order is None:
            return None

        if action == "ready":
            if not order.pickup_branch_id:
                raise ValueError("pickup_branch_required")
            await self._assert_order_stock_available(order)
            updated = await self.transition_order(care_order_id=care_order_id, to_status=target)
            if updated is None:
                return None
            await self._ensure_reservations_for_order(updated)
            return updated

        if action == "issue":
            updated = await self.transition_order(care_order_id=care_order_id, to_status=target)
            if updated is None:
                return None
            await self._consume_active_reservations(care_order_id=care_order_id)
            return updated

        if action == "cancel":
            updated = await self.transition_order(care_order_id=care_order_id, to_status=target)
            if updated is None:
                return None
            await self._release_active_reservations(care_order_id=care_order_id)
            return updated

        return await self.transition_order(care_order_id=care_order_id, to_status=target)

    async def _ensure_reservations_for_order(self, order: CareOrder) -> None:
        items = await self.repository.list_order_items(order.care_order_id)
        existing = await self.repository.list_reservations_for_order(care_order_id=order.care_order_id)
        existing_by_product: dict[str, int] = {}
        for reservation in existing:
            if reservation.status in {"created", "consumed"}:
                existing_by_product[reservation.care_product_id] = existing_by_product.get(reservation.care_product_id, 0) + reservation.reserved_qty
        for item in items:
            missing_qty = item.quantity - existing_by_product.get(item.care_product_id, 0)
            if missing_qty > 0:
                outcome = await self.reserve_if_available(
                    care_order_id=order.care_order_id,
                    care_product_id=item.care_product_id,
                    branch_id=order.pickup_branch_id or "",
                    reserved_qty=missing_qty,
                )
                if not outcome.ok:
                    raise ValueError(outcome.reason or "reservation_failed")

    async def _assert_order_stock_available(self, order: CareOrder) -> None:
        items = await self.repository.list_order_items(order.care_order_id)
        existing = await self.repository.list_reservations_for_order(care_order_id=order.care_order_id)
        already_reserved: dict[str, int] = {}
        for row in existing:
            if row.status == "created":
                already_reserved[row.care_product_id] = already_reserved.get(row.care_product_id, 0) + row.reserved_qty
        for item in items:
            needed = max(0, item.quantity - already_reserved.get(item.care_product_id, 0))
            if needed == 0:
                continue
            free_qty = await self.compute_free_qty(branch_id=order.pickup_branch_id or "", care_product_id=item.care_product_id)
            if free_qty < needed:
                raise ValueError("insufficient_stock")

    async def _consume_active_reservations(self, *, care_order_id: str) -> None:
        rows = await self.repository.list_reservations_for_order(care_order_id=care_order_id)
        for row in rows:
            if row.status == "created":
                await self.consume_reservation(care_reservation_id=row.care_reservation_id, care_order_id=care_order_id)

    async def _release_active_reservations(self, *, care_order_id: str) -> None:
        rows = await self.repository.list_reservations_for_order(care_order_id=care_order_id)
        for row in rows:
            if row.status == "created":
                await self.release_reservation(care_reservation_id=row.care_reservation_id, care_order_id=care_order_id)

    async def _adjust_reservation_stock(self, *, branch_id: str, care_product_id: str, qty: int, consume: bool) -> None:
        row = await self.repository.get_branch_product_availability(branch_id=branch_id, care_product_id=care_product_id)
        if row is None:
            return
        now = datetime.now(timezone.utc)
        next_reserved = max(0, row.reserved_qty - qty)
        next_available = max(0, row.available_qty - qty) if consume else row.available_qty
        await self.repository.upsert_branch_product_availability(
            BranchProductAvailability(
                **{**row.__dict__, "reserved_qty": next_reserved, "available_qty": next_available, "updated_at": now}
            )
        )


def _content_str(row: dict[str, str | None], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
