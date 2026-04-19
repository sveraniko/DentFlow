from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CardProfile(str, Enum):
    PRODUCT = "product"
    PATIENT = "patient"
    DOCTOR = "doctor"
    BOOKING = "booking"
    RECOMMENDATION = "recommendation"
    CARE_ORDER = "care_order"


class EntityType(str, Enum):
    CARE_PRODUCT = "care_product"
    PATIENT = "patient"
    DOCTOR = "doctor"
    BOOKING = "booking"
    RECOMMENDATION = "recommendation"
    CARE_ORDER = "care_order"


class CardMode(str, Enum):
    COMPACT = "compact"
    EXPANDED = "expanded"
    LIST_ROW = "list_row"
    PICKER = "picker"


class SourceContext(str, Enum):
    SEARCH_RESULTS = "search_results"
    DOCTOR_QUEUE = "doctor_queue"
    ADMIN_TODAY = "admin_today"
    ADMIN_CONFIRMATIONS = "admin_confirmations"
    ADMIN_RESCHEDULES = "admin_reschedules"
    ADMIN_PATIENTS = "admin_patients"
    ADMIN_CARE_PICKUPS = "admin_care_pickups"
    ADMIN_ISSUES = "admin_issues"
    RECOMMENDATION_DETAIL = "recommendation_detail"
    CARE_CATALOG_CATEGORY = "care_catalog_category"
    CARE_ORDER_LIST = "care_order_list"
    BOOKING_LIST = "booking_list"
    OWNER_ALERT = "owner_alert"


class CardAction(str, Enum):
    OPEN = "open"
    EXPAND = "expand"
    COLLAPSE = "collapse"
    BACK = "back"
    COVER = "cover"
    GALLERY = "gallery"
    NEXT = "next"
    PREV = "prev"
    PAGE = "page"
    HOME = "home"
    RESERVE = "reserve"
    CHANGE_BRANCH = "change_branch"
    BOOKINGS = "bookings"
    RECOMMENDATIONS = "recommendations"
    CHART = "chart"
    ORDERS = "orders"
    TODAY = "today"
    SCHEDULE = "schedule"
    CONFIRM = "confirm"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"
    CHECKED_IN = "checked_in"
    IN_SERVICE = "in_service"
    COMPLETE = "complete"
    OPEN_PATIENT = "open_patient"
    OPEN_CHART = "open_chart"
    OPEN_RECOMMENDATION = "open_recommendation"
    OPEN_CARE_ORDER = "open_care_order"


@dataclass(slots=True, frozen=True)
class SourceRef:
    context: SourceContext
    source_ref: str | None = None
    page_or_index: int | str | None = None


@dataclass(slots=True, frozen=True)
class CardBadge:
    text: str


@dataclass(slots=True, frozen=True)
class CardMetaLine:
    key: str
    value: str


@dataclass(slots=True, frozen=True)
class CardActionButton:
    action: CardAction
    label: str


@dataclass(slots=True, frozen=True)
class CardNavigation:
    can_go_back: bool = True
    has_home: bool = False


@dataclass(slots=True, frozen=True)
class CardMedia:
    has_cover: bool = False
    gallery_size: int = 0


@dataclass(slots=True, frozen=True)
class CardShell:
    profile: CardProfile
    entity_type: EntityType
    entity_id: str
    mode: CardMode
    title: str
    subtitle: str | None
    source: SourceRef
    state_token: str
    badges: tuple[CardBadge, ...] = ()
    meta_lines: tuple[CardMetaLine, ...] = ()
    detail_lines: tuple[str, ...] = ()
    actions: tuple[CardActionButton, ...] = ()
    navigation: CardNavigation = field(default_factory=CardNavigation)
    media: CardMedia = field(default_factory=CardMedia)

    def with_mode(self, mode: CardMode) -> "CardShell":
        return CardShell(
            profile=self.profile,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            mode=mode,
            title=self.title,
            subtitle=self.subtitle,
            source=self.source,
            state_token=self.state_token,
            badges=self.badges,
            meta_lines=self.meta_lines,
            detail_lines=self.detail_lines,
            actions=self.actions,
            navigation=self.navigation,
            media=self.media,
        )
