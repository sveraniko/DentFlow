from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

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
        row = await _fetch_one(self._db_config, "SELECT care_product_id, clinic_id, sku, title_key, description_key, category, use_case_tag, price_amount, currency_code, status, pickup_supported, delivery_supported, sort_order, available_qty, created_at, updated_at FROM care_commerce.products WHERE care_product_id=:id", {"id": care_product_id})
        return CareProduct(**row) if row else None

    async def list_active_products_by_clinic(self, *, clinic_id: str) -> list[CareProduct]:
        rows = await _fetch_all(
            self._db_config,
            """
            SELECT care_product_id, clinic_id, sku, title_key, description_key, category, use_case_tag, price_amount, currency_code, status, pickup_supported, delivery_supported, sort_order, available_qty, created_at, updated_at
            FROM care_commerce.products
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

    async def list_catalog_products_by_recommendation_type(self, *, clinic_id: str, recommendation_type: str) -> list[tuple[RecommendationProductLink, CareProduct]]:
        rows = await _fetch_all(
            self._db_config,
            """
            WITH direct_links AS (
              SELECT rl.target_code AS sku, rl.relevance_rank, rl.justification_key,
                     COALESCE(rl.justification_text_en, rl.justification_text_ru) AS justification_text
              FROM care_commerce.recommendation_links rl
              WHERE rl.clinic_id=:clinic_id AND rl.recommendation_type=:recommendation_type AND rl.active=TRUE AND rl.target_kind='product'
            ),
            set_links AS (
              SELECT p.sku AS sku, rl.relevance_rank + rsi.position AS relevance_rank, rl.justification_key,
                     COALESCE(rl.justification_text_en, rl.justification_text_ru) AS justification_text
              FROM care_commerce.recommendation_links rl
              JOIN care_commerce.recommendation_sets rs ON rs.clinic_id=rl.clinic_id AND rs.set_code=rl.target_code
              JOIN care_commerce.recommendation_set_items rsi ON rsi.care_recommendation_set_id=rs.care_recommendation_set_id
              JOIN care_commerce.products p ON p.care_product_id=rsi.care_product_id
              WHERE rl.clinic_id=:clinic_id AND rl.recommendation_type=:recommendation_type AND rl.active=TRUE AND rl.target_kind='set' AND rs.status='active'
            ),
            links AS (
              SELECT * FROM direct_links
              UNION ALL
              SELECT * FROM set_links
            )
            SELECT l.sku, l.relevance_rank, l.justification_key, l.justification_text,
                   p.care_product_id, p.clinic_id, p.title_key, p.description_key,
                   p.category, p.use_case_tag, p.price_amount, p.currency_code,
                   p.status, p.pickup_supported, p.delivery_supported, p.sort_order,
                   p.available_qty, p.created_at, p.updated_at
            FROM links l
            JOIN care_commerce.products p ON p.clinic_id=:clinic_id AND p.sku=l.sku
            WHERE p.status='active'
            ORDER BY l.relevance_rank ASC, p.sort_order NULLS LAST, p.created_at ASC
            """,
            {"clinic_id": clinic_id, "recommendation_type": recommendation_type},
        )
        out: list[tuple[RecommendationProductLink, CareProduct]] = []
        for row in rows:
            link = RecommendationProductLink(
                recommendation_product_link_id=f"catalog_{row['sku']}_{row['relevance_rank']}",
                recommendation_id=f"catalog::{recommendation_type}",
                care_product_id=row["care_product_id"],
                relevance_rank=row["relevance_rank"],
                justification_key=row["justification_key"],
                justification_text_key=row["justification_text"],
                created_at=row["updated_at"],
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
                created_at=row["created_at"],
                updated_at=row["updated_at"],
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


    async def list_branch_ids(self, *, clinic_id: str) -> set[str]:
        rows = await _fetch_all(
            self._db_config,
            "SELECT branch_id FROM core_reference.branches WHERE clinic_id=:clinic_id",
            {"clinic_id": clinic_id},
        )
        return {str(row["branch_id"]) for row in rows}

    async def upsert_catalog_product(self, *, clinic_id: str, row, now) -> str:
        existing = await _fetch_one(
            self._db_config,
            "SELECT care_product_id, product_code, status, category, use_case_tag, price_amount, currency_code, pickup_supported, delivery_supported, sort_order, title_key, description_key FROM care_commerce.products WHERE clinic_id=:clinic_id AND sku=:sku",
            {"clinic_id": clinic_id, "sku": row.sku},
        )
        care_product_id = str(existing["care_product_id"]) if existing else f"cp_{uuid4().hex[:16]}"
        title_key = f"care.catalog.{row.sku}.title"
        description_key = f"care.catalog.{row.sku}.description"
        await _execute(
            self._db_config,
            """
            INSERT INTO care_commerce.products (
              care_product_id, clinic_id, sku, title_key, description_key, product_code,
              category, use_case_tag, price_amount, currency_code, status,
              pickup_supported, delivery_supported, sort_order, available_qty,
              created_at, updated_at
            ) VALUES (
              :care_product_id, :clinic_id, :sku, :title_key, :description_key, :product_code,
              :category, :use_case_tag, :price_amount, :currency_code, :status,
              :pickup_supported, :delivery_supported, :sort_order, NULL,
              :created_at, :updated_at
            )
            ON CONFLICT (clinic_id, sku) DO UPDATE SET
              product_code=EXCLUDED.product_code,
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
              updated_at=EXCLUDED.updated_at
            """,
            {
                "care_product_id": care_product_id,
                "clinic_id": clinic_id,
                "sku": row.sku,
                "title_key": title_key,
                "description_key": description_key,
                "product_code": row.product_code,
                "category": row.category,
                "use_case_tag": row.use_case_tag,
                "price_amount": int(row.price_amount * 100),
                "currency_code": row.currency_code,
                "status": row.status,
                "pickup_supported": row.pickup_supported,
                "delivery_supported": row.delivery_supported,
                "sort_order": row.sort_order,
                "created_at": now,
                "updated_at": now,
            },
        )
        if not existing:
            return "added"
        changed = (
            existing["product_code"] != row.product_code
            or existing["status"] != row.status
            or existing["category"] != row.category
            or existing["use_case_tag"] != row.use_case_tag
            or int(existing["price_amount"]) != int(row.price_amount * 100)
            or existing["currency_code"] != row.currency_code
            or bool(existing["pickup_supported"]) != row.pickup_supported
            or bool(existing["delivery_supported"]) != row.delivery_supported
            or existing["sort_order"] != row.sort_order
            or existing["title_key"] != title_key
            or existing["description_key"] != description_key
        )
        return "updated" if changed else "unchanged"

    async def upsert_catalog_product_i18n(self, *, clinic_id: str, row, now) -> str:
        product = await _fetch_one(
            self._db_config,
            "SELECT care_product_id FROM care_commerce.products WHERE clinic_id=:clinic_id AND sku=:sku",
            {"clinic_id": clinic_id, "sku": row.sku},
        )
        if not product:
            return "skipped"
        existing = await _fetch_one(
            self._db_config,
            "SELECT title, description, short_label, justification_text, usage_hint FROM care_commerce.product_i18n WHERE care_product_id=:care_product_id AND locale=:locale",
            {"care_product_id": product["care_product_id"], "locale": row.locale},
        )
        await _execute(
            self._db_config,
            """
            INSERT INTO care_commerce.product_i18n (
              care_product_i18n_id, clinic_id, care_product_id, locale, title, description,
              short_label, justification_text, usage_hint, created_at, updated_at
            ) VALUES (
              :care_product_i18n_id, :clinic_id, :care_product_id, :locale, :title, :description,
              :short_label, :justification_text, :usage_hint, :created_at, :updated_at
            )
            ON CONFLICT (care_product_id, locale) DO UPDATE SET
              title=EXCLUDED.title,
              description=EXCLUDED.description,
              short_label=EXCLUDED.short_label,
              justification_text=EXCLUDED.justification_text,
              usage_hint=EXCLUDED.usage_hint,
              updated_at=EXCLUDED.updated_at
            """,
            {
                "care_product_i18n_id": f"cpi18n_{uuid4().hex[:16]}",
                "clinic_id": clinic_id,
                "care_product_id": product["care_product_id"],
                "locale": row.locale,
                "title": row.title,
                "description": row.description,
                "short_label": row.short_label,
                "justification_text": row.justification_text,
                "usage_hint": row.usage_hint,
                "created_at": now,
                "updated_at": now,
            },
        )
        if not existing:
            return "added"
        changed = any(existing[key] != getattr(row, key) for key in ("title", "description", "short_label", "justification_text", "usage_hint"))
        return "updated" if changed else "unchanged"

    async def upsert_branch_availability_baseline(self, *, clinic_id: str, row, now) -> str:
        product = await _fetch_one(
            self._db_config,
            "SELECT care_product_id FROM care_commerce.products WHERE clinic_id=:clinic_id AND sku=:sku",
            {"clinic_id": clinic_id, "sku": row.sku},
        )
        if not product:
            return "skipped"
        existing = await _fetch_one(
            self._db_config,
            "SELECT available_qty, reserved_qty, status FROM care_commerce.branch_product_availability WHERE branch_id=:branch_id AND care_product_id=:care_product_id",
            {"branch_id": row.branch_id, "care_product_id": product["care_product_id"]},
        )
        status = "active" if row.availability_enabled else "inactive"
        await _execute(
            self._db_config,
            """
            INSERT INTO care_commerce.branch_product_availability (
              branch_product_availability_id, clinic_id, branch_id, care_product_id,
              available_qty, reserved_qty, status, created_at, updated_at
            ) VALUES (
              :branch_product_availability_id, :clinic_id, :branch_id, :care_product_id,
              :available_qty, :reserved_qty, :status, :created_at, :updated_at
            )
            ON CONFLICT (branch_id, care_product_id) DO UPDATE SET
              clinic_id=EXCLUDED.clinic_id,
              available_qty=EXCLUDED.available_qty,
              status=EXCLUDED.status,
              updated_at=EXCLUDED.updated_at
            """,
            {
                "branch_product_availability_id": f"bpa_{uuid4().hex[:16]}",
                "clinic_id": clinic_id,
                "branch_id": row.branch_id,
                "care_product_id": product["care_product_id"],
                "available_qty": row.on_hand_qty,
                "reserved_qty": int(existing["reserved_qty"]) if existing else 0,
                "status": status,
                "created_at": now,
                "updated_at": now,
            },
        )
        if not existing:
            return "added"
        changed = int(existing["available_qty"]) != row.on_hand_qty or existing["status"] != status
        return "updated" if changed else "unchanged"

    async def upsert_recommendation_set(self, *, clinic_id: str, row, now) -> str:
        existing = await _fetch_one(
            self._db_config,
            "SELECT status, title_ru, title_en, description_ru, description_en, sort_order FROM care_commerce.recommendation_sets WHERE clinic_id=:clinic_id AND set_code=:set_code",
            {"clinic_id": clinic_id, "set_code": row.set_code},
        )
        await _execute(
            self._db_config,
            """
            INSERT INTO care_commerce.recommendation_sets (
              care_recommendation_set_id, clinic_id, set_code, status, title_ru, title_en,
              description_ru, description_en, sort_order, created_at, updated_at
            ) VALUES (
              :care_recommendation_set_id, :clinic_id, :set_code, :status, :title_ru, :title_en,
              :description_ru, :description_en, :sort_order, :created_at, :updated_at
            )
            ON CONFLICT (clinic_id, set_code) DO UPDATE SET
              status=EXCLUDED.status,
              title_ru=EXCLUDED.title_ru,
              title_en=EXCLUDED.title_en,
              description_ru=EXCLUDED.description_ru,
              description_en=EXCLUDED.description_en,
              sort_order=EXCLUDED.sort_order,
              updated_at=EXCLUDED.updated_at
            """,
            {
                "care_recommendation_set_id": f"crs_{uuid4().hex[:16]}",
                "clinic_id": clinic_id,
                "set_code": row.set_code,
                "status": row.status,
                "title_ru": row.title_ru,
                "title_en": row.title_en,
                "description_ru": row.description_ru,
                "description_en": row.description_en,
                "sort_order": row.sort_order,
                "created_at": now,
                "updated_at": now,
            },
        )
        if not existing:
            return "added"
        changed = any(existing[key] != getattr(row, key) for key in ("status", "title_ru", "title_en", "description_ru", "description_en", "sort_order"))
        return "updated" if changed else "unchanged"

    async def upsert_recommendation_set_item(self, *, clinic_id: str, row, now) -> str:
        product = await _fetch_one(
            self._db_config,
            "SELECT care_product_id FROM care_commerce.products WHERE clinic_id=:clinic_id AND sku=:sku",
            {"clinic_id": clinic_id, "sku": row.sku},
        )
        rec_set = await _fetch_one(
            self._db_config,
            "SELECT care_recommendation_set_id FROM care_commerce.recommendation_sets WHERE clinic_id=:clinic_id AND set_code=:set_code",
            {"clinic_id": clinic_id, "set_code": row.set_code},
        )
        if not product or not rec_set:
            return "skipped"
        existing = await _fetch_one(
            self._db_config,
            "SELECT position, quantity, notes FROM care_commerce.recommendation_set_items WHERE care_recommendation_set_id=:set_id AND care_product_id=:product_id",
            {"set_id": rec_set["care_recommendation_set_id"], "product_id": product["care_product_id"]},
        )
        await _execute(
            self._db_config,
            """
            INSERT INTO care_commerce.recommendation_set_items (
              care_recommendation_set_item_id, care_recommendation_set_id, care_product_id,
              position, quantity, notes, created_at, updated_at
            ) VALUES (
              :care_recommendation_set_item_id, :care_recommendation_set_id, :care_product_id,
              :position, :quantity, :notes, :created_at, :updated_at
            )
            ON CONFLICT (care_recommendation_set_id, care_product_id) DO UPDATE SET
              position=EXCLUDED.position,
              quantity=EXCLUDED.quantity,
              notes=EXCLUDED.notes,
              updated_at=EXCLUDED.updated_at
            """,
            {
                "care_recommendation_set_item_id": f"crsi_{uuid4().hex[:16]}",
                "care_recommendation_set_id": rec_set["care_recommendation_set_id"],
                "care_product_id": product["care_product_id"],
                "position": row.position,
                "quantity": row.quantity,
                "notes": row.notes,
                "created_at": now,
                "updated_at": now,
            },
        )
        if not existing:
            return "added"
        changed = existing["position"] != row.position or existing["quantity"] != row.quantity or existing["notes"] != row.notes
        return "updated" if changed else "unchanged"

    async def upsert_recommendation_link(self, *, clinic_id: str, row, now) -> str:
        existing = await _fetch_one(
            self._db_config,
            "SELECT relevance_rank, active, justification_key, justification_text_ru, justification_text_en FROM care_commerce.recommendation_links WHERE clinic_id=:clinic_id AND recommendation_type=:recommendation_type AND target_kind=:target_kind AND target_code=:target_code",
            {
                "clinic_id": clinic_id,
                "recommendation_type": row.recommendation_type,
                "target_kind": row.target_kind,
                "target_code": row.target_code,
            },
        )
        await _execute(
            self._db_config,
            """
            INSERT INTO care_commerce.recommendation_links (
              care_recommendation_link_id, clinic_id, recommendation_type, target_kind, target_code,
              relevance_rank, active, justification_key, justification_text_ru, justification_text_en,
              created_at, updated_at
            ) VALUES (
              :care_recommendation_link_id, :clinic_id, :recommendation_type, :target_kind, :target_code,
              :relevance_rank, :active, :justification_key, :justification_text_ru, :justification_text_en,
              :created_at, :updated_at
            )
            ON CONFLICT (clinic_id, recommendation_type, target_kind, target_code) DO UPDATE SET
              relevance_rank=EXCLUDED.relevance_rank,
              active=EXCLUDED.active,
              justification_key=EXCLUDED.justification_key,
              justification_text_ru=EXCLUDED.justification_text_ru,
              justification_text_en=EXCLUDED.justification_text_en,
              updated_at=EXCLUDED.updated_at
            """,
            {
                "care_recommendation_link_id": f"crl_{uuid4().hex[:16]}",
                "clinic_id": clinic_id,
                "recommendation_type": row.recommendation_type,
                "target_kind": row.target_kind,
                "target_code": row.target_code,
                "relevance_rank": row.relevance_rank,
                "active": row.active,
                "justification_key": row.justification_key,
                "justification_text_ru": row.justification_text_ru,
                "justification_text_en": row.justification_text_en,
                "created_at": now,
                "updated_at": now,
            },
        )
        if not existing:
            return "added"
        changed = (
            existing["relevance_rank"] != row.relevance_rank
            or bool(existing["active"]) != row.active
            or existing["justification_key"] != row.justification_key
            or existing["justification_text_ru"] != row.justification_text_ru
            or existing["justification_text_en"] != row.justification_text_en
        )
        return "updated" if changed else "unchanged"

    async def upsert_catalog_setting(self, *, clinic_id: str, key: str, value: str, now) -> str:
        existing = await _fetch_one(
            self._db_config,
            "SELECT value FROM care_commerce.catalog_settings WHERE clinic_id=:clinic_id AND key=:key",
            {"clinic_id": clinic_id, "key": key},
        )
        await _execute(
            self._db_config,
            """
            INSERT INTO care_commerce.catalog_settings (
              care_catalog_setting_id, clinic_id, key, value, created_at, updated_at
            ) VALUES (
              :care_catalog_setting_id, :clinic_id, :key, :value, :created_at, :updated_at
            )
            ON CONFLICT (clinic_id, key) DO UPDATE SET
              value=EXCLUDED.value,
              updated_at=EXCLUDED.updated_at
            """,
            {
                "care_catalog_setting_id": f"ccs_{uuid4().hex[:16]}",
                "clinic_id": clinic_id,
                "key": key,
                "value": value,
                "created_at": now,
                "updated_at": now,
            },
        )
        if not existing:
            return "added"
        return "updated" if existing["value"] != value else "unchanged"

    async def apply_catalog_sync_transaction(self, *, clinic_id: str, parsed, now) -> dict[str, dict[str, int]]:
        engine = create_engine(self._db_config)
        tab_stats: dict[str, dict[str, int]] = {
            "products": {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0},
            "product_i18n": {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0},
            "branch_availability": {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0},
            "recommendation_sets": {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0},
            "recommendation_set_items": {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0},
            "recommendation_links": {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0},
            "settings": {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0},
        }
        try:
            async with engine.begin() as conn:
                for row in parsed.products:
                    existing = (
                        await conn.execute(
                            text(
                                "SELECT care_product_id, product_code, status, category, use_case_tag, price_amount, currency_code, pickup_supported, delivery_supported, sort_order, title_key, description_key FROM care_commerce.products WHERE clinic_id=:clinic_id AND sku=:sku"
                            ),
                            {"clinic_id": clinic_id, "sku": row.sku},
                        )
                    ).mappings().first()
                    care_product_id = str(existing["care_product_id"]) if existing else f"cp_{uuid4().hex[:16]}"
                    title_key = f"care.catalog.{row.sku}.title"
                    description_key = f"care.catalog.{row.sku}.description"
                    await conn.execute(
                        text(
                            """
                            INSERT INTO care_commerce.products (
                              care_product_id, clinic_id, sku, title_key, description_key, product_code,
                              category, use_case_tag, price_amount, currency_code, status,
                              pickup_supported, delivery_supported, sort_order, available_qty,
                              created_at, updated_at
                            ) VALUES (
                              :care_product_id, :clinic_id, :sku, :title_key, :description_key, :product_code,
                              :category, :use_case_tag, :price_amount, :currency_code, :status,
                              :pickup_supported, :delivery_supported, :sort_order, NULL,
                              :created_at, :updated_at
                            )
                            ON CONFLICT (clinic_id, sku) DO UPDATE SET
                              product_code=EXCLUDED.product_code,
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
                              updated_at=EXCLUDED.updated_at
                            """
                        ),
                        {
                            "care_product_id": care_product_id,
                            "clinic_id": clinic_id,
                            "sku": row.sku,
                            "title_key": title_key,
                            "description_key": description_key,
                            "product_code": row.product_code,
                            "category": row.category,
                            "use_case_tag": row.use_case_tag,
                            "price_amount": int(row.price_amount * 100),
                            "currency_code": row.currency_code,
                            "status": row.status,
                            "pickup_supported": row.pickup_supported,
                            "delivery_supported": row.delivery_supported,
                            "sort_order": row.sort_order,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    if not existing:
                        tab_stats["products"]["added"] += 1
                    else:
                        changed = (
                            existing["product_code"] != row.product_code
                            or existing["status"] != row.status
                            or existing["category"] != row.category
                            or existing["use_case_tag"] != row.use_case_tag
                            or int(existing["price_amount"]) != int(row.price_amount * 100)
                            or existing["currency_code"] != row.currency_code
                            or bool(existing["pickup_supported"]) != row.pickup_supported
                            or bool(existing["delivery_supported"]) != row.delivery_supported
                            or existing["sort_order"] != row.sort_order
                            or existing["title_key"] != title_key
                            or existing["description_key"] != description_key
                        )
                        tab_stats["products"]["updated" if changed else "unchanged"] += 1

                for row in parsed.product_i18n:
                    product = (
                        await conn.execute(
                            text("SELECT care_product_id FROM care_commerce.products WHERE clinic_id=:clinic_id AND sku=:sku"),
                            {"clinic_id": clinic_id, "sku": row.sku},
                        )
                    ).mappings().first()
                    if not product:
                        tab_stats["product_i18n"]["skipped"] += 1
                        continue
                    existing = (
                        await conn.execute(
                            text("SELECT title, description, short_label, justification_text, usage_hint FROM care_commerce.product_i18n WHERE care_product_id=:care_product_id AND locale=:locale"),
                            {"care_product_id": product["care_product_id"], "locale": row.locale},
                        )
                    ).mappings().first()
                    await conn.execute(
                        text(
                            """
                            INSERT INTO care_commerce.product_i18n (
                              care_product_i18n_id, clinic_id, care_product_id, locale, title, description,
                              short_label, justification_text, usage_hint, created_at, updated_at
                            ) VALUES (
                              :care_product_i18n_id, :clinic_id, :care_product_id, :locale, :title, :description,
                              :short_label, :justification_text, :usage_hint, :created_at, :updated_at
                            )
                            ON CONFLICT (care_product_id, locale) DO UPDATE SET
                              title=EXCLUDED.title,
                              description=EXCLUDED.description,
                              short_label=EXCLUDED.short_label,
                              justification_text=EXCLUDED.justification_text,
                              usage_hint=EXCLUDED.usage_hint,
                              updated_at=EXCLUDED.updated_at
                            """
                        ),
                        {
                            "care_product_i18n_id": f"cpi18n_{uuid4().hex[:16]}",
                            "clinic_id": clinic_id,
                            "care_product_id": product["care_product_id"],
                            "locale": row.locale,
                            "title": row.title,
                            "description": row.description,
                            "short_label": row.short_label,
                            "justification_text": row.justification_text,
                            "usage_hint": row.usage_hint,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    if not existing:
                        tab_stats["product_i18n"]["added"] += 1
                    else:
                        changed = any(existing[key] != getattr(row, key) for key in ("title", "description", "short_label", "justification_text", "usage_hint"))
                        tab_stats["product_i18n"]["updated" if changed else "unchanged"] += 1

                for row in parsed.branch_availability:
                    product = (
                        await conn.execute(
                            text("SELECT care_product_id FROM care_commerce.products WHERE clinic_id=:clinic_id AND sku=:sku"),
                            {"clinic_id": clinic_id, "sku": row.sku},
                        )
                    ).mappings().first()
                    if not product:
                        tab_stats["branch_availability"]["skipped"] += 1
                        continue
                    existing = (
                        await conn.execute(
                            text("SELECT available_qty, reserved_qty, status FROM care_commerce.branch_product_availability WHERE branch_id=:branch_id AND care_product_id=:care_product_id"),
                            {"branch_id": row.branch_id, "care_product_id": product["care_product_id"]},
                        )
                    ).mappings().first()
                    status = "active" if row.availability_enabled else "inactive"
                    await conn.execute(
                        text(
                            """
                            INSERT INTO care_commerce.branch_product_availability (
                              branch_product_availability_id, clinic_id, branch_id, care_product_id,
                              available_qty, reserved_qty, status, created_at, updated_at
                            ) VALUES (
                              :branch_product_availability_id, :clinic_id, :branch_id, :care_product_id,
                              :available_qty, :reserved_qty, :status, :created_at, :updated_at
                            )
                            ON CONFLICT (branch_id, care_product_id) DO UPDATE SET
                              clinic_id=EXCLUDED.clinic_id,
                              available_qty=EXCLUDED.available_qty,
                              status=EXCLUDED.status,
                              updated_at=EXCLUDED.updated_at
                            """
                        ),
                        {
                            "branch_product_availability_id": f"bpa_{uuid4().hex[:16]}",
                            "clinic_id": clinic_id,
                            "branch_id": row.branch_id,
                            "care_product_id": product["care_product_id"],
                            "available_qty": row.on_hand_qty,
                            "reserved_qty": int(existing["reserved_qty"]) if existing else 0,
                            "status": status,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    if not existing:
                        tab_stats["branch_availability"]["added"] += 1
                    else:
                        changed = int(existing["available_qty"]) != row.on_hand_qty or existing["status"] != status
                        tab_stats["branch_availability"]["updated" if changed else "unchanged"] += 1

                for row in parsed.recommendation_sets:
                    existing = (
                        await conn.execute(
                            text("SELECT status, title_ru, title_en, description_ru, description_en, sort_order FROM care_commerce.recommendation_sets WHERE clinic_id=:clinic_id AND set_code=:set_code"),
                            {"clinic_id": clinic_id, "set_code": row.set_code},
                        )
                    ).mappings().first()
                    await conn.execute(
                        text(
                            """
                            INSERT INTO care_commerce.recommendation_sets (
                              care_recommendation_set_id, clinic_id, set_code, status, title_ru, title_en,
                              description_ru, description_en, sort_order, created_at, updated_at
                            ) VALUES (
                              :care_recommendation_set_id, :clinic_id, :set_code, :status, :title_ru, :title_en,
                              :description_ru, :description_en, :sort_order, :created_at, :updated_at
                            )
                            ON CONFLICT (clinic_id, set_code) DO UPDATE SET
                              status=EXCLUDED.status,
                              title_ru=EXCLUDED.title_ru,
                              title_en=EXCLUDED.title_en,
                              description_ru=EXCLUDED.description_ru,
                              description_en=EXCLUDED.description_en,
                              sort_order=EXCLUDED.sort_order,
                              updated_at=EXCLUDED.updated_at
                            """
                        ),
                        {
                            "care_recommendation_set_id": f"crs_{uuid4().hex[:16]}",
                            "clinic_id": clinic_id,
                            "set_code": row.set_code,
                            "status": row.status,
                            "title_ru": row.title_ru,
                            "title_en": row.title_en,
                            "description_ru": row.description_ru,
                            "description_en": row.description_en,
                            "sort_order": row.sort_order,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    if not existing:
                        tab_stats["recommendation_sets"]["added"] += 1
                    else:
                        changed = any(existing[key] != getattr(row, key) for key in ("status", "title_ru", "title_en", "description_ru", "description_en", "sort_order"))
                        tab_stats["recommendation_sets"]["updated" if changed else "unchanged"] += 1

                for row in parsed.recommendation_set_items:
                    product = (
                        await conn.execute(
                            text("SELECT care_product_id FROM care_commerce.products WHERE clinic_id=:clinic_id AND sku=:sku"),
                            {"clinic_id": clinic_id, "sku": row.sku},
                        )
                    ).mappings().first()
                    rec_set = (
                        await conn.execute(
                            text("SELECT care_recommendation_set_id FROM care_commerce.recommendation_sets WHERE clinic_id=:clinic_id AND set_code=:set_code"),
                            {"clinic_id": clinic_id, "set_code": row.set_code},
                        )
                    ).mappings().first()
                    if not product or not rec_set:
                        tab_stats["recommendation_set_items"]["skipped"] += 1
                        continue
                    existing = (
                        await conn.execute(
                            text("SELECT position, quantity, notes FROM care_commerce.recommendation_set_items WHERE care_recommendation_set_id=:set_id AND care_product_id=:product_id"),
                            {"set_id": rec_set["care_recommendation_set_id"], "product_id": product["care_product_id"]},
                        )
                    ).mappings().first()
                    await conn.execute(
                        text(
                            """
                            INSERT INTO care_commerce.recommendation_set_items (
                              care_recommendation_set_item_id, care_recommendation_set_id, care_product_id,
                              position, quantity, notes, created_at, updated_at
                            ) VALUES (
                              :care_recommendation_set_item_id, :care_recommendation_set_id, :care_product_id,
                              :position, :quantity, :notes, :created_at, :updated_at
                            )
                            ON CONFLICT (care_recommendation_set_id, care_product_id) DO UPDATE SET
                              position=EXCLUDED.position,
                              quantity=EXCLUDED.quantity,
                              notes=EXCLUDED.notes,
                              updated_at=EXCLUDED.updated_at
                            """
                        ),
                        {
                            "care_recommendation_set_item_id": f"crsi_{uuid4().hex[:16]}",
                            "care_recommendation_set_id": rec_set["care_recommendation_set_id"],
                            "care_product_id": product["care_product_id"],
                            "position": row.position,
                            "quantity": row.quantity,
                            "notes": row.notes,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    if not existing:
                        tab_stats["recommendation_set_items"]["added"] += 1
                    else:
                        changed = existing["position"] != row.position or existing["quantity"] != row.quantity or existing["notes"] != row.notes
                        tab_stats["recommendation_set_items"]["updated" if changed else "unchanged"] += 1

                for row in parsed.recommendation_links:
                    existing = (
                        await conn.execute(
                            text("SELECT relevance_rank, active, justification_key, justification_text_ru, justification_text_en FROM care_commerce.recommendation_links WHERE clinic_id=:clinic_id AND recommendation_type=:recommendation_type AND target_kind=:target_kind AND target_code=:target_code"),
                            {
                                "clinic_id": clinic_id,
                                "recommendation_type": row.recommendation_type,
                                "target_kind": row.target_kind,
                                "target_code": row.target_code,
                            },
                        )
                    ).mappings().first()
                    await conn.execute(
                        text(
                            """
                            INSERT INTO care_commerce.recommendation_links (
                              care_recommendation_link_id, clinic_id, recommendation_type, target_kind, target_code,
                              relevance_rank, active, justification_key, justification_text_ru, justification_text_en,
                              created_at, updated_at
                            ) VALUES (
                              :care_recommendation_link_id, :clinic_id, :recommendation_type, :target_kind, :target_code,
                              :relevance_rank, :active, :justification_key, :justification_text_ru, :justification_text_en,
                              :created_at, :updated_at
                            )
                            ON CONFLICT (clinic_id, recommendation_type, target_kind, target_code) DO UPDATE SET
                              relevance_rank=EXCLUDED.relevance_rank,
                              active=EXCLUDED.active,
                              justification_key=EXCLUDED.justification_key,
                              justification_text_ru=EXCLUDED.justification_text_ru,
                              justification_text_en=EXCLUDED.justification_text_en,
                              updated_at=EXCLUDED.updated_at
                            """
                        ),
                        {
                            "care_recommendation_link_id": f"crl_{uuid4().hex[:16]}",
                            "clinic_id": clinic_id,
                            "recommendation_type": row.recommendation_type,
                            "target_kind": row.target_kind,
                            "target_code": row.target_code,
                            "relevance_rank": row.relevance_rank,
                            "active": row.active,
                            "justification_key": row.justification_key,
                            "justification_text_ru": row.justification_text_ru,
                            "justification_text_en": row.justification_text_en,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    if not existing:
                        tab_stats["recommendation_links"]["added"] += 1
                    else:
                        changed = (
                            existing["relevance_rank"] != row.relevance_rank
                            or bool(existing["active"]) != row.active
                            or existing["justification_key"] != row.justification_key
                            or existing["justification_text_ru"] != row.justification_text_ru
                            or existing["justification_text_en"] != row.justification_text_en
                        )
                        tab_stats["recommendation_links"]["updated" if changed else "unchanged"] += 1

                for row in parsed.settings:
                    existing = (
                        await conn.execute(
                            text("SELECT value FROM care_commerce.catalog_settings WHERE clinic_id=:clinic_id AND key=:key"),
                            {"clinic_id": clinic_id, "key": row.key},
                        )
                    ).mappings().first()
                    await conn.execute(
                        text(
                            """
                            INSERT INTO care_commerce.catalog_settings (
                              care_catalog_setting_id, clinic_id, key, value, created_at, updated_at
                            ) VALUES (
                              :care_catalog_setting_id, :clinic_id, :key, :value, :created_at, :updated_at
                            )
                            ON CONFLICT (clinic_id, key) DO UPDATE SET
                              value=EXCLUDED.value,
                              updated_at=EXCLUDED.updated_at
                            """
                        ),
                        {
                            "care_catalog_setting_id": f"ccs_{uuid4().hex[:16]}",
                            "clinic_id": clinic_id,
                            "key": row.key,
                            "value": row.value,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    if not existing:
                        tab_stats["settings"]["added"] += 1
                    else:
                        tab_stats["settings"]["updated" if existing["value"] != row.value else "unchanged"] += 1
            return tab_stats
        finally:
            await engine.dispose()

    async def get_product_i18n_content(self, *, care_product_id: str, locale: str) -> dict[str, str | None] | None:
        return await _fetch_one(
            self._db_config,
            """
            SELECT title, description, short_label, justification_text, usage_hint
            FROM care_commerce.product_i18n
            WHERE care_product_id=:care_product_id AND locale=:locale
            """,
            {"care_product_id": care_product_id, "locale": locale.lower()},
        )

    async def get_catalog_setting(self, *, clinic_id: str, key: str) -> str | None:
        row = await _fetch_one(
            self._db_config,
            "SELECT value FROM care_commerce.catalog_settings WHERE clinic_id=:clinic_id AND key=:key",
            {"clinic_id": clinic_id, "key": key},
        )
        if not row:
            return None
        value = row.get("value")
        return str(value) if value is not None else None

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
