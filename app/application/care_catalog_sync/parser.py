from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.application.care_catalog_sync.models import (
    CatalogBranchAvailabilityRow,
    CatalogIssue,
    CatalogProductI18nRow,
    CatalogProductRow,
    CatalogRecommendationLinkRow,
    CatalogRecommendationSetItemRow,
    CatalogRecommendationSetRow,
    CatalogSettingRow,
    CatalogImportResult,
    ParsedCatalogWorkbook,
)

_REQUIRED_TABS = (
    "products",
    "product_i18n",
    "branch_availability",
    "recommendation_sets",
    "recommendation_set_items",
    "recommendation_links",
)

_HEADERS: dict[str, tuple[str, ...]] = {
    "products": (
        "sku",
        "product_code",
        "status",
        "category",
        "use_case_tag",
        "price_amount",
        "currency_code",
        "pickup_supported",
        "delivery_supported",
        "sort_order",
        "default_pickup_branch_id",
        "media_asset_id",
        "notes",
    ),
    "product_i18n": (
        "sku",
        "locale",
        "title",
        "description",
        "short_label",
        "justification_text",
        "usage_hint",
    ),
    "branch_availability": (
        "branch_id",
        "sku",
        "on_hand_qty",
        "availability_enabled",
        "low_stock_threshold",
        "preferred_pickup",
    ),
    "recommendation_sets": (
        "set_code",
        "status",
        "title_ru",
        "title_en",
        "description_ru",
        "description_en",
        "sort_order",
    ),
    "recommendation_set_items": (
        "set_code",
        "sku",
        "position",
        "quantity",
        "notes",
    ),
    "recommendation_links": (
        "recommendation_type",
        "target_kind",
        "target_code",
        "relevance_rank",
        "active",
        "justification_key",
        "justification_text_ru",
        "justification_text_en",
    ),
    "settings": (
        "key",
        "value",
    ),
}

_ALLOWED_STATUS = {"active", "inactive", "archived"}
_ALLOWED_TARGET_KIND = {"product", "set"}


def parse_catalog_workbook(
    *,
    workbook: dict[str, list[dict[str, Any]]],
    known_branch_ids: set[str],
    source: str,
) -> tuple[ParsedCatalogWorkbook | None, CatalogImportResult]:
    result = CatalogImportResult(source=source)
    _validate_tabs_and_headers(workbook=workbook, result=result)
    if result.fatal_errors:
        return None, result

    products = _parse_products(workbook["products"], result)
    product_keys = {row.sku for row in products}
    sets = _parse_recommendation_sets(workbook["recommendation_sets"], result)
    set_codes = {row.set_code for row in sets}

    i18n = _parse_product_i18n(workbook["product_i18n"], product_keys, result)
    branch_availability = _parse_branch_availability(workbook["branch_availability"], product_keys, known_branch_ids, result)
    set_items = _parse_recommendation_set_items(workbook["recommendation_set_items"], product_keys, set_codes, result)
    links = _parse_recommendation_links(workbook["recommendation_links"], product_keys, set_codes, result)
    settings = _parse_settings(workbook.get("settings", []), result)

    parsed = ParsedCatalogWorkbook(
        products=products,
        product_i18n=i18n,
        branch_availability=branch_availability,
        recommendation_sets=sets,
        recommendation_set_items=set_items,
        recommendation_links=links,
        settings=settings,
    )
    return parsed, result


def _validate_tabs_and_headers(*, workbook: dict[str, list[dict[str, Any]]], result: CatalogImportResult) -> None:
    missing_tabs = [tab for tab in _REQUIRED_TABS if tab not in workbook]
    if missing_tabs:
        for tab in missing_tabs:
            result.fatal_errors.append(CatalogIssue(level="fatal", tab=tab, row_number=None, code="missing_tab", message=f"required tab '{tab}' is missing"))
        return

    for tab in _REQUIRED_TABS + ("settings",):
        if tab not in workbook:
            continue
        expected_headers = _HEADERS[tab]
        rows = workbook[tab]
        actual_headers = tuple(rows[0].keys()) if rows else expected_headers
        missing_headers = [h for h in expected_headers if h not in actual_headers]
        if missing_headers:
            result.fatal_errors.append(
                CatalogIssue(level="fatal", tab=tab, row_number=None, code="missing_headers", message=f"missing headers: {', '.join(missing_headers)}")
            )


