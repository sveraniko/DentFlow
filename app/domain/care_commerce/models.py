from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

CARE_PRODUCT_STATUSES = frozenset({"active", "inactive", "archived"})
CARE_ORDER_STATUSES = frozenset(
    {
        "created",
        "awaiting_confirmation",
        "confirmed",
        "awaiting_payment",
        "paid",
        "ready_for_pickup",
        "issued",
        "fulfilled",
        "canceled",
        "expired",
    }
)
CARE_RESERVATION_STATUSES = frozenset({"created", "active", "released", "consumed", "expired"})
BRANCH_PRODUCT_AVAILABILITY_STATUSES = frozenset({"active", "inactive", "unavailable"})


@dataclass(frozen=True)
class CareProduct:
    care_product_id: str
    clinic_id: str
    sku: str
    title_key: str
    description_key: str | None
    category: str
    use_case_tag: str | None
    price_amount: int
    currency_code: str
    status: str
    pickup_supported: bool
    delivery_supported: bool
    sort_order: int | None
    available_qty: int | None
    created_at: datetime
    updated_at: datetime
    media_asset_id: str | None = None


@dataclass(frozen=True)
class RecommendationProductLink:
    recommendation_product_link_id: str
    recommendation_id: str
    care_product_id: str
    relevance_rank: int
    justification_key: str | None
    justification_text_key: str | None
    created_at: datetime


@dataclass(frozen=True)
class CareOrder:
    care_order_id: str
    clinic_id: str
    patient_id: str
    booking_id: str | None
    recommendation_id: str | None
    status: str
    payment_mode: str
    pickup_branch_id: str | None
    total_amount: int
    currency_code: str
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    paid_at: datetime | None
    ready_for_pickup_at: datetime | None
    issued_at: datetime | None
    fulfilled_at: datetime | None
    canceled_at: datetime | None
    expired_at: datetime | None


@dataclass(frozen=True)
class CareOrderItem:
    care_order_item_id: str
    care_order_id: str
    care_product_id: str
    quantity: int
    unit_price: int
    line_total: int
    created_at: datetime


@dataclass(frozen=True)
class CareReservation:
    care_reservation_id: str
    care_order_id: str
    care_product_id: str
    branch_id: str
    status: str
    reserved_qty: int
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    released_at: datetime | None
    consumed_at: datetime | None


@dataclass(frozen=True)
class BranchProductAvailability:
    branch_product_availability_id: str
    clinic_id: str
    branch_id: str
    care_product_id: str
    available_qty: int
    reserved_qty: int
    status: str
    updated_at: datetime
    created_at: datetime

    @property
    def free_qty(self) -> int:
        return max(0, self.available_qty - self.reserved_qty)
