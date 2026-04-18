from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class CatalogProductRow:
    sku: str
    product_code: str
    status: str
    category: str
    use_case_tag: str
    price_amount: Decimal
    currency_code: str
    pickup_supported: bool
    delivery_supported: bool
    sort_order: int | None
    default_pickup_branch_id: str | None
    media_asset_id: str | None
    notes: str | None


@dataclass(frozen=True)
class CatalogProductI18nRow:
    sku: str
    locale: str
    title: str
    description: str
    short_label: str | None
    justification_text: str | None
    usage_hint: str | None


@dataclass(frozen=True)
class CatalogBranchAvailabilityRow:
    branch_id: str
    sku: str
    on_hand_qty: int
    availability_enabled: bool
    low_stock_threshold: int | None
    preferred_pickup: bool


@dataclass(frozen=True)
class CatalogRecommendationSetRow:
    set_code: str
    status: str
    title_ru: str | None
    title_en: str | None
    description_ru: str | None
    description_en: str | None
    sort_order: int | None


@dataclass(frozen=True)
class CatalogRecommendationSetItemRow:
    set_code: str
    sku: str
    position: int
    quantity: int
    notes: str | None


@dataclass(frozen=True)
class CatalogRecommendationLinkRow:
    recommendation_type: str
    target_kind: str
    target_code: str
    relevance_rank: int
    active: bool
    justification_key: str | None
    justification_text_ru: str | None
    justification_text_en: str | None


@dataclass(frozen=True)
class CatalogSettingRow:
    key: str
    value: str


@dataclass(frozen=True)
class ParsedCatalogWorkbook:
    products: list[CatalogProductRow]
    product_i18n: list[CatalogProductI18nRow]
    branch_availability: list[CatalogBranchAvailabilityRow]
    recommendation_sets: list[CatalogRecommendationSetRow]
    recommendation_set_items: list[CatalogRecommendationSetItemRow]
    recommendation_links: list[CatalogRecommendationLinkRow]
    settings: list[CatalogSettingRow]


@dataclass(frozen=True)
class CatalogIssue:
    level: str
    tab: str
    row_number: int | None
    code: str
    message: str


@dataclass
class TabImportStats:
    tab: str
    added: int = 0
    updated: int = 0
    skipped: int = 0
    unchanged: int = 0


@dataclass
class CatalogImportResult:
    source: str
    tabs_processed: list[str] = field(default_factory=list)
    stats: dict[str, TabImportStats] = field(default_factory=dict)
    validation_errors: list[CatalogIssue] = field(default_factory=list)
    warnings: list[CatalogIssue] = field(default_factory=list)
    fatal_errors: list[CatalogIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.fatal_errors and not self.validation_errors

    def ensure_tab(self, tab: str) -> TabImportStats:
        if tab not in self.stats:
            self.stats[tab] = TabImportStats(tab=tab)
        return self.stats[tab]