def _parse_products(rows: list[dict[str, Any]], result: CatalogImportResult) -> list[CatalogProductRow]:
    tab = "products"
    out: list[CatalogProductRow] = []
    seen_sku: set[str] = set()
    for index, row in enumerate(rows, start=2):
        sku = _required_str(row, "sku")
        product_code = _required_str(row, "product_code")
        status = _required_str(row, "status").lower()
        if status not in _ALLOWED_STATUS:
            _row_error(result, tab, index, "invalid_status", f"unsupported status '{status}'")
            continue
        if sku in seen_sku:
            _row_error(result, tab, index, "duplicate_sku", f"duplicate sku '{sku}'")
            continue
        seen_sku.add(sku)
        price_amount = _decimal(row.get("price_amount"))
        if price_amount is None or price_amount < 0:
            _row_error(result, tab, index, "invalid_price", "price_amount must be a non-negative decimal")
            continue
        pickup = _bool(row.get("pickup_supported"))
        delivery = _bool(row.get("delivery_supported"))
        if pickup is None or delivery is None:
            _row_error(result, tab, index, "invalid_boolean", "pickup_supported and delivery_supported must be booleans")
            continue
        sort_order = _int(row.get("sort_order"), nullable=True)
        if sort_order is False:
            _row_error(result, tab, index, "invalid_sort_order", "sort_order must be integer")
            continue
        out.append(
            CatalogProductRow(
                sku=sku,
                product_code=product_code,
                status=status,
                category=_required_str(row, "category"),
                use_case_tag=_required_str(row, "use_case_tag"),
                price_amount=price_amount,
                currency_code=_required_str(row, "currency_code").upper(),
                pickup_supported=pickup,
                delivery_supported=delivery,
                sort_order=sort_order,
                default_pickup_branch_id=_optional_str(row, "default_pickup_branch_id"),
                media_asset_id=_optional_str(row, "media_asset_id"),
                notes=_optional_str(row, "notes"),
            )
        )
    result.tabs_processed.append(tab)
    return out


def _parse_product_i18n(rows: list[dict[str, Any]], product_keys: set[str], result: CatalogImportResult) -> list[CatalogProductI18nRow]:
    tab = "product_i18n"
    out: list[CatalogProductI18nRow] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, start=2):
        sku = _required_str(row, "sku")
        locale = _required_str(row, "locale").lower()
        if sku not in product_keys:
            _row_error(result, tab, index, "unknown_sku", f"unknown sku '{sku}'")
            continue
        key = (sku, locale)
        if key in seen:
            _row_error(result, tab, index, "duplicate_locale", f"duplicate locale row for '{sku}/{locale}'")
            continue
        seen.add(key)
        out.append(
            CatalogProductI18nRow(
                sku=sku,
                locale=locale,
                title=_required_str(row, "title"),
                description=_required_str(row, "description"),
                short_label=_optional_str(row, "short_label"),
                justification_text=_optional_str(row, "justification_text"),
                usage_hint=_optional_str(row, "usage_hint"),
            )
        )
    result.tabs_processed.append(tab)
    return out


