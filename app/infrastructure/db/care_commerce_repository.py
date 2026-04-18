from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sqlalchemy import bindparam, text

from app.domain.care_commerce import BranchProductAvailability, CareOrder, CareOrderItem, CareProduct, CareReservation, RecommendationProductLink
from app.domain.events import build_event
from app.infrastructure.db.engine import create_engine
from app.infrastructure.outbox.repository import OutboxRepository

_ORDER_EVENT_BY_STATUS = {
    "created": "care_order.created",
    "confirmed": "care_order.confirmed",
    "awaiting_payment": "care_order.payment_required",
    "paid": "care_order.paid",
    "ready_for_pickup": "care_order.ready_for_pickup",
    "issued": "care_order.issued",
    "fulfilled": "care_order.fulfilled",
    "canceled": "care_order.canceled",
}

_RES_EVENT_BY_STATUS = {
    "created": "care_reservation.created",
    "released": "care_reservation.released",
    "expired": "care_reservation.expired",
    "consumed": "care_reservation.consumed",
}


_AVAILABILITY_EVENT_BY_STATUS = {
    "active": "care_availability.updated",
    "inactive": "care_availability.updated",
    "unavailable": "care_availability.updated",
}


class DbCareCommerceRepository:
    def __init__(self, db_config: Any) -> None:
        self._db_config = db_config

    async def upsert_product(self, product: CareProduct) -> CareProduct:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                previous = (await conn.execute(text("SELECT care_product_id FROM care_commerce.products WHERE care_product_id=:id"), {"id": product.care_product_id})).scalar_one_or_none()
                await conn.execute(
                    text(
                        """
                        INSERT INTO care_commerce.products (
                          care_product_id, clinic_id, sku, title_key, description_key, category, use_case_tag,
                          price_amount, currency_code, status, pickup_supported, delivery_supported,
                          sort_order, available_qty, created_at, updated_at
                        ) VALUES (
                          :care_product_id, :clinic_id, :sku, :title_key, :description_key, :category, :use_case_tag,
                          :price_amount, :currency_code, :status, :pickup_supported, :delivery_supported,
                          :sort_order, :available_qty, :created_at, :updated_at
                        )
                        ON CONFLICT (care_product_id) DO UPDATE SET
                          sku=EXCLUDED.sku,
                          title_key=EXCLUDED.title_key,
                          description_key=EXCLUDED.description_key,
                          category=EXCLUDED.category,
                          use_case_tag=EXCLUDED.use_case_tag,
                          price_amount=EXCLUDED.price_amount,
                          currency_code=EXCLUDED.currency_code,
                          status=EXCLUDED.status,
                          pickup_supported=EXCLUDED.pickup_supported,
                          delivery_supported=EXCLUDED.delivery_supported,
                          sort_order=EXCLUDED.sort_order,
                          available_qty=EXCLUDED.available_qty,
                          updated_at=EXCLUDED.updated_at
                        """
                    ),
                    asdict(product),
                )
                event_name = "care_product.updated" if previous else "care_product.created"
                await OutboxRepository(self._db_config).append_on_connection(
                    conn,
                    build_event(
                        event_name=event_name,
                        producer_context="care_commerce.catalog",
                        clinic_id=product.clinic_id,
                        entity_type="care_product",
                        entity_id=product.care_product_id,
                        occurred_at=product.updated_at,
                        payload={"sku": product.sku, "status": product.status, "category": product.category},
                    ),
                )
            return product
        finally:
            await engine.dispose()

    async def get_product(self, care_product_id: str) -> CareProduct | None:
        row = await _fetch_one(self._db_config, "SELECT * FROM care_commerce.products WHERE care_product_id=:id", {"id": care_product_id})
        return CareProduct(**row) if row else None

    async def list_active_products_by_clinic(self, *, clinic_id: str) -> list[CareProduct]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT * FROM care_commerce.products
            WHERE clinic_id=:clinic_id AND status='active'
            ORDER BY sort_order NULLS LAST, created_at DESC
            """,
            {"clinic_id": clinic_id},
        )
        return [CareProduct(**row) for row in rows]

    async def link_product_to_recommendation(self, link: RecommendationProductLink) -> RecommendationProductLink:
        await _execute(
            self._db_config,
            """
            INSERT INTO care_commerce.recommendation_product_links (
              recommendation_product_link_id, recommendation_id, care_product_id, relevance_rank,
              justification_key, justification_text_key, created_at
            ) VALUES (
              :recommendation_product_link_id, :recommendation_id, :care_product_id, :relevance_rank,
              :justification_key, :justification_text_key, :created_at
            )
            ON CONFLICT (recommendation_id, care_product_id) DO UPDATE SET
              relevance_rank=EXCLUDED.relevance_rank,
              justification_key=EXCLUDED.justification_key,
              justification_text_key=EXCLUDED.justification_text_key
            """,
            asdict(link),
        )
        return link

    async def list_products_by_recommendation(self, *, recommendation_id: str) -> list[tuple[RecommendationProductLink, CareProduct]]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT
              l.recommendation_product_link_id, l.recommendation_id, l.care_product_id, l.relevance_rank,
              l.justification_key, l.justification_text_key, l.created_at,
              p.clinic_id, p.sku, p.title_key, p.description_key, p.category, p.use_case_tag,
              p.price_amount, p.currency_code, p.status, p.pickup_supported, p.delivery_supported,
              p.sort_order, p.available_qty, p.created_at AS product_created_at, p.updated_at AS product_updated_at
            FROM care_commerce.recommendation_product_links l
            JOIN care_commerce.products p ON p.care_product_id=l.care_product_id
            WHERE l.recommendation_id=:recommendation_id
            ORDER BY l.relevance_rank ASC, l.created_at ASC
            """,
            {"recommendation_id": recommendation_id},
        )
        out: list[tuple[RecommendationProductLink, CareProduct]] = []
        for row in rows:
            link = RecommendationProductLink(
                recommendation_product_link_id=row["recommendation_product_link_id"],
                recommendation_id=row["recommendation_id"],
                care_product_id=row["care_product_id"],
                relevance_rank=row["relevance_rank"],
                justification_key=row["justification_key"],
                justification_text_key=row["justification_text_key"],
                created_at=row["created_at"],
            )
            product = CareProduct(
                care_product_id=row["care_product_id"],
                clinic_id=row["clinic_id"],
                sku=row["sku"],
                title_key=row["title_key"],
                description_key=row["description_key"],
                category=row["category"],
                use_case_tag=row["use_case_tag"],
                price_amount=row["price_amount"],
                currency_code=row["currency_code"],
                status=row["status"],
                pickup_supported=row["pickup_supported"],
                delivery_supported=row["delivery_supported"],
                sort_order=row["sort_order"],
                available_qty=row["available_qty"],
                created_at=row["product_created_at"],
                updated_at=row["product_updated_at"],
            )
            out.append((link, product))
        return out

    async def create_order(self, order: CareOrder, items: list[CareOrderItem]) -> CareOrder:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        INSERT INTO care_commerce.care_orders (
                          care_order_id, clinic_id, patient_id, booking_id, recommendation_id, status,
                          payment_mode, pickup_branch_id, total_amount, currency_code,
                          created_at, updated_at, confirmed_at, paid_at, ready_for_pickup_at,
                          issued_at, fulfilled_at, canceled_at, expired_at
                        ) VALUES (
                          :care_order_id, :clinic_id, :patient_id, :booking_id, :recommendation_id, :status,
                          :payment_mode, :pickup_branch_id, :total_amount, :currency_code,
                          :created_at, :updated_at, :confirmed_at, :paid_at, :ready_for_pickup_at,
                          :issued_at, :fulfilled_at, :canceled_at, :expired_at
                        )
                        """
                    ),
                    asdict(order),
                )
                if items:
                    await conn.execute(
                        text(
                            """
                            INSERT INTO care_commerce.care_order_items (
                              care_order_item_id, care_order_id, care_product_id, quantity,
                              unit_price, line_total, created_at
                            ) VALUES (
                              :care_order_item_id, :care_order_id, :care_product_id, :quantity,
                              :unit_price, :line_total, :created_at
                            )
                            """
                        ),
                        [asdict(item) for item in items],
                    )
                await self._append_order_event(conn, order)
            return order
        finally:
            await engine.dispose()

    async def get_order(self, care_order_id: str) -> CareOrder | None:
        row = await _fetch_one(self._db_config, "SELECT * FROM care_commerce.care_orders WHERE care_order_id=:id", {"id": care_order_id})
        return CareOrder(**row) if row else None

    async def list_order_items(self, care_order_id: str) -> list[CareOrderItem]:
        rows = await _fetch_all(self._db_config, "SELECT * FROM care_commerce.care_order_items WHERE care_order_id=:id ORDER BY created_at ASC", {"id": care_order_id})
        return [CareOrderItem(**row) for row in rows]

    async def save_order(self, order: CareOrder) -> CareOrder:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                previous = (await conn.execute(text("SELECT status FROM care_commerce.care_orders WHERE care_order_id=:id"), {"id": order.care_order_id})).scalar_one_or_none()
                await conn.execute(
                    text(
                        """
                        UPDATE care_commerce.care_orders
                        SET status=:status, updated_at=:updated_at, confirmed_at=:confirmed_at, paid_at=:paid_at,
                            ready_for_pickup_at=:ready_for_pickup_at, issued_at=:issued_at,
                            fulfilled_at=:fulfilled_at, canceled_at=:canceled_at, expired_at=:expired_at
                        WHERE care_order_id=:care_order_id
                        """
                    ),
                    asdict(order),
                )
                if previous != order.status:
                    await self._append_order_event(conn, order)
            return order
        finally:
            await engine.dispose()

    async def list_orders_for_patient(self, *, patient_id: str, clinic_id: str) -> list[CareOrder]:
        rows = await _fetch_all(
            self._db_config,
            "SELECT * FROM care_commerce.care_orders WHERE clinic_id=:clinic_id AND patient_id=:patient_id ORDER BY created_at DESC",
            {"clinic_id": clinic_id, "patient_id": patient_id},
        )
        return [CareOrder(**row) for row in rows]

    async def list_orders_for_admin(self, *, clinic_id: str, statuses: tuple[str, ...], limit: int = 30) -> list[CareOrder]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT * FROM care_commerce.care_orders
            WHERE clinic_id=:clinic_id AND status IN :statuses
            ORDER BY created_at ASC
            LIMIT :limit
            """,
            {"clinic_id": clinic_id, "statuses": tuple(statuses), "limit": limit},
            expanding=True,
        )
        return [CareOrder(**row) for row in rows]

    async def create_reservation(self, reservation: CareReservation) -> CareReservation:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        INSERT INTO care_commerce.care_reservations (
                          care_reservation_id, care_order_id, care_product_id, branch_id, status,
                          reserved_qty, expires_at, created_at, updated_at, released_at, consumed_at
                        ) VALUES (
                          :care_reservation_id, :care_order_id, :care_product_id, :branch_id, :status,
                          :reserved_qty, :expires_at, :created_at, :updated_at, :released_at, :consumed_at
                        )
                        """
                    ),
                    asdict(reservation),
                )
                await self._append_reservation_event(conn, reservation)
            return reservation
        finally:
            await engine.dispose()

    async def save_reservation(self, reservation: CareReservation) -> CareReservation:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                previous = (await conn.execute(text("SELECT status FROM care_commerce.care_reservations WHERE care_reservation_id=:id"), {"id": reservation.care_reservation_id})).scalar_one_or_none()
                await conn.execute(
                    text(
                        """
                        UPDATE care_commerce.care_reservations
                        SET status=:status, updated_at=:updated_at, released_at=:released_at,
                            consumed_at=:consumed_at, expires_at=:expires_at
                        WHERE care_reservation_id=:care_reservation_id
                        """
                    ),
                    asdict(reservation),
                )
                if previous != reservation.status:
                    await self._append_reservation_event(conn, reservation)
            return reservation
        finally:
            await engine.dispose()

    async def list_reservations_for_order(self, *, care_order_id: str) -> list[CareReservation]:
        rows = await _fetch_all(self._db_config, "SELECT * FROM care_commerce.care_reservations WHERE care_order_id=:id ORDER BY created_at ASC", {"id": care_order_id})
        return [CareReservation(**row) for row in rows]

    async def get_branch_product_availability(self, *, branch_id: str, care_product_id: str) -> BranchProductAvailability | None:
        row = await _fetch_one(
            self._db_config,
            """
            SELECT * FROM care_commerce.branch_product_availability
            WHERE branch_id=:branch_id AND care_product_id=:care_product_id
            """,
            {"branch_id": branch_id, "care_product_id": care_product_id},
        )
        return BranchProductAvailability(**row) if row else None

    async def upsert_branch_product_availability(self, availability: BranchProductAvailability) -> BranchProductAvailability:
        engine = create_engine(self._db_config)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        INSERT INTO care_commerce.branch_product_availability (
                          branch_product_availability_id, clinic_id, branch_id, care_product_id,
                          available_qty, reserved_qty, status, updated_at, created_at
                        ) VALUES (
                          :branch_product_availability_id, :clinic_id, :branch_id, :care_product_id,
                          :available_qty, :reserved_qty, :status, :updated_at, :created_at
                        )
                        ON CONFLICT (branch_id, care_product_id) DO UPDATE SET
                          clinic_id=EXCLUDED.clinic_id,
                          available_qty=EXCLUDED.available_qty,
                          reserved_qty=EXCLUDED.reserved_qty,
                          status=EXCLUDED.status,
                          updated_at=EXCLUDED.updated_at
                        """
                    ),
                    asdict(availability),
                )
                await self._append_availability_event(conn, availability)
            return availability
        finally:
            await engine.dispose()

    async def _append_order_event(self, conn, order: CareOrder) -> None:
        event_name = _ORDER_EVENT_BY_STATUS.get(order.status)
        if not event_name:
            return
        await OutboxRepository(self._db_config).append_on_connection(
            conn,
            build_event(
                event_name=event_name,
                producer_context="care_commerce.order",
                clinic_id=order.clinic_id,
                entity_type="care_order",
                entity_id=order.care_order_id,
                occurred_at=order.updated_at,
                payload={"patient_id": order.patient_id, "status": order.status, "recommendation_id": order.recommendation_id},
            ),
        )

    async def _append_reservation_event(self, conn, reservation: CareReservation) -> None:
        event_name = _RES_EVENT_BY_STATUS.get(reservation.status)
        if not event_name:
            return
        await OutboxRepository(self._db_config).append_on_connection(
            conn,
            build_event(
                event_name=event_name,
                producer_context="care_commerce.reservation",
                clinic_id=None,
                entity_type="care_reservation",
                entity_id=reservation.care_reservation_id,
                occurred_at=reservation.updated_at,
                payload={"care_order_id": reservation.care_order_id, "care_product_id": reservation.care_product_id, "status": reservation.status},
            ),
        )

    async def _append_availability_event(self, conn, availability: BranchProductAvailability) -> None:
        event_name = _AVAILABILITY_EVENT_BY_STATUS.get(availability.status)
        if not event_name:
            return
        await OutboxRepository(self._db_config).append_on_connection(
            conn,
            build_event(
                event_name=event_name,
                producer_context="care_commerce.availability",
                clinic_id=availability.clinic_id,
                entity_type="branch_product_availability",
                entity_id=availability.branch_product_availability_id,
                occurred_at=availability.updated_at,
                payload={
                    "branch_id": availability.branch_id,
                    "care_product_id": availability.care_product_id,
                    "available_qty": availability.available_qty,
                    "reserved_qty": availability.reserved_qty,
                    "status": availability.status,
                },
            ),
        )


async def _fetch_one(db_config: Any, sql: str, params: dict[str, object]) -> dict[str, object] | None:
    rows = await _fetch_all(db_config, sql, params)
    return rows[0] if rows else None


async def _fetch_all(db_config: Any, sql: str, params: dict[str, object], *, expanding: bool = False) -> list[dict[str, object]]:
    engine = create_engine(db_config)
    try:
        stmt = text(sql)
        if expanding and "statuses" in params:
            stmt = stmt.bindparams(bindparam("statuses", expanding=True))
        async with engine.connect() as conn:
            rows = (await conn.execute(stmt, params)).mappings().all()
            return [dict(row) for row in rows]
    finally:
        await engine.dispose()


async def _execute(db_config: Any, sql: str, params: dict[str, object]) -> None:
    engine = create_engine(db_config)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql), params)
    finally:
        await engine.dispose()