def _parse_branch_availability(
    rows: list[dict[str, Any]],
    product_keys: set[str],
    known_branch_ids: set[str],
    result: CatalogImportResult,
) -> list[CatalogBranchAvailabilityRow]:
    tab = "branch_availability"
    out: list[CatalogBranchAvailabilityRow] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, start=2):
        branch_id = _required_str(row, "branch_id")
        sku = _required_str(row, "sku")
        if branch_id not in known_branch_ids:
            _row_error(result, tab, index, "unknown_branch", f"unknown branch '{branch_id}'")
            continue
        if sku not in product_keys:
            _row_error(result, tab, index, "unknown_sku", f"unknown sku '{sku}'")
            continue
        key = (branch_id, sku)
        if key in seen:
            _row_error(result, tab, index, "duplicate_branch_sku", f"duplicate branch/sku '{branch_id}/{sku}'")
            continue
        seen.add(key)
        on_hand_qty = _int(row.get("on_hand_qty"))
        if on_hand_qty is None or on_hand_qty < 0:
            _row_error(result, tab, index, "invalid_on_hand_qty", "on_hand_qty must be integer >= 0")
            continue
        enabled = _bool(row.get("availability_enabled"))
        preferred_pickup = _bool(row.get("preferred_pickup"), default=False)
        if enabled is None or preferred_pickup is None:
            _row_error(result, tab, index, "invalid_boolean", "availability_enabled/preferred_pickup must be booleans")
            continue
        low_stock = _int(row.get("low_stock_threshold"), nullable=True)
        if low_stock is False or (isinstance(low_stock, int) and low_stock < 0):
            _row_error(result, tab, index, "invalid_low_stock_threshold", "low_stock_threshold must be integer >= 0")
            continue
        out.append(
            CatalogBranchAvailabilityRow(
                branch_id=branch_id,
                sku=sku,
                on_hand_qty=on_hand_qty,
                availability_enabled=enabled,
                low_stock_threshold=low_stock,
                preferred_pickup=preferred_pickup,
            )
        )
    result.tabs_processed.append(tab)
    return out


def _parse_recommendation_sets(rows: list[dict[str, Any]], result: CatalogImportResult) -> list[CatalogRecommendationSetRow]:
    tab = "recommendation_sets"
    out: list[CatalogRecommendationSetRow] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        set_code = _required_str(row, "set_code")
        status = _required_str(row, "status").lower()
        if set_code in seen:
            _row_error(result, tab, index, "duplicate_set_code", f"duplicate set_code '{set_code}'")
            continue
        if status not in _ALLOWED_STATUS:
            _row_error(result, tab, index, "invalid_status", f"unsupported status '{status}'")
            continue
        seen.add(set_code)
        sort_order = _int(row.get("sort_order"), nullable=True)
        if sort_order is False:
            _row_error(result, tab, index, "invalid_sort_order", "sort_order must be integer")
            continue
        out.append(
            CatalogRecommendationSetRow(
                set_code=set_code,
                status=status,
                title_ru=_optional_str(row, "title_ru"),
                title_en=_optional_str(row, "title_en"),
                description_ru=_optional_str(row, "description_ru"),
                description_en=_optional_str(row, "description_en"),
                sort_order=sort_order,
            )
        )
    result.tabs_processed.append(tab)
    return out


def _parse_recommendation_set_items(
    rows: list[dict[str, Any]],
    product_keys: set[str],
    set_codes: set[str],
    result: CatalogImportResult,
) -> list[CatalogRecommendationSetItemRow]:
    tab = "recommendation_set_items"
    out: list[CatalogRecommendationSetItemRow] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, start=2):
        set_code = _required_str(row, "set_code")
        sku = _required_str(row, "sku")
        if set_code not in set_codes:
            _row_error(result, tab, index, "unknown_set_code", f"unknown set_code '{set_code}'")
            continue
        if sku not in product_keys:
            _row_error(result, tab, index, "unknown_sku", f"unknown sku '{sku}'")
            continue
        key = (set_code, sku)
        if key in seen:
            _row_error(result, tab, index, "duplicate_set_sku", f"duplicate set item '{set_code}/{sku}'")
            continue
        seen.add(key)
        position = _int(row.get("position"))
        quantity = _int(row.get("quantity"), nullable=True)
        if position is None or position < 1:
            _row_error(result, tab, index, "invalid_position", "position must be integer >= 1")
            continue
        if quantity is False:
            _row_error(result, tab, index, "invalid_quantity", "quantity must be integer >= 1")
            continue
        item_quantity = 1 if quantity is None else quantity
        if item_quantity < 1:
            _row_error(result, tab, index, "invalid_quantity", "quantity must be integer >= 1")
            continue
        out.append(
            CatalogRecommendationSetItemRow(
                set_code=set_code,
                sku=sku,
                position=position,
                quantity=item_quantity,
                notes=_optional_str(row, "notes"),
            )
        )
    result.tabs_processed.append(tab)
    return out


def _parse_recommendation_links(
    rows: list[dict[str, Any]],
    product_keys: set[str],
    set_codes: set[str],
    result: CatalogImportResult,
) -> list[CatalogRecommendationLinkRow]:
    tab = "recommendation_links"
    out: list[CatalogRecommendationLinkRow] = []
    for index, row in enumerate(rows, start=2):
        target_kind = _required_str(row, "target_kind").lower()
        target_code = _required_str(row, "target_code")
        if target_kind not in _ALLOWED_TARGET_KIND:
            _row_error(result, tab, index, "invalid_target_kind", f"unsupported target_kind '{target_kind}'")
            continue
        if target_kind == "product" and target_code not in product_keys:
            _row_error(result, tab, index, "unknown_sku", f"unknown sku '{target_code}'")
            continue
        if target_kind == "set" and target_code not in set_codes:
            _row_error(result, tab, index, "unknown_set_code", f"unknown set_code '{target_code}'")
            continue
        relevance_rank = _int(row.get("relevance_rank"))
        active = _bool(row.get("active"))
        if relevance_rank is None:
            _row_error(result, tab, index, "invalid_rank", "relevance_rank must be integer")
            continue
        if active is None:
            _row_error(result, tab, index, "invalid_active", "active must be boolean")
            continue
        out.append(
            CatalogRecommendationLinkRow(
                recommendation_type=_required_str(row, "recommendation_type"),
                target_kind=target_kind,
                target_code=target_code,
                relevance_rank=relevance_rank,
                active=active,
                justification_key=_optional_str(row, "justification_key"),
                justification_text_ru=_optional_str(row, "justification_text_ru"),
                justification_text_en=_optional_str(row, "justification_text_en"),
            )
        )
    result.tabs_processed.append(tab)
    return out


def _parse_settings(rows: list[dict[str, Any]], result: CatalogImportResult) -> list[CatalogSettingRow]:
    tab = "settings"
    out: list[CatalogSettingRow] = []
    for index, row in enumerate(rows, start=2):
        key = _required_str(row, "key")
        value = _required_str(row, "value")
        out.append(CatalogSettingRow(key=key, value=value))
    if rows:
        result.tabs_processed.append(tab)
    return out


def _required_str(row: dict[str, Any], key: str) -> str:
    value = _optional_str(row, key)
    if value is None:
        return ""
    return value


def _optional_str(row: dict[str, Any], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        normalized = " ".join(value.strip().split())
        return normalized or None
    normalized = str(value).strip()
    return normalized or None


def _bool(value: Any, *, default: bool | None = None) -> bool | None:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    mapping = {
        "true": True,
        "false": False,
        "1": True,
        "0": False,
        "yes": True,
        "no": False,
        "y": True,
        "n": False,
    }
    return mapping.get(normalized)


def _int(value: Any, *, nullable: bool = False) -> int | None | bool:
    if value is None or value == "":
        return None if nullable else None
    if isinstance(value, bool):
        return False if nullable else None
    try:
        return int(str(value).strip())
    except ValueError:
        return False if nullable else None


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def _row_error(result: CatalogImportResult, tab: str, row_number: int, code: str, message: str) -> None:
    result.validation_errors.append(CatalogIssue(level="error", tab=tab, row_number=row_number, code=code, message=message))
    stats = result.ensure_tab(tab)
    result.stats[tab] = type(stats)(tab=stats.tab, added=stats.added, updated=stats.updated, skipped=stats.skipped + 1, unchanged=stats.unchanged)
