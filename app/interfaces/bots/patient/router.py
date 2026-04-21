from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup

from app.application.communication import ReminderActionService
from app.application.care_commerce import CareCommerceService
from app.application.booking.orchestration_outcomes import ConflictOutcome, InvalidStateOutcome, OrchestrationSuccess, SlotUnavailableOutcome
from app.application.booking.telegram_flow import BookingControlResolutionResult, BookingPatientFlowService
from app.application.clinic_reference import ClinicReferenceService
from app.common.i18n import I18nService
from app.application.recommendation import RecommendationService
from app.interfaces.cards import (
    BookingCardAdapter,
    BookingRuntimeViewBuilder,
    CareOrderCardAdapter,
    CareOrderRuntimeSnapshot,
    CareOrderRuntimeViewBuilder,
    CardAction,
    CardCallback,
    CardCallbackCodec,
    CardCallbackError,
    CardMode,
    CardProfile,
    CardRuntimeCoordinator,
    CardShellRenderer,
    EntityType,
    PanelFamily,
    ProductCardAdapter,
    ProductRuntimeSnapshot,
    ProductRuntimeViewBuilder,
    SourceContext,
    SourceRef,
)


@dataclass(slots=True)
class _CareViewState:
    selected_category: str | None = None
    category_page: int = 0
    recommendation_id: str | None = None
    recommendation_type: str | None = None
    recommendation_reason: str | None = None
    recommendation_page: int = 0
    recommendation_products: list[str] | None = None
    recommendation_source_ref: str | None = None
    selected_branch_by_product: dict[str, str] | None = None
    product_page_by_category: dict[str, int] | None = None
    media_product_id: str | None = None
    media_index_by_product: dict[str, int] | None = None
    media_return_mode_by_product: dict[str, str] | None = None
    care_order_page: int = 0


@dataclass(slots=True)
class _PatientFlowState:
    booking_session_id: str = ""
    booking_mode: str = "new_booking_contact"
    care: _CareViewState | None = None


@dataclass(slots=True)
class _CompactProductRowCard:
    product_id: str
    shell: Any

    def button_label(self) -> str:
        meta = {row.key: row.value for row in self.shell.meta_lines}
        parts = [
            self.shell.title,
            meta.get("price", ""),
            meta.get("availability", ""),
        ]
        if self.shell.badges:
            parts.append(self.shell.badges[0].text)
        if meta.get("label"):
            parts.append(meta["label"])
        if meta.get("branch"):
            parts.append(meta["branch"])
        parts = [part for part in parts if part]
        return " · ".join(parts)[:62]

    def supports_open_action(self) -> bool:
        return any(action.action == CardAction.OPEN for action in self.shell.actions)

    def open_source_ref(self, fallback: str) -> str:
        return self.shell.source.source_ref or fallback

    def recommendation_context_badge(self) -> str | None:
        if self.shell.source.context != SourceContext.RECOMMENDATION_DETAIL or not self.shell.badges:
            return None
        return self.shell.badges[0].text

    def branch_hint(self) -> str | None:
        return next((meta.value for meta in self.shell.meta_lines if meta.key == "branch"), None)

    def availability_label(self) -> str:
        return next((meta.value for meta in self.shell.meta_lines if meta.key == "availability"), "")

    def short_label(self) -> str | None:
        return next((meta.value for meta in self.shell.meta_lines if meta.key == "label"), None)

    def price_label(self) -> str:
        return next((meta.value for meta in self.shell.meta_lines if meta.key == "price"), "")

    def grammar_signature(self) -> tuple[str, str, str | None, str | None]:
        return (
            self.price_label(),
            self.availability_label(),
            self.recommendation_context_badge(),
            self.branch_hint(),
        )

    def _parts(self) -> list[str]:
        # Kept for compatibility with focused unit tests around compact grammar.
        parts = [self.shell.title, self.price_label(), self.availability_label()]
        badge = self.recommendation_context_badge()
        if badge:
            parts.append(badge)
        short_label = self.short_label()
        if short_label:
            parts.append(short_label)
        branch = self.branch_hint()
        if branch:
            parts.append(branch)
        return parts

    def object_block_lines(self, *, index: int) -> list[str]:
        lines = [f"{index}. {self.shell.title}"]
        if self.short_label():
            lines.append(f"   - {self.short_label()}")
        lines.append(f"   - {self.price_label()}")
        lines.append(f"   - {self.availability_label()}")
        badge = self.recommendation_context_badge()
        if badge:
            lines.append(f"   - {badge}")
        branch = self.branch_hint()
        if branch:
            lines.append(f"   - {branch}")
        return lines


def _compose_product_object_list_text(*, header_lines: list[str], row_cards: list[_CompactProductRowCard]) -> str:
    lines: list[str] = list(header_lines)
    if row_cards:
        lines.append("")
    for idx, row in enumerate(row_cards, start=1):
        lines.extend(row.object_block_lines(index=idx))
        if idx < len(row_cards):
            lines.append("")
    return "\n".join(lines)


@dataclass(slots=True)
class _ResolvedMediaRef:
    media_kind: str
    media_value: str


@dataclass(slots=True, frozen=True)
class _RepeatActionView:
    text: str
    choose_branch: bool = False
    branch_choices: tuple[str, ...] = ()
    created_order_id: str | None = None
    source_order_id: str | None = None


@dataclass(slots=True)
class _CompactCareOrderRowCard:
    care_order_id: str
    shell: Any

    def button_label(self) -> str:
        meta = {row.key: row.value for row in self.shell.meta_lines}
        parts = [self.shell.title, meta.get("item", ""), meta.get("branch", ""), meta.get("pickup", "")]
        parts = [part for part in parts if part]
        return " · ".join(parts)[:62]

    def reserve_label(self) -> str:
        action = next((item for item in self.shell.actions if item.action == CardAction.RESERVE), None)
        return action.label if action else ""

    def object_block_lines(self, *, index: int) -> list[str]:
        meta = {row.key: row.value for row in self.shell.meta_lines}
        lines = [f"{index}. {self.shell.title}"]
        item = meta.get("item")
        if item:
            lines.append(f"   - {item}")
        branch = meta.get("branch")
        if branch:
            lines.append(f"   - {branch}")
        status = self.shell.badges[0].text if self.shell.badges else None
        if status:
            lines.append(f"   - {status}")
        pickup = meta.get("pickup")
        if pickup:
            lines.append(f"   - {pickup}")
        return lines


def _compose_care_order_object_list_text(*, header_lines: list[str], row_cards: list[_CompactCareOrderRowCard]) -> str:
    lines: list[str] = list(header_lines)
    if row_cards:
        lines.append("")
    for idx, row in enumerate(row_cards, start=1):
        lines.extend(row.object_block_lines(index=idx))
        if idx < len(row_cards):
            lines.append("")
    return "\n".join(lines)


def _resolve_media_ref(media_ref: str) -> _ResolvedMediaRef | None:
    ref = (media_ref or "").strip()
    if not ref:
        return None
    lower = ref.lower()
    if lower.startswith("photo:"):
        value = ref.split(":", 1)[1].strip()
        return _ResolvedMediaRef(media_kind="photo", media_value=value) if value else None
    if lower.startswith("video:"):
        value = ref.split(":", 1)[1].strip()
        return _ResolvedMediaRef(media_kind="video", media_value=value) if value else None
    if lower.endswith((".mp4", ".mov", ".webm")):
        return _ResolvedMediaRef(media_kind="video", media_value=ref)
    return _ResolvedMediaRef(media_kind="photo", media_value=ref)


def _parse_gallery_index(page_or_index: str, *, total: int) -> int:
    if total < 1:
        return 0
    if ":" not in page_or_index:
        return 0
    _, raw_idx = page_or_index.split(":", 1)
    try:
        parsed = int(raw_idx or "0")
    except ValueError:
        return 0
    return min(max(parsed, 0), total - 1)


def _resolve_service_label(
    *,
    service_title_key: str | None,
    service_code: str | None,
    fallback_id: str | None,
    locale: str,
    fallback_locale: str,
    i18n: I18nService,
) -> str:
    if service_title_key:
        localized = i18n.t(service_title_key, locale)
        if localized and localized != service_title_key:
            return localized
        fallback_localized = i18n.t(service_title_key, fallback_locale)
        if fallback_localized and fallback_localized != service_title_key:
            return fallback_localized
    if service_code:
        return service_code
    if fallback_id:
        return fallback_id
    return i18n.t("patient.booking.review.value.missing", locale)


def _resolve_reference_label(*, display_name: str | None, fallback_id: str | None, locale: str, i18n: I18nService) -> str:
    name = (display_name or "").strip()
    if name:
        return name
    if fallback_id:
        return fallback_id
    return i18n.t("patient.booking.review.value.missing", locale)


def _resolve_status_label(*, status: str, locale: str, i18n: I18nService) -> str:
    key = f"booking.status.{status}"
    translated = i18n.t(key, locale)
    if translated and translated != key:
        return translated
    return status.replace("_", " ").strip().capitalize() or i18n.t("patient.booking.review.value.missing", locale)


def make_router(
    i18n: I18nService,
    booking_flow: BookingPatientFlowService,
    reference: ClinicReferenceService,
    reminder_actions: ReminderActionService,
    recommendation_service: RecommendationService | None = None,
    care_commerce_service: CareCommerceService | None = None,
    recommendation_repository=None,
    *,
    default_locale: str,
    card_runtime: CardRuntimeCoordinator | None = None,
    card_callback_codec: CardCallbackCodec | None = None,
) -> Router:
    router = Router(name="patient_router")
    if card_runtime is None:
        raise RuntimeError("patient router requires shared card runtime coordinator")
    if card_callback_codec is None:
        raise RuntimeError("patient router requires shared card callback codec")
    _SESSION_SCOPE = "patient_flow"
    booking_builder = BookingRuntimeViewBuilder()
    product_builder = ProductRuntimeViewBuilder()
    care_order_builder = CareOrderRuntimeViewBuilder()

    def _locale() -> str:
        return default_locale

    def _primary_clinic_id() -> str | None:
        clinics = list(reference.repository.clinics.values())
        return clinics[0].clinic_id if clinics else None

    def _fallback_locale_for_clinic(clinic_id: str | None) -> str:
        if clinic_id:
            clinic = reference.get_clinic(clinic_id)
            if clinic and clinic.default_locale:
                return clinic.default_locale
        return _locale()

    def _resolve_booking_timezone_name(*, clinic_id: str, branch_id: str | None) -> str:
        if branch_id:
            branch = reference.get_branch(clinic_id, branch_id)
            if branch and branch.timezone:
                return branch.timezone
        clinic = reference.get_clinic(clinic_id)
        if clinic and clinic.timezone:
            return clinic.timezone
        return "UTC"

    def _zone_or_utc(timezone_name: str) -> ZoneInfo:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    async def _load_flow_state(actor_id: int) -> _PatientFlowState:
        payload = await card_runtime.resolve_actor_session_state(scope=_SESSION_SCOPE, actor_id=actor_id)
        if payload is None:
            return _PatientFlowState(care=_CareViewState(selected_branch_by_product={}))
        care_payload = payload.get("care") or {}
        care_state = _CareViewState(
            selected_category=care_payload.get("selected_category"),
            category_page=int(care_payload.get("category_page", 0) or 0),
            recommendation_id=care_payload.get("recommendation_id"),
            recommendation_type=care_payload.get("recommendation_type"),
            recommendation_reason=care_payload.get("recommendation_reason"),
            recommendation_page=int(care_payload.get("recommendation_page", 0) or 0),
            recommendation_products=list(care_payload.get("recommendation_products") or []),
            recommendation_source_ref=care_payload.get("recommendation_source_ref"),
            selected_branch_by_product=dict(care_payload.get("selected_branch_by_product") or {}),
            product_page_by_category=dict(care_payload.get("product_page_by_category") or {}),
            media_product_id=care_payload.get("media_product_id"),
            media_index_by_product=dict(care_payload.get("media_index_by_product") or {}),
            media_return_mode_by_product=dict(care_payload.get("media_return_mode_by_product") or {}),
            care_order_page=int(care_payload.get("care_order_page", 0) or 0),
        )
        return _PatientFlowState(
            booking_session_id=payload.get("booking_session_id", ""),
            booking_mode=payload.get("booking_mode", "new_booking_contact"),
            care=care_state,
        )

    async def _save_flow_state(actor_id: int, state: _PatientFlowState) -> None:
        care_state = state.care or _CareViewState(selected_branch_by_product={})
        await card_runtime.bind_actor_session_state(
            scope=_SESSION_SCOPE,
            actor_id=actor_id,
            payload={
                "booking_session_id": state.booking_session_id,
                "booking_mode": state.booking_mode,
                "care": {
                    "selected_category": care_state.selected_category,
                    "category_page": care_state.category_page,
                    "recommendation_id": care_state.recommendation_id,
                    "recommendation_type": care_state.recommendation_type,
                    "recommendation_reason": care_state.recommendation_reason,
                    "recommendation_page": care_state.recommendation_page,
                    "recommendation_products": list(care_state.recommendation_products or []),
                    "recommendation_source_ref": care_state.recommendation_source_ref,
                    "selected_branch_by_product": dict(care_state.selected_branch_by_product or {}),
                    "product_page_by_category": dict(care_state.product_page_by_category or {}),
                    "media_product_id": care_state.media_product_id,
                    "media_index_by_product": dict(care_state.media_index_by_product or {}),
                    "media_return_mode_by_product": dict(care_state.media_return_mode_by_product or {}),
                    "care_order_page": care_state.care_order_page,
                },
            },
        )

    async def _care_state(actor_id: int) -> _CareViewState:
        state = await _load_flow_state(actor_id)
        current = state.care or _CareViewState(selected_branch_by_product={})
        if current.selected_branch_by_product is None:
            current.selected_branch_by_product = {}
        if current.product_page_by_category is None:
            current.product_page_by_category = {}
        if current.media_index_by_product is None:
            current.media_index_by_product = {}
        if current.media_return_mode_by_product is None:
            current.media_return_mode_by_product = {}
        if current.recommendation_products is None:
            current.recommendation_products = []
        state.care = current
        await _save_flow_state(actor_id, state)
        return current

    async def _encode_runtime_callback(
        *,
        profile: CardProfile,
        entity_type: EntityType,
        entity_id: str,
        action: CardAction,
        source_context: SourceContext,
        source_ref: str,
        page_or_index: str,
        state_token: str,
    ) -> str:
        return await card_callback_codec.encode(
            CardCallback(
                profile=profile,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                mode=CardMode.COMPACT,
                source_context=source_context,
                source_ref=source_ref,
                page_or_index=page_or_index,
                state_token=state_token,
            )
        )

    def _is_in_stock(row: Any) -> bool:
        return row is not None and row.status == "active" and row.free_qty > 0

    _LIST_PAGE_SIZE = 6

    def _page_slice(total: int, page: int, page_size: int = _LIST_PAGE_SIZE) -> tuple[int, int, int]:
        if total <= 0:
            return 0, 0, 0
        page_count = (total + page_size - 1) // page_size
        safe_page = min(max(page, 0), page_count - 1)
        start = safe_page * page_size
        end = min(start + page_size, total)
        return safe_page, start, end

    def _availability_label(row: Any, *, locale: str) -> str:
        if row is None or row.status != "active" or row.free_qty <= 0:
            return i18n.t("patient.care.availability.out", locale)
        if row.free_qty <= 2:
            return i18n.t("patient.care.availability.low", locale)
        return i18n.t("patient.care.availability.in", locale)

    async def _compact_product_row_card(
        *,
        clinic_id: str,
        actor_id: int,
        product: Any,
        locale: str,
        source_context: SourceContext,
        badge: str | None = None,
    ) -> _CompactProductRowCard:
        content = await care_commerce_service.resolve_product_content(
            clinic_id=clinic_id,
            product=product,
            locale=locale,
            fallback_locale=locale,
        )
        state = await _care_state(actor_id)
        branch_id = state.selected_branch_by_product.get(product.care_product_id) or await _resolve_preferred_branch_for_product(
            clinic_id=clinic_id,
            product_id=product.care_product_id,
        )
        availability = (
            await care_commerce_service.get_branch_product_availability(branch_id=branch_id, care_product_id=product.care_product_id)
            if branch_id
            else None
        )
        row_seed = product_builder.build_seed(
            snapshot=ProductRuntimeSnapshot(
                product_id=product.care_product_id,
                sku=content.short_label or product.sku,
                price_amount=product.price_amount,
                currency_code=product.currency_code,
                status=product.status,
                available_qty=(availability.free_qty if availability else 0),
                title_by_locale={locale: (content.title or i18n.t(product.title_key, locale))},
                category=await _category_label(category_code=product.category, locale=locale),
                selected_branch_label=(next((b.display_name for b in reference.list_branches(clinic_id) if b.branch_id == branch_id), None) if branch_id else None),
                recommendation_badge=(badge if source_context == SourceContext.RECOMMENDATION_DETAIL else None),
                state_token=f"care:{actor_id}",
            ),
            i18n=i18n,
            locale=locale,
        )
        row_shell = ProductCardAdapter.build(
            seed=row_seed,
            source=SourceRef(context=source_context, source_ref="care.product.row"),
            i18n=i18n,
            locale=locale,
            mode=CardMode.LIST_ROW,
        )
        return _CompactProductRowCard(
            product_id=product.care_product_id,
            shell=row_shell,
        )

    async def _category_label(*, category_code: str, locale: str) -> str:
        key = f"care.category.{category_code}"
        resolved = i18n.t(key, locale)
        if resolved != key:
            return resolved
        return category_code.replace("_", " ").replace("-", " ").strip().title()

    async def _resolve_preferred_branch_for_product(*, clinic_id: str, product_id: str) -> str | None:
        if care_commerce_service is None:
            return None
        branches = reference.list_branches(clinic_id)
        picker_rows: list[tuple[Any, Any]] = []
        for branch in branches:
            availability = await care_commerce_service.get_branch_product_availability(branch_id=branch.branch_id, care_product_id=product_id)
            picker_rows.append((branch, availability))
        setting_branch = await care_commerce_service.repository.get_catalog_setting(clinic_id=clinic_id, key="care.default_pickup_branch_id")
        if setting_branch:
            preferred = next((x for x in picker_rows if x[0].branch_id == setting_branch and _is_in_stock(x[1])), None)
            if preferred:
                return preferred[0].branch_id
        in_stock = [branch.branch_id for branch, availability in picker_rows if _is_in_stock(availability)]
        return in_stock[0] if in_stock else None

    async def _render_care_categories_panel(message: Message | CallbackQuery, *, actor_id: int, clinic_id: str, page: int | None = None) -> None:
        locale = _locale()
        categories = await care_commerce_service.list_catalog_categories(clinic_id=clinic_id)
        if not categories:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="care",
                text=i18n.t("patient.care.catalog.empty", locale),
            )
            return
        state = await _care_state(actor_id)
        active_page, start, end = _page_slice(len(categories), state.category_page if page is None else page)
        state.category_page = active_page
        flow = await _load_flow_state(actor_id)
        flow.care = state
        await _save_flow_state(actor_id, flow)
        rows: list[list[InlineKeyboardButton]] = []
        for category in categories[start:end]:
            callback_data = await _encode_runtime_callback(
                profile=CardProfile.PRODUCT,
                entity_type=EntityType.CARE_PRODUCT,
                entity_id=category,
                action=CardAction.OPEN,
                source_context=SourceContext.CARE_CATALOG_CATEGORY,
                source_ref="care.catalog.category",
                page_or_index="cat",
                state_token=f"care:{actor_id}",
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        text=await _category_label(category_code=category, locale=locale),
                        callback_data=callback_data,
                    )
                ]
            )
        nav_row: list[InlineKeyboardButton] = []
        if active_page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    text=i18n.t("common.prev", locale),
                    callback_data=await _encode_runtime_callback(
                        profile=CardProfile.PRODUCT,
                        entity_type=EntityType.CARE_PRODUCT,
                        entity_id="categories",
                        action=CardAction.OPEN,
                        source_context=SourceContext.CARE_CATALOG_CATEGORY,
                        source_ref="care.catalog.category.page",
                        page_or_index=f"cat_page:{active_page - 1}",
                        state_token=f"care:{actor_id}",
                    ),
                )
            )
        if end < len(categories):
            nav_row.append(
                InlineKeyboardButton(
                    text=i18n.t("common.next", locale),
                    callback_data=await _encode_runtime_callback(
                        profile=CardProfile.PRODUCT,
                        entity_type=EntityType.CARE_PRODUCT,
                        entity_id="categories",
                        action=CardAction.OPEN,
                        source_context=SourceContext.CARE_CATALOG_CATEGORY,
                        source_ref="care.catalog.category.page",
                        page_or_index=f"cat_page:{active_page + 1}",
                        state_token=f"care:{actor_id}",
                    ),
                )
            )
        if nav_row:
            rows.append(nav_row)
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=i18n.t("patient.care.catalog.title_page", locale).format(page=active_page + 1),
            keyboard=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    async def _render_care_product_list(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        clinic_id: str,
        category: str,
        page: int | None = None,
    ) -> None:
        locale = _locale()
        products = await care_commerce_service.list_catalog_products_by_category(clinic_id=clinic_id, category=category)
        if not products:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="care",
                text=i18n.t("patient.care.catalog.category.empty", locale),
                keyboard=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=i18n.t("common.back", locale),
                                callback_data=await _encode_runtime_callback(
                                    profile=CardProfile.PRODUCT,
                                    entity_type=EntityType.CARE_PRODUCT,
                                    entity_id="categories",
                                    action=CardAction.BACK,
                                    source_context=SourceContext.CARE_CATALOG_CATEGORY,
                                    source_ref="care.catalog.back",
                                    page_or_index="back_categories",
                                    state_token=f"care:{actor_id}",
                                ),
                            )
                        ]
                    ]
                ),
            )
            return
        state = await _care_state(actor_id)
        page_map = state.product_page_by_category or {}
        active_page, start, end = _page_slice(len(products), page_map.get(category, 0) if page is None else page)
        page_map[category] = active_page
        state.product_page_by_category = page_map
        header_lines = [
            i18n.t("patient.care.catalog.products.title", locale).format(
                category=await _category_label(category_code=category, locale=locale)
            )
        ]
        header_lines.append(i18n.t("patient.care.catalog.page_indicator", locale).format(page=active_page + 1))
        rows: list[list[InlineKeyboardButton]] = []
        row_cards: list[_CompactProductRowCard] = []
        for product in products[start:end]:
            row_cards.append(
                await _compact_product_row_card(
                    clinic_id=clinic_id,
                    actor_id=actor_id,
                    product=product,
                    locale=locale,
                    source_context=SourceContext.CARE_CATALOG_CATEGORY,
                )
            )
        for idx, item in enumerate(row_cards, start=1):
            if not item.supports_open_action():
                continue
            rows.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.care.products.open.indexed", locale).format(index=idx),
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.PRODUCT,
                            entity_type=EntityType.CARE_PRODUCT,
                            entity_id=item.product_id,
                            action=CardAction.OPEN,
                            source_context=SourceContext.CARE_CATALOG_CATEGORY,
                            source_ref=item.open_source_ref("care.product.open"),
                            page_or_index="product",
                            state_token=f"care:{actor_id}",
                        ),
                    )
                ]
            )
        nav_row: list[InlineKeyboardButton] = []
        if active_page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    text=i18n.t("common.prev", locale),
                    callback_data=await _encode_runtime_callback(
                        profile=CardProfile.PRODUCT,
                        entity_type=EntityType.CARE_PRODUCT,
                        entity_id=category,
                        action=CardAction.OPEN,
                        source_context=SourceContext.CARE_CATALOG_CATEGORY,
                        source_ref="care.catalog.products.page",
                        page_or_index=f"products_page:{active_page - 1}",
                        state_token=f"care:{actor_id}",
                    ),
                )
            )
        if end < len(products):
            nav_row.append(
                InlineKeyboardButton(
                    text=i18n.t("common.next", locale),
                    callback_data=await _encode_runtime_callback(
                        profile=CardProfile.PRODUCT,
                        entity_type=EntityType.CARE_PRODUCT,
                        entity_id=category,
                        action=CardAction.OPEN,
                        source_context=SourceContext.CARE_CATALOG_CATEGORY,
                        source_ref="care.catalog.products.page",
                        page_or_index=f"products_page:{active_page + 1}",
                        state_token=f"care:{actor_id}",
                    ),
                )
            )
        if nav_row:
            rows.append(nav_row)
        rows.append(
            [
                InlineKeyboardButton(
                    text=i18n.t("common.back", locale),
                    callback_data=await _encode_runtime_callback(
                        profile=CardProfile.PRODUCT,
                        entity_type=EntityType.CARE_PRODUCT,
                        entity_id="categories",
                        action=CardAction.BACK,
                        source_context=SourceContext.CARE_CATALOG_CATEGORY,
                        source_ref="care.catalog.back",
                        page_or_index="back_categories",
                        state_token=f"care:{actor_id}",
                    ),
                )
            ]
        )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=_compose_product_object_list_text(header_lines=header_lines, row_cards=row_cards),
            keyboard=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        flow = await _load_flow_state(actor_id)
        flow.care = state
        await _save_flow_state(actor_id, flow)

    async def _render_product_card(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        clinic_id: str,
        product_id: str,
        mode: CardMode = CardMode.COMPACT,
        source_context: SourceContext | None = None,
    ) -> None:
        locale = _locale()
        if care_commerce_service is None:
            return
        product = await care_commerce_service.repository.get_product(product_id)
        if product is None or product.status != "active":
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id="care", text=i18n.t("patient.care.product.missing", locale))
            return
        state = await _care_state(actor_id)
        content = await care_commerce_service.resolve_product_content(clinic_id=clinic_id, product=product, locale=locale, fallback_locale=locale)
        media_refs = tuple(content.media_refs)
        branch_id = state.selected_branch_by_product.get(product_id) or await _resolve_preferred_branch_for_product(clinic_id=clinic_id, product_id=product_id)
        if branch_id:
            state.selected_branch_by_product[product_id] = branch_id
            flow = await _load_flow_state(actor_id)
            flow.care = state
            await _save_flow_state(actor_id, flow)
        availability = await care_commerce_service.get_branch_product_availability(branch_id=branch_id, care_product_id=product_id) if branch_id else None
        branch = next((b for b in reference.list_branches(clinic_id) if b.branch_id == branch_id), None)
        state_source = source_context or (
            SourceContext.RECOMMENDATION_DETAIL if state.recommendation_id else SourceContext.CARE_CATALOG_CATEGORY
        )
        seed = product_builder.build_seed(
            snapshot=ProductRuntimeSnapshot(
                product_id=product.care_product_id,
                sku=content.short_label or product.sku,
                price_amount=product.price_amount,
                currency_code=product.currency_code,
                status=product.status,
                available_qty=(availability.free_qty if availability else 0),
                title_by_locale={locale: (content.title or i18n.t(product.title_key, locale))},
                description_by_locale={locale: (content.description or i18n.t("patient.care.product.description.empty", locale))},
                usage_hint=content.usage_hint,
                category=await _category_label(category_code=product.category, locale=locale),
                selected_branch_label=(branch.display_name if branch else i18n.t("patient.care.product.branch.none", locale)),
                recommendation_badge=(i18n.t("patient.care.products.title", locale) if state.recommendation_id else None),
                recommendation_rationale=(state.recommendation_reason[:180] if state.recommendation_reason else None),
                media_count=len(media_refs),
                state_token=f"care:{actor_id}",
            ),
            i18n=i18n,
            locale=locale,
        )
        shell = ProductCardAdapter.build(
            seed=seed,
            source=SourceRef(context=state_source, source_ref="care.product"),
            i18n=i18n,
            locale=locale,
            mode=mode,
        )
        action_mapping: dict[CardAction, tuple[str, str]] = {
            CardAction.EXPAND: ("expand", "care.product.expand"),
            CardAction.COLLAPSE: ("collapse", "care.product.collapse"),
            CardAction.RESERVE: ("reserve", "care.product.reserve"),
            CardAction.CHANGE_BRANCH: ("branch", "care.product.branch"),
            CardAction.COVER: ("cover", "care.product.cover"),
            CardAction.GALLERY: ("gallery", "care.product.gallery"),
            CardAction.BACK: ("back_products", "care.product.back"),
        }
        rows: list[list[InlineKeyboardButton]] = []
        for action in shell.actions:
            mapped = action_mapping.get(action.action)
            if mapped is None:
                continue
            page_or_index, source_ref = mapped
            rows.append(
                [
                    InlineKeyboardButton(
                        text=action.label,
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.PRODUCT,
                            entity_type=EntityType.CARE_PRODUCT,
                            entity_id=state.selected_category if action.action == CardAction.BACK and state.selected_category else product_id,
                            action=action.action,
                            source_context=state_source,
                            source_ref=source_ref,
                            page_or_index=page_or_index,
                            state_token=f"care:{actor_id}",
                        ),
                    )
                ]
            )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=CardShellRenderer.to_panel(shell).text,
            keyboard=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    async def _render_branch_picker(message: Message | CallbackQuery, *, actor_id: int, clinic_id: str, product_id: str) -> None:
        locale = _locale()
        if care_commerce_service is None:
            return
        branches = reference.list_branches(clinic_id)
        rows: list[list[InlineKeyboardButton]] = []
        for branch in branches[:10]:
            availability = await care_commerce_service.get_branch_product_availability(branch_id=branch.branch_id, care_product_id=product_id)
            label = i18n.t("patient.care.branch.option", locale).format(branch=branch.display_name, status=_availability_label(availability, locale=locale))
            rows.append(
                [
                    InlineKeyboardButton(
                        text=label[:62],
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.PRODUCT,
                            entity_type=EntityType.CARE_PRODUCT,
                            entity_id=product_id,
                            action=CardAction.CHANGE_BRANCH,
                            source_context=SourceContext.CARE_CATALOG_CATEGORY,
                            source_ref=f"care.branch.select:{branch.branch_id}",
                            page_or_index="branch_select",
                            state_token=f"care:{actor_id}",
                        ),
                    )
                ]
            )
        rows.append(
            [
                InlineKeyboardButton(
                    text=i18n.t("common.back", locale),
                    callback_data=await _encode_runtime_callback(
                        profile=CardProfile.PRODUCT,
                        entity_type=EntityType.CARE_PRODUCT,
                        entity_id=product_id,
                        action=CardAction.BACK,
                        source_context=SourceContext.CARE_CATALOG_CATEGORY,
                        source_ref="care.branch.back",
                        page_or_index="back_product",
                        state_token=f"care:{actor_id}",
                    ),
                )
            ]
        )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=i18n.t("patient.care.branch.prompt", locale),
            keyboard=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    async def _reserve_product(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        clinic_id: str,
        patient_id: str,
        product_id: str,
        recommendation_id: str | None,
    ) -> None:
        locale = _locale()
        if care_commerce_service is None:
            return
        product = await care_commerce_service.repository.get_product(product_id)
        if product is None or product.status != "active":
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id="care", text=i18n.t("patient.care.product.missing", locale))
            return
        state = await _care_state(actor_id)
        branch_id = state.selected_branch_by_product.get(product_id) or await _resolve_preferred_branch_for_product(clinic_id=clinic_id, product_id=product_id)
        if not branch_id:
            await _render_branch_picker(message, actor_id=actor_id, clinic_id=clinic_id, product_id=product_id)
            return
        free_qty = await care_commerce_service.compute_free_qty(branch_id=branch_id, care_product_id=product_id)
        if free_qty < 1:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="care",
                text=i18n.t("patient.care.order.out_of_stock", locale).format(branch_id=branch_id, title=i18n.t(product.title_key, locale)),
                keyboard=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=i18n.t("patient.care.product.change_branch", locale),
                                callback_data=await _encode_runtime_callback(
                                    profile=CardProfile.PRODUCT,
                                    entity_type=EntityType.CARE_PRODUCT,
                                    entity_id=product_id,
                                    action=CardAction.CHANGE_BRANCH,
                                    source_context=SourceContext.CARE_CATALOG_CATEGORY,
                                    source_ref="care.product.branch",
                                    page_or_index="branch",
                                    state_token=f"care:{actor_id}",
                                ),
                            )
                        ]
                    ]
                ),
            )
            return
        order = await care_commerce_service.create_order(
            clinic_id=clinic_id,
            patient_id=patient_id,
            payment_mode="pay_at_pickup",
            currency_code=product.currency_code,
            pickup_branch_id=branch_id,
            recommendation_id=recommendation_id,
            booking_id=None,
            items=[(product, 1)],
        )
        await care_commerce_service.transition_order(care_order_id=order.care_order_id, to_status="confirmed")
        reservation = await care_commerce_service.create_reservation(
            care_order_id=order.care_order_id,
            care_product_id=product.care_product_id,
            branch_id=branch_id,
            reserved_qty=1,
        )
        next_step = i18n.t("patient.care.order.next_step", locale)
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=i18n.t("patient.care.order.result", locale).format(
                product=i18n.t(product.title_key, locale),
                branch_id=branch_id,
                status="confirmed",
                reservation_status=reservation.status,
                care_order_id=order.care_order_id,
                next_step=next_step,
            ),
        )

    async def _send_or_edit_panel(
        *,
        actor_id: int,
        message: Message | CallbackQuery,
        text: str,
        keyboard: InlineKeyboardMarkup | None = None,
        session_id: str,
        reply_keyboard: ReplyKeyboardMarkup | None = None,
    ) -> None:
        panel_family = PanelFamily.PATIENT_CATALOG if session_id == "care" else PanelFamily.BOOKING_DETAIL
        source_context = SourceContext.CARE_CATALOG_CATEGORY if session_id == "care" else SourceContext.BOOKING_LIST
        state_token = session_id or f"actor:{actor_id}"
        state = await card_runtime.resolve_active_panel(actor_id=actor_id, panel_family=panel_family)
        if isinstance(message, CallbackQuery):
            current_message = message.message
            if current_message:
                if state is not None and state.message_id != current_message.message_id:
                    await message.answer(i18n.t("common.card.callback.stale", _locale()), show_alert=True)
                    return
                await current_message.edit_text(text=text, reply_markup=keyboard)
                await card_runtime.bind_panel(
                    actor_id=actor_id,
                    chat_id=current_message.chat.id,
                    message_id=current_message.message_id,
                    panel_family=panel_family,
                    profile=None,
                    entity_id=session_id or None,
                    source_context=source_context,
                    source_ref=session_id,
                    page_or_index=session_id,
                    state_token=state_token,
                )
            await message.answer()
            return
        if state:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=state.message_id,
                    text=text,
                    reply_markup=keyboard,
                )
                await card_runtime.bind_panel(
                    actor_id=actor_id,
                    chat_id=message.chat.id,
                    message_id=state.message_id,
                    panel_family=panel_family,
                    profile=None,
                    entity_id=session_id or None,
                    source_context=source_context,
                    source_ref=session_id,
                    page_or_index=session_id,
                    state_token=state_token,
                )
                return
            except Exception:
                pass
        sent = await message.answer(text, reply_markup=reply_keyboard or keyboard)
        await card_runtime.bind_panel(
            actor_id=actor_id,
            chat_id=sent.chat.id,
            message_id=sent.message_id,
            panel_family=panel_family,
            profile=None,
            entity_id=session_id or None,
            source_context=source_context,
            source_ref=session_id,
            page_or_index=session_id,
            state_token=state_token,
        )

    async def _send_media_panel(
        *,
        actor_id: int,
        message: Message | CallbackQuery,
        caption: str,
        media_ref: str,
        keyboard: InlineKeyboardMarkup,
    ) -> bool:
        resolved = _resolve_media_ref(media_ref)
        if resolved is None:
            return False
        try:
            if isinstance(message, CallbackQuery):
                if message.message is None:
                    return False
                bot = message.bot
                chat_id = message.message.chat.id
            else:
                bot = message.bot
                chat_id = message.chat.id
            if resolved.media_kind == "video":
                sent = await bot.send_video(chat_id=chat_id, video=resolved.media_value, caption=caption, reply_markup=keyboard)
            else:
                sent = await bot.send_photo(chat_id=chat_id, photo=resolved.media_value, caption=caption, reply_markup=keyboard)
            await card_runtime.bind_panel(
                actor_id=actor_id,
                chat_id=sent.chat.id,
                message_id=sent.message_id,
                panel_family=PanelFamily.PATIENT_CATALOG,
                profile=None,
                entity_id="care",
                source_context=SourceContext.CARE_CATALOG_CATEGORY,
                source_ref="care.product.media",
                page_or_index="media",
                state_token="care",
            )
            return True
        except Exception:
            return False

    async def _reserve_again_from_order(
        *,
        clinic_id: str,
        patient_id: str,
        care_order_id: str,
        selected_branch_id: str | None = None,
    ) -> _RepeatActionView:
        locale = _locale()
        candidate_branch_ids = tuple(branch.branch_id for branch in reference.list_branches(clinic_id))
        outcome = await care_commerce_service.repeat_order_as_new(
            clinic_id=clinic_id,
            patient_id=patient_id,
            source_order_id=care_order_id,
            requested_branch_id=selected_branch_id,
            allowed_branch_ids=candidate_branch_ids,
        )
        if outcome.ok and outcome.created_order and outcome.selected_branch_id:
            product_name = "-"
            if outcome.product is not None:
                content = await care_commerce_service.resolve_product_content(
                    clinic_id=clinic_id,
                    product=outcome.product,
                    locale=locale,
                    fallback_locale=locale,
                )
                product_name = content.title or i18n.t(outcome.product.title_key, locale)
            quantity = outcome.source_item.quantity if outcome.source_item is not None else 1
            return _RepeatActionView(
                text=i18n.t("patient.care.orders.repeat.result", locale).format(
                    care_order_id=outcome.created_order.care_order_id,
                    product=product_name,
                    quantity=quantity,
                    branch_id=outcome.selected_branch_id,
                    status=i18n.t(f"care.order.status.{outcome.created_order.status}", locale),
                    next_step=i18n.t("patient.care.orders.repeat.next_step", locale),
                ),
                created_order_id=outcome.created_order.care_order_id,
                source_order_id=care_order_id,
            )
        if outcome.reason in {"source_not_found", "source_empty"}:
            return _RepeatActionView(text=i18n.t("patient.care.orders.repeat.not_found", locale))
        if outcome.reason == "product_unavailable":
            return _RepeatActionView(text=i18n.t("patient.care.orders.repeat.unavailable", locale))
        if outcome.reason in {"branch_selection_required", "branch_required"} and outcome.available_branch_ids:
            return _RepeatActionView(
                text=i18n.t("patient.care.orders.repeat.branch_select_required", locale),
                choose_branch=True,
                branch_choices=outcome.available_branch_ids,
            )
        if outcome.reason == "branch_invalid":
            if outcome.available_branch_ids:
                return _RepeatActionView(
                    text=i18n.t("patient.care.orders.repeat.branch_changed", locale),
                    choose_branch=True,
                    branch_choices=outcome.available_branch_ids,
                )
            return _RepeatActionView(text=i18n.t("patient.care.orders.repeat.branch_required", locale))
        if outcome.reason in {"availability_inactive", "insufficient_stock", "branch_unavailable"}:
            if outcome.selected_branch_id:
                message = i18n.t("patient.care.orders.repeat.out_of_stock", locale).format(branch_id=outcome.selected_branch_id)
            else:
                message = i18n.t("patient.care.orders.repeat.branch_required", locale)
            if outcome.available_branch_ids:
                message = f"{message}\n{i18n.t('patient.care.orders.repeat.branch_select_required', locale)}"
                return _RepeatActionView(text=message, choose_branch=True, branch_choices=outcome.available_branch_ids)
            return _RepeatActionView(text=message)
        return _RepeatActionView(text=i18n.t("patient.care.orders.repeat.branch_required", locale))

    async def _repeat_action_keyboard(*, actor_id: int, care_order_id: str, view: _RepeatActionView) -> InlineKeyboardMarkup | None:
        rows: list[list[InlineKeyboardButton]] = []
        if view.choose_branch and view.branch_choices:
            for branch_id in view.branch_choices:
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=i18n.t("patient.care.orders.repeat.branch_option", _locale()).format(branch_id=branch_id),
                            callback_data=await _encode_runtime_callback(
                                profile=CardProfile.CARE_ORDER,
                                entity_type=EntityType.CARE_ORDER,
                                entity_id=care_order_id,
                                action=CardAction.CHANGE_BRANCH,
                                source_context=SourceContext.CARE_ORDER_LIST,
                                source_ref="care.orders.repeat.branch",
                                page_or_index=f"repeat_branch:{branch_id}",
                                state_token=f"care:{actor_id}",
                            ),
                        )
                    ]
                )
        if view.created_order_id:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.care.orders.repeat.open_new", _locale()),
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.CARE_ORDER,
                            entity_type=EntityType.CARE_ORDER,
                            entity_id=view.created_order_id,
                            action=CardAction.OPEN,
                            source_context=SourceContext.CARE_ORDER_LIST,
                            source_ref="care.orders.repeat.result.open_new",
                            page_or_index="open",
                            state_token=f"care:{actor_id}",
                        ),
                    )
                ]
            )
        rows.append(
            [
                InlineKeyboardButton(
                    text=i18n.t("patient.care.orders.repeat.back_to_orders", _locale()),
                    callback_data=await _encode_runtime_callback(
                        profile=CardProfile.CARE_ORDER,
                        entity_type=EntityType.CARE_ORDER,
                        entity_id=care_order_id,
                        action=CardAction.BACK,
                        source_context=SourceContext.CARE_ORDER_LIST,
                        source_ref="care.orders.repeat.result.back",
                        page_or_index="back_orders",
                        state_token=f"care:{actor_id}",
                    ),
                )
            ]
        )
        return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

    async def _build_care_order_row_card(*, clinic_id: str, actor_id: int, order: Any, locale: str) -> _CompactCareOrderRowCard:
        items = await care_commerce_service.repository.list_order_items(order.care_order_id)
        item_summary = "-"
        reservation_hint = None
        pickup_ready = order.status in {"ready_for_pickup", "issued", "fulfilled"}
        if items:
            first = items[0]
            product = await care_commerce_service.repository.get_product(first.care_product_id)
            title = "-"
            if product is not None:
                content = await care_commerce_service.resolve_product_content(
                    clinic_id=clinic_id,
                    product=product,
                    locale=locale,
                    fallback_locale=locale,
                )
                title = content.title or i18n.t(product.title_key, locale)
            suffix = ""
            if len(items) > 1:
                suffix = f" +{len(items) - 1}"
            item_summary = f"{title} x{first.quantity}{suffix}"
            if order.pickup_branch_id:
                row = await care_commerce_service.get_branch_product_availability(
                    branch_id=order.pickup_branch_id,
                    care_product_id=first.care_product_id,
                )
                if row is not None and row.status == "active" and row.free_qty >= first.quantity:
                    reservation_hint = i18n.t("patient.care.orders.repeat.availability_ok", locale).format(branch_id=order.pickup_branch_id)
                else:
                    reservation_hint = i18n.t("patient.care.orders.repeat.out_of_stock", locale).format(branch_id=order.pickup_branch_id)
        branch_label = order.pickup_branch_id or "-"
        seed = care_order_builder.build_seed(
            snapshot=CareOrderRuntimeSnapshot(
                care_order_id=order.care_order_id,
                status=order.status,
                total_amount=order.total_amount,
                currency_code=order.currency_code,
                item_summary=item_summary,
                branch_label=branch_label,
                pickup_ready=pickup_ready,
                reservation_hint=reservation_hint,
                issued=order.status in {"issued", "fulfilled"},
                fulfilled=order.status == "fulfilled",
                state_token=f"care:{actor_id}",
            ),
            i18n=i18n,
            locale=locale,
        )
        shell = CareOrderCardAdapter.build(
            seed=seed,
            source=SourceRef(context=SourceContext.CARE_ORDER_LIST, source_ref="care.orders.row"),
            i18n=i18n,
            locale=locale,
            mode=CardMode.LIST_ROW,
        )
        return _CompactCareOrderRowCard(care_order_id=order.care_order_id, shell=shell)

    async def _render_care_orders_panel(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        clinic_id: str,
        patient_id: str,
        page: int | None = None,
    ) -> None:
        locale = _locale()
        rows = await care_commerce_service.list_patient_orders(clinic_id=clinic_id, patient_id=patient_id)
        if not rows:
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id="care", text=i18n.t("patient.care.orders.empty", locale))
            return
        state = await _care_state(actor_id)
        active_page, start, end = _page_slice(len(rows), state.care_order_page if page is None else page)
        state.care_order_page = active_page
        flow = await _load_flow_state(actor_id)
        flow.care = state
        await _save_flow_state(actor_id, flow)
        compact_rows: list[_CompactCareOrderRowCard] = []
        for order in rows[start:end]:
            compact_rows.append(await _build_care_order_row_card(clinic_id=clinic_id, actor_id=actor_id, order=order, locale=locale))
        keyboard_rows: list[list[InlineKeyboardButton]] = []
        for row_card in compact_rows:
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text=row_card.button_label(),
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.CARE_ORDER,
                            entity_type=EntityType.CARE_ORDER,
                            entity_id=row_card.care_order_id,
                            action=CardAction.OPEN,
                            source_context=SourceContext.CARE_ORDER_LIST,
                            source_ref="care.orders.list.open",
                            page_or_index="open",
                            state_token=f"care:{actor_id}",
                        ),
                    ),
                    InlineKeyboardButton(
                        text=row_card.reserve_label(),
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.CARE_ORDER,
                            entity_type=EntityType.CARE_ORDER,
                            entity_id=row_card.care_order_id,
                            action=CardAction.RESERVE,
                            source_context=SourceContext.CARE_ORDER_LIST,
                            source_ref="care.orders.list.repeat",
                            page_or_index="repeat",
                            state_token=f"care:{actor_id}",
                        ),
                    ),
                ]
            )
        nav: list[InlineKeyboardButton] = []
        if active_page > 0:
            nav.append(
                InlineKeyboardButton(
                    text=i18n.t("common.prev", locale),
                    callback_data=await _encode_runtime_callback(
                        profile=CardProfile.CARE_ORDER,
                        entity_type=EntityType.CARE_ORDER,
                        entity_id="orders",
                        action=CardAction.OPEN,
                        source_context=SourceContext.CARE_ORDER_LIST,
                        source_ref="care.orders.list.page",
                        page_or_index=f"orders_page:{active_page - 1}",
                        state_token=f"care:{actor_id}",
                    ),
                )
            )
        if end < len(rows):
            nav.append(
                InlineKeyboardButton(
                    text=i18n.t("common.next", locale),
                    callback_data=await _encode_runtime_callback(
                        profile=CardProfile.CARE_ORDER,
                        entity_type=EntityType.CARE_ORDER,
                        entity_id="orders",
                        action=CardAction.OPEN,
                        source_context=SourceContext.CARE_ORDER_LIST,
                        source_ref="care.orders.list.page",
                        page_or_index=f"orders_page:{active_page + 1}",
                        state_token=f"care:{actor_id}",
                    ),
                )
            )
        if nav:
            keyboard_rows.append(nav)
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=_compose_care_order_object_list_text(
                header_lines=[
                    i18n.t("patient.care.orders.title", locale),
                    i18n.t("patient.care.catalog.page_indicator", locale).format(page=active_page + 1),
                ],
                row_cards=compact_rows,
            ),
            keyboard=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        )

    async def _render_care_order_card(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        clinic_id: str,
        patient_id: str,
        care_order_id: str,
        mode: CardMode = CardMode.COMPACT,
    ) -> None:
        locale = _locale()
        order = await care_commerce_service.get_order(care_order_id)
        if order is None or order.patient_id != patient_id:
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id="care", text=i18n.t("patient.care.orders.repeat.not_found", locale))
            return
        row_card = await _build_care_order_row_card(clinic_id=clinic_id, actor_id=actor_id, order=order, locale=locale)
        reservation_hint = None
        items = await care_commerce_service.repository.list_order_items(order.care_order_id)
        if items and order.pickup_branch_id:
            availability = await care_commerce_service.get_branch_product_availability(
                branch_id=order.pickup_branch_id,
                care_product_id=items[0].care_product_id,
            )
            if availability is not None and availability.status == "active" and availability.free_qty >= items[0].quantity:
                reservation_hint = i18n.t("patient.care.orders.repeat.availability_ok", locale).format(branch_id=order.pickup_branch_id)
            else:
                reservation_hint = i18n.t("patient.care.orders.repeat.out_of_stock", locale).format(branch_id=order.pickup_branch_id)
        shell = CareOrderCardAdapter.build(
            seed=care_order_builder.build_seed(
                snapshot=CareOrderRuntimeSnapshot(
                    care_order_id=order.care_order_id,
                    status=order.status,
                    total_amount=order.total_amount,
                    currency_code=order.currency_code,
                    item_summary=next((meta.value for meta in row_card.shell.meta_lines if meta.key == "item"), "-"),
                    branch_label=order.pickup_branch_id or "-",
                    pickup_ready=order.status in {"ready_for_pickup", "issued", "fulfilled"},
                    reservation_hint=reservation_hint,
                    issued=order.status in {"issued", "fulfilled"},
                    fulfilled=order.status == "fulfilled",
                    state_token=f"care:{actor_id}",
                ),
                i18n=i18n,
                locale=locale,
            ),
            source=SourceRef(context=SourceContext.CARE_ORDER_LIST, source_ref="care.orders.object"),
            i18n=i18n,
            locale=locale,
            mode=mode,
        )
        action_map: dict[CardAction, tuple[str, str]] = {
            CardAction.EXPAND: ("open_expand", "care.orders.object.expand"),
            CardAction.COLLAPSE: ("open", "care.orders.object.collapse"),
            CardAction.RESERVE: ("repeat", "care.orders.object.repeat"),
            CardAction.BACK: ("back_orders", "care.orders.object.back"),
        }
        buttons: list[list[InlineKeyboardButton]] = []
        for action in shell.actions:
            mapped = action_map.get(action.action)
            if mapped is None:
                continue
            page_or_index, source_ref = mapped
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=action.label,
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.CARE_ORDER,
                            entity_type=EntityType.CARE_ORDER,
                            entity_id=order.care_order_id,
                            action=action.action,
                            source_context=SourceContext.CARE_ORDER_LIST,
                            source_ref=source_ref,
                            page_or_index=page_or_index,
                            state_token=f"care:{actor_id}",
                        ),
                    )
                ]
            )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=CardShellRenderer.to_panel(shell).text,
            keyboard=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

    async def _render_service_panel(message: Message | CallbackQuery, *, actor_id: int, session_id: str, clinic_id: str) -> None:
        locale = _locale()
        services = booking_flow.list_services(clinic_id=clinic_id)
        buttons = [[InlineKeyboardButton(text=svc.code, callback_data=f"book:svc:{session_id}:{svc.service_id}")] for svc in services[:8]]
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=i18n.t("patient.booking.service.prompt", locale),
            keyboard=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

    async def _render_recommendation_picker(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        clinic_id: str,
        recommendation_id: str,
        source_context: SourceContext = SourceContext.RECOMMENDATION_DETAIL,
        page: int | None = None,
    ) -> None:
        state = await _care_state(actor_id)
        if not state.recommendation_products:
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id="care", text=i18n.t("patient.care.products.empty", _locale()))
            return
        locale = _locale()
        rows_products: list[_CompactProductRowCard] = []
        for product_id in state.recommendation_products:
            product = await care_commerce_service.repository.get_product(product_id)
            if product is None or product.status != "active":
                continue
            rows_products.append(
                await _compact_product_row_card(
                    clinic_id=clinic_id,
                    actor_id=actor_id,
                    product=product,
                    locale=locale,
                    source_context=SourceContext.RECOMMENDATION_DETAIL,
                    badge=i18n.t("patient.care.products.badge", locale),
                )
            )
        if not rows_products:
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id="care", text=i18n.t("patient.care.products.empty", locale))
            return
        active_page, start, end = _page_slice(len(rows_products), state.recommendation_page if page is None else page)
        state.recommendation_page = active_page
        header_lines = [i18n.t("patient.care.products.title", locale), i18n.t("patient.care.catalog.page_indicator", locale).format(page=active_page + 1)]
        if state.recommendation_reason:
            header_lines.append(state.recommendation_reason.strip()[:180])
        buttons: list[list[InlineKeyboardButton]] = []
        page_rows = rows_products[start:end]
        for idx, item in enumerate(page_rows, start=1):
            if not item.supports_open_action():
                continue
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.care.products.open.indexed", locale).format(index=idx),
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.PRODUCT,
                            entity_type=EntityType.CARE_PRODUCT,
                            entity_id=item.product_id,
                            action=CardAction.OPEN,
                            source_context=source_context,
                            source_ref=item.open_source_ref(state.recommendation_source_ref or f"care.recommendation.{recommendation_id}"),
                            page_or_index="product",
                            state_token=f"care:{actor_id}",
                        ),
                    )
                ]
            )
        nav_row: list[InlineKeyboardButton] = []
        if active_page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    text=i18n.t("common.prev", locale),
                    callback_data=await _encode_runtime_callback(
                        profile=CardProfile.PRODUCT,
                        entity_type=EntityType.CARE_PRODUCT,
                        entity_id=recommendation_id,
                        action=CardAction.OPEN,
                        source_context=SourceContext.RECOMMENDATION_DETAIL,
                        source_ref=state.recommendation_source_ref or "care.recommendation.page",
                        page_or_index=f"rec_page:{active_page - 1}",
                        state_token=f"care:{actor_id}",
                    ),
                )
            )
        if end < len(rows_products):
            nav_row.append(
                InlineKeyboardButton(
                    text=i18n.t("common.next", locale),
                    callback_data=await _encode_runtime_callback(
                        profile=CardProfile.PRODUCT,
                        entity_type=EntityType.CARE_PRODUCT,
                        entity_id=recommendation_id,
                        action=CardAction.OPEN,
                        source_context=SourceContext.RECOMMENDATION_DETAIL,
                        source_ref=state.recommendation_source_ref or "care.recommendation.page",
                        page_or_index=f"rec_page:{active_page + 1}",
                        state_token=f"care:{actor_id}",
                    ),
                )
            )
        if nav_row:
            buttons.append(nav_row)
        buttons.append(
            [
                InlineKeyboardButton(
                    text=i18n.t("patient.care.catalog.title", locale).split("/")[0].strip(),
                    callback_data=await _encode_runtime_callback(
                        profile=CardProfile.PRODUCT,
                        entity_type=EntityType.CARE_PRODUCT,
                        entity_id="categories",
                        action=CardAction.BACK,
                        source_context=SourceContext.CARE_CATALOG_CATEGORY,
                        source_ref="care.catalog.entry",
                        page_or_index="back_categories",
                        state_token=f"care:{actor_id}",
                    ),
                )
            ]
        )
        flow = await _load_flow_state(actor_id)
        flow.care = state
        await _save_flow_state(actor_id, flow)
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=_compose_product_object_list_text(header_lines=header_lines, row_cards=page_rows),
            keyboard=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

    async def _render_doctor_pref_panel(
        message: Message | CallbackQuery, *, actor_id: int, session_id: str, clinic_id: str, branch_id: str | None
    ) -> None:
        locale = _locale()
        doctors = booking_flow.list_doctors(clinic_id=clinic_id, branch_id=branch_id)
        rows = [[InlineKeyboardButton(text=i18n.t("patient.booking.doctor.any", locale), callback_data=f"book:doc:{session_id}:any")]]
        rows.extend([[InlineKeyboardButton(text=doctor.display_name, callback_data=f"book:doc:{session_id}:{doctor.doctor_id}")] for doctor in doctors[:6]])
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=i18n.t("patient.booking.doctor.prompt", locale),
            keyboard=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    async def _render_slot_panel(message: Message | CallbackQuery, *, actor_id: int, session_id: str) -> None:
        locale = _locale()
        slots = await booking_flow.list_slots_for_session(booking_session_id=session_id)
        if not slots:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.slot.empty", locale),
            )
            return
        rows = []
        for slot in slots:
            label = slot.start_at.astimezone(timezone.utc).strftime("%a %d %b · %H:%M UTC")
            rows.append([InlineKeyboardButton(text=label, callback_data=f"book:slot:{session_id}:{slot.slot_id}")])
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=i18n.t("patient.booking.slot.prompt", locale),
            keyboard=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    async def _render_review_finalize_panel(message: Message | CallbackQuery, *, actor_id: int, session_id: str) -> None:
        locale = _locale()
        session = await booking_flow.get_booking_session(booking_session_id=session_id)
        if session is None:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.review.unavailable", locale),
            )
            return

        fallback_locale = _fallback_locale_for_clinic(session.clinic_id)
        service_label = i18n.t("patient.booking.review.value.missing", locale)
        if session.service_id:
            service = reference.get_service(session.clinic_id, session.service_id)
            service_label = _resolve_service_label(
                service_title_key=(service.title_key if service is not None else None),
                service_code=(service.code if service is not None else None),
                fallback_id=session.service_id,
                locale=locale,
                fallback_locale=fallback_locale,
                i18n=i18n,
            )

        doctor_label = i18n.t("patient.booking.review.value.any_doctor", locale)
        if session.doctor_preference_type == "specific":
            doctor = reference.get_doctor(session.clinic_id, session.doctor_id or "") if session.doctor_id else None
            doctor_label = _resolve_reference_label(
                display_name=(doctor.display_name if doctor is not None else None),
                fallback_id=session.doctor_id,
                locale=locale,
                i18n=i18n,
            )

        branch = reference.get_branch(session.clinic_id, session.branch_id or "") if session.branch_id else None
        branch_label = _resolve_reference_label(
            display_name=(branch.display_name if branch is not None else None),
            fallback_id=session.branch_id,
            locale=locale,
            i18n=i18n,
        )

        datetime_label = i18n.t("patient.booking.review.value.missing", locale)
        if session.selected_slot_id:
            slot = await booking_flow.get_availability_slot(slot_id=session.selected_slot_id)
            if slot is not None:
                timezone_name = _resolve_booking_timezone_name(clinic_id=session.clinic_id, branch_id=slot.branch_id or session.branch_id)
                datetime_label = slot.start_at.astimezone(_zone_or_utc(timezone_name)).strftime("%Y-%m-%d %H:%M %Z")

        phone_label = session.contact_phone_snapshot or i18n.t("patient.booking.review.value.missing", locale)
        text = i18n.t("patient.booking.review.panel", locale).format(
            service=service_label,
            doctor=doctor_label,
            datetime=datetime_label,
            branch=branch_label,
            phone=phone_label,
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.booking.review.confirm_cta", locale),
                        callback_data=f"book:confirm:{session_id}",
                    )
                ]
            ]
        )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=text,
            keyboard=keyboard,
        )

    async def _render_finalize_outcome(message: Message | CallbackQuery, *, actor_id: int, session_id: str, finalized) -> None:
        locale = _locale()
        if isinstance(finalized, OrchestrationSuccess):
            booking = finalized.entity
            card = booking_flow.build_booking_card(booking=booking)
            clinic_fallback_locale = _fallback_locale_for_clinic(booking.clinic_id)
            service = reference.get_service(booking.clinic_id, booking.service_id)
            service_label = _resolve_service_label(
                service_title_key=(service.title_key if service is not None else None),
                service_code=(service.code if service is not None else None),
                fallback_id=booking.service_id,
                locale=locale,
                fallback_locale=clinic_fallback_locale,
                i18n=i18n,
            )
            doctor = reference.get_doctor(booking.clinic_id, booking.doctor_id or "") if booking.doctor_id else None
            doctor_label = _resolve_reference_label(
                display_name=(doctor.display_name if doctor is not None else None),
                fallback_id=booking.doctor_id,
                locale=locale,
                i18n=i18n,
            )
            branch = reference.get_branch(booking.clinic_id, booking.branch_id or "") if booking.branch_id else None
            branch_label = _resolve_reference_label(
                display_name=(branch.display_name if branch is not None else None),
                fallback_id=booking.branch_id,
                locale=locale,
                i18n=i18n,
            )
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.success", locale).format(
                    doctor=doctor_label,
                    service=service_label,
                    datetime=card.datetime_label,
                    branch=branch_label,
                    status=_resolve_status_label(status=booking.status, locale=locale, i18n=i18n),
                ),
            )
            return
        key = {
            "invalid_state": "patient.booking.finalize.invalid_state",
            "slot_unavailable": "patient.booking.finalize.slot_unavailable",
            "conflict": "patient.booking.finalize.conflict",
            "escalated": "patient.booking.escalated",
        }.get(finalized.kind, "patient.booking.finalize.invalid_state")
        await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=session_id, text=i18n.t(key, locale))

    async def _render_patient_home_panel(message: Message | CallbackQuery, *, actor_id: int) -> None:
        locale = _locale()
        rows: list[list[InlineKeyboardButton]] = [
            [InlineKeyboardButton(text=i18n.t("patient.home.action.book", locale), callback_data="phome:book")],
            [InlineKeyboardButton(text=i18n.t("patient.home.action.my_booking", locale), callback_data="phome:my_booking")],
        ]
        if recommendation_service is not None:
            rows.append(
                [InlineKeyboardButton(text=i18n.t("patient.home.action.recommendations", locale), callback_data="phome:recommendations")]
            )
        if care_commerce_service is not None:
            rows.append([InlineKeyboardButton(text=i18n.t("patient.home.action.care", locale), callback_data="phome:care")])
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="patient_home",
            text=i18n.t("patient.home.panel", locale),
            keyboard=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    async def _enter_new_booking(message: Message | CallbackQuery, *, actor_id: int) -> None:
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.booking.unavailable", _locale()),
            )
            return
        session = await booking_flow.start_or_resume_session(
            clinic_id=clinic_id,
            telegram_user_id=actor_id,
        )
        flow = await _load_flow_state(actor_id)
        flow.booking_session_id = session.booking_session_id
        await _save_flow_state(actor_id, flow)
        await _render_resume_panel(message, actor_id=actor_id, session_id=session.booking_session_id, clinic_id=clinic_id)

    async def _enter_existing_booking_lookup(message: Message | CallbackQuery, *, actor_id: int) -> None:
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.booking.unavailable", _locale()),
            )
            return

        direct_result = await _try_resolve_existing_booking_shortcut(clinic_id=clinic_id, actor_id=actor_id)
        if direct_result is not None:
            await _show_existing_booking_result(message, actor_id=actor_id, result=direct_result)
            return

        session = await booking_flow.start_or_resume_existing_booking_session(clinic_id=clinic_id, telegram_user_id=actor_id)
        flow = await _load_flow_state(actor_id)
        flow.booking_session_id = session.booking_session_id
        flow.booking_mode = "existing_lookup_contact"
        await _save_flow_state(actor_id, flow)
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session.booking_session_id,
            text=i18n.t("patient.booking.my.contact_prompt", _locale()),
        )

    async def _enter_recommendations_list(message: Message | CallbackQuery, *, actor_id: int) -> None:
        if recommendation_service is None:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.home.action.unavailable", _locale()),
            )
            return
        patient_id = await _resolve_patient_id_for_user(actor_id)
        if not patient_id:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.recommendations.patient_resolution_failed", _locale()),
            )
            return
        rows = await recommendation_service.list_for_patient(patient_id=patient_id)
        if not rows:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.recommendations.empty", _locale()),
            )
            return
        lines = [i18n.t("patient.recommendations.title", _locale())]
        for row in rows[:8]:
            lines.append(f"• {row.title} [{row.recommendation_type}] ({row.status})")
            lines.append(f"  /recommendation_open {row.recommendation_id}")
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="patient_home",
            text="\n".join(lines),
        )

    async def _enter_care_catalog(message: Message | CallbackQuery, *, actor_id: int) -> None:
        if care_commerce_service is None:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.home.action.unavailable", _locale()),
            )
            return
        clinic_id = _primary_clinic_id()
        if clinic_id is None:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.booking.unavailable", _locale()),
            )
            return
        state = await _care_state(actor_id)
        state.selected_category = None
        state.category_page = 0
        state.recommendation_id = None
        state.recommendation_type = None
        state.recommendation_reason = None
        state.recommendation_page = 0
        state.recommendation_products = []
        state.product_page_by_category = {}
        flow = await _load_flow_state(actor_id)
        flow.care = state
        await _save_flow_state(actor_id, flow)
        await _render_care_categories_panel(message, actor_id=actor_id, clinic_id=clinic_id)

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        if not message.from_user:
            return
        await _render_patient_home_panel(message, actor_id=message.from_user.id)

    @router.message(Command("care"))
    async def care_catalog(message: Message) -> None:
        if not message.from_user:
            return
        await _enter_care_catalog(message, actor_id=message.from_user.id)

    async def _resolve_patient_id_for_user(telegram_user_id: int) -> str | None:
        clinic_id = _primary_clinic_id()
        if clinic_id is None or recommendation_repository is None:
            return None
        list_finder = getattr(recommendation_repository, "find_patient_ids_by_telegram_user", None)
        if callable(list_finder):
            try:
                rows = await list_finder(clinic_id=clinic_id, telegram_user_id=telegram_user_id)
            except Exception:
                return None
            if not isinstance(rows, (list, tuple)):
                return None
            trusted = tuple(str(row).strip() for row in rows if isinstance(row, str) and row.strip())
            if len(trusted) != 1:
                return None
            return trusted[0]
        finder = getattr(recommendation_repository, "find_patient_id_by_telegram_user", None)
        if not callable(finder):
            return None
        try:
            patient_id = await finder(clinic_id=clinic_id, telegram_user_id=telegram_user_id)
        except Exception:
            return None
        if not isinstance(patient_id, str):
            return None
        trusted = patient_id.strip()
        return trusted or None

    async def _try_resolve_existing_booking_shortcut(
        *,
        clinic_id: str,
        actor_id: int,
    ) -> BookingControlResolutionResult | None:
        patient_id = await _resolve_patient_id_for_user(actor_id)
        if not patient_id:
            return None
        try:
            direct_result = await booking_flow.resolve_existing_booking_for_known_patient(
                clinic_id=clinic_id,
                telegram_user_id=actor_id,
                patient_id=patient_id,
            )
        except Exception:
            return None
        kind = getattr(direct_result, "kind", None)
        if kind not in {"exact_match", "no_match"}:
            return None
        return direct_result

    @router.message(Command("recommendations"))
    async def recommendations_list(message: Message) -> None:
        if not message.from_user:
            return
        await _enter_recommendations_list(message, actor_id=message.from_user.id)

    @router.message(Command("recommendation_open"))
    async def recommendations_open(message: Message) -> None:
        if not message.from_user or not message.text or recommendation_service is None:
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("patient.recommendations.open.usage", _locale()))
            return
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        recommendation = await recommendation_service.get(parts[1].strip())
        if not patient_id or recommendation is None or recommendation.patient_id != patient_id:
            await message.answer(i18n.t("patient.recommendations.not_found", _locale()))
            return
        if recommendation.status == "issued":
            recommendation = await recommendation_service.mark_viewed(recommendation_id=recommendation.recommendation_id)
        text = i18n.t("patient.recommendations.detail", _locale()).format(
            title=recommendation.title if recommendation else "-",
            body=(recommendation.body_text if recommendation else "-"),
            recommendation_type=(recommendation.recommendation_type if recommendation else "-"),
            status=(recommendation.status if recommendation else "-"),
            recommendation_id=parts[1].strip(),
        )
        await message.answer(text)

    @router.message(Command("recommendation_action"))
    async def recommendations_action(message: Message) -> None:
        if not message.from_user or not message.text or recommendation_service is None:
            return
        parts = message.text.split(maxsplit=3)
        if len(parts) != 4:
            await message.answer(i18n.t("patient.recommendations.action.usage", _locale()))
            return
        action = parts[1].strip()
        recommendation_id = parts[2].strip()
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        recommendation = await recommendation_service.get(recommendation_id)
        if not patient_id or recommendation is None or recommendation.patient_id != patient_id:
            await message.answer(i18n.t("patient.recommendations.not_found", _locale()))
            return
        try:
            if action == "ack":
                updated = await recommendation_service.acknowledge(recommendation_id=recommendation_id)
            elif action == "accept":
                updated = await recommendation_service.accept(recommendation_id=recommendation_id)
            elif action == "decline":
                updated = await recommendation_service.decline(recommendation_id=recommendation_id)
            else:
                await message.answer(i18n.t("patient.recommendations.action.usage", _locale()))
                return
        except ValueError:
            await message.answer(i18n.t("patient.recommendations.action.invalid_state", _locale()))
            return
        await message.answer(i18n.t("patient.recommendations.action.ok", _locale()).format(status=(updated.status if updated else recommendation.status)))

    @router.message(Command("recommendation_products"))
    async def recommendation_products(message: Message) -> None:
        if not message.from_user or not message.text or recommendation_service is None or care_commerce_service is None:
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("patient.care.products.open.usage", _locale()))
            return
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        if not patient_id:
            await message.answer(i18n.t("patient.recommendations.patient_resolution_failed", _locale()))
            return
        recommendation = await recommendation_service.get(parts[1].strip())
        if recommendation is None or recommendation.patient_id != patient_id:
            await message.answer(i18n.t("patient.recommendations.not_found", _locale()))
            return
        resolution = await care_commerce_service.resolve_recommendation_target_result(
            clinic_id=_primary_clinic_id() or recommendation.clinic_id,
            recommendation_id=recommendation.recommendation_id,
            recommendation_type=recommendation.recommendation_type,
            locale=_locale(),
        )
        if resolution.status == "manual_target_invalid":
            state = await _care_state(message.from_user.id)
            state.recommendation_id = recommendation.recommendation_id
            state.recommendation_type = recommendation.recommendation_type
            state.recommendation_reason = recommendation.rationale_text or recommendation.body_text
            flow = await _load_flow_state(message.from_user.id)
            flow.care = state
            await _save_flow_state(message.from_user.id, flow)
            await message.answer(
                i18n.t("patient.care.products.manual_target_invalid", _locale()).format(
                    recommendation_id=recommendation.recommendation_id
                )
            )
            return
        resolved = resolution.products
        if not resolved:
            await message.answer(i18n.t("patient.care.products.empty", _locale()))
            return
        state = await _care_state(message.from_user.id)
        state.recommendation_id = recommendation.recommendation_id
        state.recommendation_type = recommendation.recommendation_type
        state.recommendation_reason = recommendation.rationale_text or recommendation.body_text
        state.recommendation_products = [item.care_product_id for item in resolved]
        state.recommendation_page = 0
        state.recommendation_source_ref = f"care.recommendation.{recommendation.recommendation_id}"
        flow = await _load_flow_state(message.from_user.id)
        flow.care = state
        await _save_flow_state(message.from_user.id, flow)
        await _render_recommendation_picker(
            message,
            actor_id=message.from_user.id,
            clinic_id=_primary_clinic_id() or recommendation.clinic_id,
            recommendation_id=recommendation.recommendation_id,
        )

    @router.message(Command("care_product_open"))
    async def care_product_open(message: Message) -> None:
        if not message.from_user or not message.text or care_commerce_service is None:
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("patient.care.product.open.usage", _locale()))
            return
        clinic_id = _primary_clinic_id()
        if clinic_id is None:
            await message.answer(i18n.t("patient.booking.unavailable", _locale()))
            return
        await _render_product_card(message, actor_id=message.from_user.id, clinic_id=clinic_id, product_id=parts[1].strip())

    @router.message(Command("care_order_create"))
    async def care_order_create(message: Message) -> None:
        if not message.from_user or not message.text or recommendation_service is None or care_commerce_service is None:
            return
        parts = message.text.split(maxsplit=3)
        if len(parts) != 4:
            await message.answer(i18n.t("patient.care.order.create.usage", _locale()))
            return
        recommendation_id, care_product_id, pickup_branch_id = parts[1], parts[2], parts[3]
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        clinic_id = _primary_clinic_id()
        if not patient_id or clinic_id is None:
            await message.answer(i18n.t("patient.recommendations.patient_resolution_failed", _locale()))
            return
        recommendation = await recommendation_service.get(recommendation_id)
        if recommendation is None or recommendation.patient_id != patient_id:
            await message.answer(i18n.t("patient.recommendations.not_found", _locale()))
            return
        branches = reference.list_branches(clinic_id)
        if not any(branch.branch_id == pickup_branch_id for branch in branches):
            await message.answer(i18n.t("patient.care.order.branch_invalid", _locale()))
            return
        linked_resolution = await care_commerce_service.resolve_recommendation_target_result(
            clinic_id=clinic_id,
            recommendation_id=recommendation_id,
            recommendation_type=recommendation.recommendation_type,
            locale=_locale(),
        )
        linked = linked_resolution.products
        match = next((item.product for item in linked if item.care_product_id == care_product_id), None)
        if match is None:
            await message.answer(i18n.t("patient.care.order.product_not_linked", _locale()))
            return
        free_qty = await care_commerce_service.compute_free_qty(branch_id=pickup_branch_id, care_product_id=match.care_product_id)
        if free_qty < 1:
            content = await care_commerce_service.resolve_product_content(
                clinic_id=clinic_id,
                product=match,
                locale=_locale(),
                fallback_locale=_locale(),
            )
            await message.answer(
                i18n.t("patient.care.order.out_of_stock", _locale()).format(
                    branch_id=pickup_branch_id,
                    title=content.title or i18n.t(match.title_key, _locale()),
                )
            )
            return
        order = await care_commerce_service.create_order(
            clinic_id=clinic_id,
            patient_id=patient_id,
            payment_mode="pay_at_pickup",
            currency_code=match.currency_code,
            pickup_branch_id=pickup_branch_id,
            recommendation_id=recommendation_id,
            booking_id=recommendation.booking_id,
            items=[(match, 1)],
        )
        await care_commerce_service.transition_order(care_order_id=order.care_order_id, to_status="confirmed")
        await message.answer(i18n.t("patient.care.order.created", _locale()).format(care_order_id=order.care_order_id, status="confirmed", branch_id=pickup_branch_id))

    @router.message(Command("care_orders"))
    async def care_orders(message: Message) -> None:
        if not message.from_user or care_commerce_service is None:
            return
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        clinic_id = _primary_clinic_id()
        if not patient_id or clinic_id is None:
            await message.answer(i18n.t("patient.recommendations.patient_resolution_failed", _locale()))
            return
        await _render_care_orders_panel(
            message,
            actor_id=message.from_user.id,
            clinic_id=clinic_id,
            patient_id=patient_id,
            page=0,
        )

    @router.message(Command("care_order_repeat"))
    async def care_order_repeat(message: Message) -> None:
        if not message.from_user or not message.text or care_commerce_service is None:
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("patient.care.orders.repeat.usage", _locale()))
            return
        clinic_id = _primary_clinic_id()
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        if clinic_id is None or patient_id is None:
            await message.answer(i18n.t("patient.recommendations.patient_resolution_failed", _locale()))
            return
        view = await _reserve_again_from_order(clinic_id=clinic_id, patient_id=patient_id, care_order_id=parts[1].strip())
        await message.answer(view.text)

    @router.message(Command("book"))
    async def book_entry(message: Message) -> None:
        if not message.from_user:
            return
        await _enter_new_booking(message, actor_id=message.from_user.id)

    @router.message(Command("my_booking"))
    async def my_booking_entry(message: Message) -> None:
        if not message.from_user:
            return
        await _enter_existing_booking_lookup(message, actor_id=message.from_user.id)

    @router.callback_query(F.data == "phome:book")
    async def patient_home_book(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        await _enter_new_booking(callback, actor_id=callback.from_user.id)
        await callback.answer()

    @router.callback_query(F.data == "phome:my_booking")
    async def patient_home_my_booking(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        await _enter_existing_booking_lookup(callback, actor_id=callback.from_user.id)
        await callback.answer()

    @router.callback_query(F.data == "phome:recommendations")
    async def patient_home_recommendations(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        await _enter_recommendations_list(callback, actor_id=callback.from_user.id)
        await callback.answer()

    @router.callback_query(F.data == "phome:care")
    async def patient_home_care(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        await _enter_care_catalog(callback, actor_id=callback.from_user.id)
        await callback.answer()

    @router.callback_query(F.data.startswith("book:svc:"))
    async def select_service(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        session_id = (await _load_flow_state(callback.from_user.id)).booking_session_id
        clinic_id = _primary_clinic_id()
        if not session_id or not clinic_id:
            await callback.answer(i18n.t("patient.booking.session.missing", _locale()), show_alert=True)
            return
        _, _, callback_session_id, service_id = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        session = await booking_flow.update_service(booking_session_id=callback_session_id, service_id=service_id)
        await _render_doctor_pref_panel(
            callback,
            actor_id=callback.from_user.id,
            session_id=session.booking_session_id,
            clinic_id=session.clinic_id,
            branch_id=session.branch_id,
        )

    @router.callback_query(F.data.startswith("care:repeat:"))
    async def care_repeat_from_order_surface(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data or care_commerce_service is None:
            return
        clinic_id = _primary_clinic_id()
        patient_id = await _resolve_patient_id_for_user(callback.from_user.id)
        if clinic_id is None or patient_id is None:
            await callback.answer(i18n.t("patient.recommendations.patient_resolution_failed", _locale()), show_alert=True)
            return
        care_order_id = callback.data.split(":", 2)[2]
        view = await _reserve_again_from_order(clinic_id=clinic_id, patient_id=patient_id, care_order_id=care_order_id)
        await callback.answer()
        if callback.message:
            keyboard = await _repeat_action_keyboard(actor_id=callback.from_user.id, care_order_id=care_order_id, view=view)
            await _send_or_edit_panel(
                actor_id=callback.from_user.id,
                message=callback,
                session_id="care",
                text=view.text,
                keyboard=keyboard,
            )

    @router.callback_query(F.data.startswith("c2|"))
    async def runtime_card_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        try:
            decoded = await card_callback_codec.decode(callback.data)
        except CardCallbackError:
            await callback.answer(i18n.t("common.card.callback.stale", _locale()), show_alert=True)
            return

        if decoded.source_context in {SourceContext.CARE_CATALOG_CATEGORY, SourceContext.RECOMMENDATION_DETAIL} and decoded.profile == CardProfile.PRODUCT:
            clinic_id = _primary_clinic_id()
            if clinic_id is None:
                await callback.answer(i18n.t("patient.booking.unavailable", _locale()), show_alert=True)
                return
            if decoded.page_or_index == "cat":
                state = await _care_state(callback.from_user.id)
                state.selected_category = decoded.entity_id
                state.product_page_by_category[decoded.entity_id] = 0
                flow = await _load_flow_state(callback.from_user.id)
                flow.care = state
                await _save_flow_state(callback.from_user.id, flow)
                await _render_care_product_list(callback, actor_id=callback.from_user.id, clinic_id=clinic_id, category=decoded.entity_id)
                return
            if decoded.page_or_index.startswith("cat_page:"):
                page = int(decoded.page_or_index.split(":", 1)[1])
                await _render_care_categories_panel(callback, actor_id=callback.from_user.id, clinic_id=clinic_id, page=page)
                return
            if decoded.page_or_index.startswith("products_page:"):
                page = int(decoded.page_or_index.split(":", 1)[1])
                await _render_care_product_list(callback, actor_id=callback.from_user.id, clinic_id=clinic_id, category=decoded.entity_id, page=page)
                return
            if decoded.page_or_index.startswith("rec_page:"):
                page = int(decoded.page_or_index.split(":", 1)[1])
                await _render_recommendation_picker(
                    callback,
                    actor_id=callback.from_user.id,
                    clinic_id=clinic_id,
                    recommendation_id=decoded.entity_id,
                    page=page,
                )
                return
            if decoded.page_or_index == "product":
                await _render_product_card(
                    callback,
                    actor_id=callback.from_user.id,
                    clinic_id=clinic_id,
                    product_id=decoded.entity_id,
                    mode=CardMode.COMPACT,
                    source_context=decoded.source_context,
                )
                return
            if decoded.page_or_index == "expand":
                await _render_product_card(
                    callback,
                    actor_id=callback.from_user.id,
                    clinic_id=clinic_id,
                    product_id=decoded.entity_id,
                    mode=CardMode.EXPANDED,
                    source_context=decoded.source_context,
                )
                return
            if decoded.page_or_index == "collapse":
                await _render_product_card(
                    callback,
                    actor_id=callback.from_user.id,
                    clinic_id=clinic_id,
                    product_id=decoded.entity_id,
                    mode=CardMode.COMPACT,
                    source_context=decoded.source_context,
                )
                return
            if decoded.page_or_index == "branch":
                await _render_branch_picker(callback, actor_id=callback.from_user.id, clinic_id=clinic_id, product_id=decoded.entity_id)
                return
            if decoded.page_or_index == "branch_select":
                if ":" not in decoded.source_ref:
                    await callback.answer(i18n.t("common.card.callback.stale", _locale()), show_alert=True)
                    return
                _, branch_id = decoded.source_ref.rsplit(":", 1)
                state = await _care_state(callback.from_user.id)
                state.selected_branch_by_product[decoded.entity_id] = branch_id
                flow = await _load_flow_state(callback.from_user.id)
                flow.care = state
                await _save_flow_state(callback.from_user.id, flow)
                await _render_product_card(callback, actor_id=callback.from_user.id, clinic_id=clinic_id, product_id=decoded.entity_id)
                return
            if decoded.page_or_index == "cover" or decoded.page_or_index.startswith("gallery"):
                product = await care_commerce_service.repository.get_product(decoded.entity_id)
                if product is None:
                    await callback.answer(i18n.t("patient.care.product.missing", _locale()), show_alert=True)
                    return
                refs = care_commerce_service.resolve_product_media_refs(product=product)
                state = await _care_state(callback.from_user.id)
                state.media_product_id = decoded.entity_id
                state.media_return_mode_by_product[decoded.entity_id] = CardMode.EXPANDED.value
                if not refs:
                    await _send_or_edit_panel(
                        actor_id=callback.from_user.id,
                        message=callback,
                        session_id="care",
                        text=i18n.t("patient.care.product.media.unavailable", _locale()),
                        keyboard=InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text=i18n.t("common.back", _locale()),
                                        callback_data=await _encode_runtime_callback(
                                            profile=CardProfile.PRODUCT,
                                            entity_type=EntityType.CARE_PRODUCT,
                                            entity_id=decoded.entity_id,
                                            action=CardAction.BACK,
                                            source_context=decoded.source_context,
                                            source_ref="care.product.media.back",
                                            page_or_index="back_product",
                                            state_token=f"care:{callback.from_user.id}",
                                        ),
                                    )
                                ]
                            ]
                        ),
                    )
                    flow = await _load_flow_state(callback.from_user.id)
                    flow.care = state
                    await _save_flow_state(callback.from_user.id, flow)
                    return
                if decoded.page_or_index == "cover":
                    cover_ref = refs[0]
                    state.media_index_by_product[decoded.entity_id] = 0
                    cover_keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text=i18n.t("common.back", _locale()),
                                    callback_data=await _encode_runtime_callback(
                                        profile=CardProfile.PRODUCT,
                                        entity_type=EntityType.CARE_PRODUCT,
                                        entity_id=decoded.entity_id,
                                        action=CardAction.BACK,
                                        source_context=decoded.source_context,
                                        source_ref="care.product.media.back",
                                        page_or_index="back_product",
                                        state_token=f"care:{callback.from_user.id}",
                                    ),
                                )
                            ]
                        ]
                    )
                    if not await _send_media_panel(
                        actor_id=callback.from_user.id,
                        message=callback,
                        caption=i18n.t("patient.care.product.media.cover", _locale()),
                        media_ref=cover_ref,
                        keyboard=cover_keyboard,
                    ):
                        await _send_or_edit_panel(
                            actor_id=callback.from_user.id,
                            message=callback,
                            session_id="care",
                            text=i18n.t("patient.care.product.media.cover", _locale()),
                            keyboard=cover_keyboard,
                        )
                    flow = await _load_flow_state(callback.from_user.id)
                    flow.care = state
                    await _save_flow_state(callback.from_user.id, flow)
                    return
                index = _parse_gallery_index(decoded.page_or_index, total=len(refs))
                state.media_index_by_product[decoded.entity_id] = index
                nav: list[InlineKeyboardButton] = []
                if index > 0:
                    nav.append(
                        InlineKeyboardButton(
                            text=i18n.t("common.prev", _locale()),
                            callback_data=await _encode_runtime_callback(
                                profile=CardProfile.PRODUCT,
                                entity_type=EntityType.CARE_PRODUCT,
                                entity_id=decoded.entity_id,
                                action=CardAction.GALLERY,
                                source_context=decoded.source_context,
                                source_ref="care.product.gallery",
                                page_or_index=f"gallery:{index - 1}",
                                state_token=f"care:{callback.from_user.id}",
                            ),
                        )
                    )
                if index + 1 < len(refs):
                    nav.append(
                        InlineKeyboardButton(
                            text=i18n.t("common.next", _locale()),
                            callback_data=await _encode_runtime_callback(
                                profile=CardProfile.PRODUCT,
                                entity_type=EntityType.CARE_PRODUCT,
                                entity_id=decoded.entity_id,
                                action=CardAction.GALLERY,
                                source_context=decoded.source_context,
                                source_ref="care.product.gallery",
                                page_or_index=f"gallery:{index + 1}",
                                state_token=f"care:{callback.from_user.id}",
                            ),
                        )
                    )
                gallery_keyboard: list[list[InlineKeyboardButton]] = []
                if nav:
                    gallery_keyboard.append(nav)
                gallery_keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=i18n.t("common.back", _locale()),
                            callback_data=await _encode_runtime_callback(
                                profile=CardProfile.PRODUCT,
                                entity_type=EntityType.CARE_PRODUCT,
                                entity_id=decoded.entity_id,
                                action=CardAction.BACK,
                                source_context=decoded.source_context,
                                source_ref="care.product.media.back",
                                page_or_index="back_product",
                                state_token=f"care:{callback.from_user.id}",
                            ),
                        )
                    ]
                )
                gallery_markup = InlineKeyboardMarkup(inline_keyboard=gallery_keyboard)
                if not await _send_media_panel(
                    actor_id=callback.from_user.id,
                    message=callback,
                    caption=i18n.t("patient.care.product.media.gallery", _locale()).format(index=index + 1, total=len(refs)),
                    media_ref=refs[index],
                    keyboard=gallery_markup,
                ):
                    await _send_or_edit_panel(
                        actor_id=callback.from_user.id,
                        message=callback,
                        session_id="care",
                        text=i18n.t("patient.care.product.media.gallery", _locale()).format(index=index + 1, total=len(refs)),
                        keyboard=gallery_markup,
                    )
                flow = await _load_flow_state(callback.from_user.id)
                flow.care = state
                await _save_flow_state(callback.from_user.id, flow)
                return
            if decoded.page_or_index == "reserve":
                patient_id = await _resolve_patient_id_for_user(callback.from_user.id)
                if not patient_id:
                    await callback.answer(i18n.t("patient.recommendations.patient_resolution_failed", _locale()), show_alert=True)
                    return
                rec_id = (await _care_state(callback.from_user.id)).recommendation_id
                await _reserve_product(
                    callback,
                    actor_id=callback.from_user.id,
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    product_id=decoded.entity_id,
                    recommendation_id=rec_id,
                )
                return
            if decoded.page_or_index == "back_categories":
                await _render_care_categories_panel(callback, actor_id=callback.from_user.id, clinic_id=clinic_id)
                return
            if decoded.page_or_index == "back_products":
                if decoded.source_context == SourceContext.RECOMMENDATION_DETAIL:
                    state = await _care_state(callback.from_user.id)
                    if state.recommendation_id:
                        await _render_recommendation_picker(
                            callback,
                            actor_id=callback.from_user.id,
                            clinic_id=clinic_id,
                            recommendation_id=state.recommendation_id,
                        )
                        return
                category = (await _care_state(callback.from_user.id)).selected_category if decoded.entity_id == "-" else decoded.entity_id
                if not category:
                    await _render_care_categories_panel(callback, actor_id=callback.from_user.id, clinic_id=clinic_id)
                    return
                await _render_care_product_list(callback, actor_id=callback.from_user.id, clinic_id=clinic_id, category=category)
                return
            if decoded.page_or_index == "back_product":
                state = await _care_state(callback.from_user.id)
                return_mode_raw = state.media_return_mode_by_product.get(decoded.entity_id, CardMode.COMPACT.value)
                return_mode = CardMode.EXPANDED if return_mode_raw == CardMode.EXPANDED.value else CardMode.COMPACT
                await _render_product_card(
                    callback,
                    actor_id=callback.from_user.id,
                    clinic_id=clinic_id,
                    product_id=decoded.entity_id,
                    mode=return_mode,
                )
                return

        if decoded.source_context == SourceContext.CARE_ORDER_LIST and decoded.profile == CardProfile.CARE_ORDER:
            clinic_id = _primary_clinic_id()
            if clinic_id is None:
                await callback.answer(i18n.t("patient.booking.unavailable", _locale()), show_alert=True)
                return
            patient_id = await _resolve_patient_id_for_user(callback.from_user.id)
            if patient_id is None:
                await callback.answer(i18n.t("patient.recommendations.patient_resolution_failed", _locale()), show_alert=True)
                return
            if decoded.page_or_index.startswith("orders_page:"):
                page = int(decoded.page_or_index.split(":", 1)[1])
                await _render_care_orders_panel(
                    callback,
                    actor_id=callback.from_user.id,
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    page=page,
                )
                return
            if decoded.page_or_index == "repeat":
                view = await _reserve_again_from_order(
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    care_order_id=decoded.entity_id,
                )
                keyboard = await _repeat_action_keyboard(actor_id=callback.from_user.id, care_order_id=decoded.entity_id, view=view)
                await _send_or_edit_panel(
                    actor_id=callback.from_user.id,
                    message=callback,
                    session_id="care",
                    text=view.text,
                    keyboard=keyboard,
                )
                await callback.answer()
                return
            if decoded.page_or_index == "back_orders":
                await _render_care_orders_panel(
                    callback,
                    actor_id=callback.from_user.id,
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                )
                return
            if decoded.page_or_index.startswith("repeat_branch:"):
                branch_id = decoded.page_or_index.split(":", 1)[1]
                view = await _reserve_again_from_order(
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    care_order_id=decoded.entity_id,
                    selected_branch_id=branch_id,
                )
                keyboard = await _repeat_action_keyboard(actor_id=callback.from_user.id, care_order_id=decoded.entity_id, view=view)
                await _send_or_edit_panel(
                    actor_id=callback.from_user.id,
                    message=callback,
                    session_id="care",
                    text=view.text,
                    keyboard=keyboard,
                )
                await callback.answer()
                return
            if decoded.page_or_index == "open":
                await _render_care_order_card(
                    callback,
                    actor_id=callback.from_user.id,
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    care_order_id=decoded.entity_id,
                    mode=CardMode.COMPACT,
                )
                return
            if decoded.page_or_index == "open_expand":
                await _render_care_order_card(
                    callback,
                    actor_id=callback.from_user.id,
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    care_order_id=decoded.entity_id,
                    mode=CardMode.EXPANDED,
                )
                return

        if decoded.source_context == SourceContext.BOOKING_LIST and decoded.profile == CardProfile.BOOKING:
            clinic_id = _primary_clinic_id()
            if clinic_id is None:
                await callback.answer(i18n.t("patient.booking.unavailable", _locale()), show_alert=True)
                return
            callback_session_id = decoded.state_token
            booking_id = decoded.entity_id
            if decoded.page_or_index == "reschedule":
                result = await booking_flow.request_reschedule(
                    clinic_id=clinic_id,
                    telegram_user_id=callback.from_user.id,
                    callback_session_id=callback_session_id,
                    booking_id=booking_id,
                )
                if isinstance(result, OrchestrationSuccess):
                    await _start_reschedule_mode_and_render_panel(
                        callback,
                        actor_id=callback.from_user.id,
                        booking_id=result.entity.booking_id,
                    )
                    return
                await callback.answer(i18n.t("patient.booking.finalize.invalid_state", _locale()), show_alert=True)
                return
            if decoded.page_or_index == "confirm":
                result = await booking_flow.confirm_existing_booking(
                    clinic_id=clinic_id,
                    telegram_user_id=callback.from_user.id,
                    callback_session_id=callback_session_id,
                    booking_id=booking_id,
                )
                if isinstance(result, OrchestrationSuccess):
                    panel = _render_patient_booking_panel(booking=result.entity, session_state_token=callback_session_id, locale=_locale())
                    session_id = (await _load_flow_state(callback.from_user.id)).booking_session_id
                    await _send_or_edit_panel(actor_id=callback.from_user.id, message=callback, session_id=session_id, text=panel)
                    return
                await callback.answer(i18n.t("patient.booking.finalize.invalid_state", _locale()), show_alert=True)
                return
            if decoded.page_or_index == "waitlist":
                created = await booking_flow.join_earlier_slot_waitlist(
                    clinic_id=clinic_id,
                    telegram_user_id=callback.from_user.id,
                    callback_session_id=callback_session_id,
                    booking_id=booking_id,
                )
                if isinstance(created, OrchestrationSuccess):
                    session_id = (await _load_flow_state(callback.from_user.id)).booking_session_id
                    await _send_or_edit_panel(actor_id=callback.from_user.id, message=callback, session_id=session_id, text=i18n.t("patient.booking.waitlist.created", _locale()))
                    return
                await callback.answer(i18n.t("patient.booking.finalize.invalid_state", _locale()), show_alert=True)
                return
            if decoded.page_or_index == "cancel_prompt":
                await cancel_prompt_by_runtime(callback, callback_session_id=callback_session_id, booking_id=booking_id)
                return
            if decoded.page_or_index == "cancel_abort":
                await callback.answer(i18n.t("patient.booking.cancel.aborted", _locale()), show_alert=True)
                return
            if decoded.page_or_index == "cancel_confirm":
                result = await booking_flow.cancel_booking(
                    clinic_id=clinic_id,
                    telegram_user_id=callback.from_user.id,
                    callback_session_id=callback_session_id,
                    booking_id=booking_id,
                )
                if isinstance(result, OrchestrationSuccess):
                    panel = _render_patient_booking_panel(booking=result.entity, session_state_token=callback_session_id, locale=_locale())
                    session_id = (await _load_flow_state(callback.from_user.id)).booking_session_id
                    await _send_or_edit_panel(actor_id=callback.from_user.id, message=callback, session_id=session_id, text=panel)
                    return
                await callback.answer(i18n.t("patient.booking.finalize.invalid_state", _locale()), show_alert=True)
                return

    @router.callback_query(F.data.startswith("care:cat:"))
    async def care_category_pick(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if clinic_id is None or care_commerce_service is None:
            return
        category = callback.data.split(":", 2)[2]
        state = await _care_state(callback.from_user.id)
        state.selected_category = category
        flow = await _load_flow_state(callback.from_user.id)
        flow.care = state
        await _save_flow_state(callback.from_user.id, flow)
        await _render_care_product_list(callback, actor_id=callback.from_user.id, clinic_id=clinic_id, category=category)

    @router.callback_query(F.data.startswith("care:product:"))
    async def care_product_pick(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if clinic_id is None:
            return
        product_id = callback.data.split(":", 2)[2]
        await _render_product_card(callback, actor_id=callback.from_user.id, clinic_id=clinic_id, product_id=product_id)

    @router.callback_query(F.data.startswith("care:branch:"))
    async def care_branch_pick(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if clinic_id is None:
            return
        product_id = callback.data.split(":", 2)[2]
        await _render_branch_picker(callback, actor_id=callback.from_user.id, clinic_id=clinic_id, product_id=product_id)

    @router.callback_query(F.data.startswith("care:branch_select:"))
    async def care_branch_selected(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if clinic_id is None:
            return
        _, _, _, product_id, branch_id = callback.data.split(":", 4)
        state = await _care_state(callback.from_user.id)
        state.selected_branch_by_product[product_id] = branch_id
        flow = await _load_flow_state(callback.from_user.id)
        flow.care = state
        await _save_flow_state(callback.from_user.id, flow)
        await _render_product_card(callback, actor_id=callback.from_user.id, clinic_id=clinic_id, product_id=product_id)

    @router.callback_query(F.data.startswith("care:reserve:"))
    async def care_reserve_pick(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if clinic_id is None:
            return
        patient_id = await _resolve_patient_id_for_user(callback.from_user.id)
        if not patient_id:
            await callback.answer(i18n.t("patient.recommendations.patient_resolution_failed", _locale()), show_alert=True)
            return
        product_id = callback.data.split(":", 2)[2]
        rec_id = (await _care_state(callback.from_user.id)).recommendation_id
        await _reserve_product(
            callback,
            actor_id=callback.from_user.id,
            clinic_id=clinic_id,
            patient_id=patient_id,
            product_id=product_id,
            recommendation_id=rec_id,
        )

    @router.callback_query(F.data.startswith("care:back:categories"))
    async def care_back_categories(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        clinic_id = _primary_clinic_id()
        if clinic_id is None:
            return
        await _render_care_categories_panel(callback, actor_id=callback.from_user.id, clinic_id=clinic_id)

    @router.callback_query(F.data.startswith("care:back:products:"))
    async def care_back_products(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if clinic_id is None:
            return
        category = callback.data.split(":", 3)[3]
        chosen = (await _care_state(callback.from_user.id)).selected_category if category == "-" else category
        if not chosen:
            await _render_care_categories_panel(callback, actor_id=callback.from_user.id, clinic_id=clinic_id)
            return
        await _render_care_product_list(callback, actor_id=callback.from_user.id, clinic_id=clinic_id, category=chosen)

    @router.callback_query(F.data.startswith("book:doc:"))
    async def select_doctor_preference(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        if not (await _load_flow_state(callback.from_user.id)).booking_session_id:
            await callback.answer(i18n.t("patient.booking.session.missing", _locale()), show_alert=True)
            return
        _, _, callback_session_id, doctor_token = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        if doctor_token == "any":
            await booking_flow.update_doctor_preference(booking_session_id=callback_session_id, doctor_preference_type="any", doctor_id=None)
        else:
            await booking_flow.update_doctor_preference(
                booking_session_id=callback_session_id,
                doctor_preference_type="specific",
                doctor_id=doctor_token,
            )
        await _render_slot_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)

    @router.callback_query(F.data.startswith("book:slot:"))
    async def select_slot(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        locale = _locale()
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        if not (await _load_flow_state(callback.from_user.id)).booking_session_id:
            await callback.answer(i18n.t("patient.booking.session.missing", locale), show_alert=True)
            return
        _, _, callback_session_id, slot_id = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        selected = await booking_flow.select_slot(booking_session_id=callback_session_id, slot_id=slot_id)
        if isinstance(selected, (SlotUnavailableOutcome, ConflictOutcome)):
            await callback.answer(i18n.t("patient.booking.slot.unavailable", locale), show_alert=True)
            await _render_slot_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)
            return
        flow = await _load_flow_state(callback.from_user.id)
        flow.booking_mode = "existing_booking_control"
        await _save_flow_state(callback.from_user.id, flow)
        contact_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=i18n.t("patient.booking.contact.share", locale), request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await _send_or_edit_panel(
            actor_id=callback.from_user.id,
            message=callback,
            session_id=callback_session_id,
            text=i18n.t("patient.booking.contact.prompt", locale),
            reply_keyboard=contact_keyboard,
        )

    @router.callback_query(F.data.startswith("book:confirm:"))
    async def confirm_new_booking(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        locale = _locale()
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        _, _, callback_session_id = callback.data.split(":", 2)
        callback_session = await booking_flow.get_booking_session(booking_session_id=callback_session_id)
        if callback_session is not None:
            if callback_session.clinic_id != clinic_id or callback_session.telegram_user_id != callback.from_user.id:
                await callback.answer(i18n.t("patient.booking.callback.stale", locale), show_alert=True)
                return
            if callback_session.status in {"admin_escalated", "completed", "canceled", "expired"}:
                await callback.answer(i18n.t("patient.booking.finalize.invalid_state", locale), show_alert=True)
                return
        if not await booking_flow.validate_active_session_callback(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
        ):
            await callback.answer(i18n.t("patient.booking.callback.stale", locale), show_alert=True)
            return
        finalized = await booking_flow.finalize(booking_session_id=callback_session_id)
        await _render_finalize_outcome(
            callback,
            actor_id=callback.from_user.id,
            session_id=callback_session_id,
            finalized=finalized,
        )

    @router.callback_query(F.data.startswith("mybk:reschedule:"))
    async def request_reschedule(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        _, _, callback_session_id, booking_id = callback.data.split(":", 3)
        result = await booking_flow.request_reschedule(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
            booking_id=booking_id,
        )
        if isinstance(result, OrchestrationSuccess):
            await _start_reschedule_mode_and_render_panel(
                callback,
                actor_id=callback.from_user.id,
                booking_id=result.entity.booking_id,
            )
            return
        await callback.answer(i18n.t("patient.booking.finalize.invalid_state", _locale()), show_alert=True)

    @router.callback_query(F.data.startswith("rsch:start:"))
    async def reschedule_start_continue(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        _, _, callback_session_id = callback.data.split(":", 2)
        flow = await _load_flow_state(callback.from_user.id)
        if flow.booking_mode != "reschedule_booking_control" or flow.booking_session_id != callback_session_id:
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        await _send_or_edit_panel(
            actor_id=callback.from_user.id,
            message=callback,
            session_id=callback_session_id,
            text=i18n.t("patient.booking.reschedule.start.placeholder", _locale()),
        )

    @router.callback_query(F.data.startswith("rem:"))
    async def reminder_action_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        callback_parts = callback.data.split(":", 2)
        if len(callback_parts) != 3:
            await callback.answer(i18n.t("patient.reminder.action.invalid", _locale()), show_alert=True)
            return
        _, action, reminder_id = callback_parts
        if action not in {"ack", "confirm", "reschedule", "cancel"}:
            await callback.answer(i18n.t("patient.reminder.action.invalid", _locale()), show_alert=True)
            return
        message_id = str(callback.message.message_id) if callback.message else None
        outcome = await reminder_actions.handle_action(
            reminder_id=reminder_id,
            action=action,
            provider_message_id=message_id,
        )
        if outcome.kind == "accepted":
            if callback.message:
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
            await _handoff_reminder_action_to_booking_panel(callback, action=action, outcome=outcome)
            await callback.answer()
            return
        if outcome.kind == "stale":
            await callback.answer(i18n.t("patient.reminder.action.stale", _locale()), show_alert=True)
            return
        await callback.answer(i18n.t("patient.reminder.action.invalid", _locale()), show_alert=True)

    @router.callback_query(F.data.startswith("mybk:waitlist:"))
    async def join_waitlist(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        _, _, callback_session_id, booking_id = callback.data.split(":", 3)
        created = await booking_flow.join_earlier_slot_waitlist(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
            booking_id=booking_id,
        )
        if isinstance(created, OrchestrationSuccess):
            session_id = (await _load_flow_state(callback.from_user.id)).booking_session_id
            await _send_or_edit_panel(actor_id=callback.from_user.id, message=callback, session_id=session_id, text=i18n.t("patient.booking.waitlist.created", _locale()))
            return
        await callback.answer(i18n.t("patient.booking.finalize.invalid_state", _locale()), show_alert=True)

    async def cancel_prompt_by_runtime(callback: CallbackQuery, *, callback_session_id: str, booking_id: str) -> None:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("common.yes", _locale()),
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.BOOKING,
                            entity_type=EntityType.BOOKING,
                            entity_id=booking_id,
                            action=CardAction.BOOKINGS,
                            source_context=SourceContext.BOOKING_LIST,
                            source_ref="mybk.cancel_confirm",
                            page_or_index="cancel_confirm",
                            state_token=callback_session_id,
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=i18n.t("common.no", _locale()),
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.BOOKING,
                            entity_type=EntityType.BOOKING,
                            entity_id=booking_id,
                            action=CardAction.BOOKINGS,
                            source_context=SourceContext.BOOKING_LIST,
                            source_ref="mybk.cancel_abort",
                            page_or_index="cancel_abort",
                            state_token=callback_session_id,
                        ),
                    )
                ],
            ]
        )
        session_id = (await _load_flow_state(callback.from_user.id)).booking_session_id
        await _send_or_edit_panel(actor_id=callback.from_user.id, message=callback, session_id=session_id, text=i18n.t("patient.booking.cancel.confirm", _locale()), keyboard=keyboard)

    @router.callback_query(F.data.startswith("mybk:cancel_prompt:"))
    async def cancel_prompt(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        _, _, callback_session_id, booking_id = callback.data.split(":", 3)
        await cancel_prompt_by_runtime(callback, callback_session_id=callback_session_id, booking_id=booking_id)

    @router.callback_query(F.data.startswith("mybk:cancel_abort:"))
    async def cancel_abort(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        await callback.answer(i18n.t("patient.booking.cancel.aborted", _locale()), show_alert=True)

    @router.callback_query(F.data.startswith("mybk:cancel_confirm:"))
    async def cancel_confirm(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        _, _, callback_session_id, booking_id = callback.data.split(":", 3)
        result = await booking_flow.cancel_booking(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
            booking_id=booking_id,
        )
        if isinstance(result, OrchestrationSuccess):
            panel = _render_patient_booking_panel(booking=result.entity, session_state_token=callback_session_id, locale=_locale())
            session_id = (await _load_flow_state(callback.from_user.id)).booking_session_id
            await _send_or_edit_panel(actor_id=callback.from_user.id, message=callback, session_id=session_id, text=panel)
            return
        await callback.answer(i18n.t("patient.booking.finalize.invalid_state", _locale()), show_alert=True)

    @router.message(F.contact)
    async def on_contact_share(message: Message) -> None:
        if not message.from_user or not message.contact:
            return
        await _handle_contact_submission(message, actor_id=message.from_user.id, phone=message.contact.phone_number)

    @router.message(F.text.regexp(r"^\+?\d[\d\-\s\(\)]{6,}$"))
    async def on_contact_text(message: Message) -> None:
        if not message.from_user or not message.text:
            return
        await _handle_contact_submission(message, actor_id=message.from_user.id, phone=message.text)

    async def _handle_contact_submission(message: Message, *, actor_id: int, phone: str) -> None:
        locale = _locale()
        flow = await _load_flow_state(actor_id)
        session_id = flow.booking_session_id
        if not session_id:
            return
        mode = flow.booking_mode
        if mode == "existing_lookup_contact":
            clinic_id = _primary_clinic_id()
            if not clinic_id:
                return
            result = await booking_flow.resolve_existing_booking_by_contact(clinic_id=clinic_id, telegram_user_id=actor_id, phone=phone)
            await _show_existing_booking_result(message, actor_id=actor_id, result=result)
            return
        if mode == "existing_booking_control":
            return
        if mode == "reschedule_booking_control":
            return
        await booking_flow.set_contact_phone(booking_session_id=session_id, phone=phone)
        display_name = (message.from_user.full_name or "").strip() or i18n.t("patient.booking.contact.default_name", locale)
        resolution = await booking_flow.resolve_patient_from_contact(
            booking_session_id=session_id,
            phone=phone,
            fallback_display_name=display_name,
        )
        if resolution.kind == "ambiguous_escalated":
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.escalated", locale),
            )
            return
        review = await booking_flow.mark_review_ready(booking_session_id=session_id)
        if isinstance(review, InvalidStateOutcome):
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.review.invalid", locale),
            )
            return
        await _render_review_finalize_panel(message, actor_id=actor_id, session_id=session_id)

    async def _render_resume_panel(message: Message | CallbackQuery, *, actor_id: int, session_id: str, clinic_id: str) -> None:
        flow = await _load_flow_state(actor_id)
        if flow.booking_mode == "reschedule_booking_control":
            await _render_reschedule_start_panel(message, actor_id=actor_id, session_id=session_id)
            return
        resume = await booking_flow.determine_resume_panel(booking_session_id=session_id)
        if resume is None:
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=session_id, text=i18n.t("patient.booking.session.missing", _locale()))
            return
        if resume.panel_key == "service_selection":
            await _render_service_panel(message, actor_id=actor_id, session_id=session_id, clinic_id=clinic_id)
            return
        if resume.panel_key == "doctor_preference_selection":
            await _render_doctor_pref_panel(
                message,
                actor_id=actor_id,
                session_id=session_id,
                clinic_id=resume.booking_session.clinic_id,
                branch_id=resume.booking_session.branch_id,
            )
            return
        if resume.panel_key == "slot_selection":
            await _render_slot_panel(message, actor_id=actor_id, session_id=session_id)
            return
        if resume.panel_key == "contact_collection":
            flow = await _load_flow_state(actor_id)
            flow.booking_mode = "new_booking_contact"
            await _save_flow_state(actor_id, flow)
            contact_keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=i18n.t("patient.booking.contact.share", _locale()), request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.contact.prompt", _locale()),
                reply_keyboard=contact_keyboard,
            )
            return
        if resume.panel_key == "review_finalize":
            await _render_review_finalize_panel(message, actor_id=actor_id, session_id=session_id)
            return
        await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=session_id, text=i18n.t("patient.booking.resume.terminal", _locale()))

    def _render_patient_booking_panel(*, booking, session_state_token: str, locale: str) -> str:
        snapshot = booking_flow.build_booking_snapshot(
            booking=booking,
            role_variant="patient",
            state_token=session_state_token,
            patient_label="You",
        )
        seed = booking_builder.build_seed(snapshot=snapshot, i18n=i18n, locale=locale)
        shell = BookingCardAdapter.build(
            seed=seed,
            source=SourceRef(context=SourceContext.BOOKING_LIST, source_ref="patient_my_booking"),
            i18n=i18n,
            locale=locale,
            mode=CardMode.EXPANDED,
        )
        return CardShellRenderer.to_panel(shell).text

    async def _build_patient_booking_controls_keyboard(*, booking, session_state_token: str, locale: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                *(
                    [
                        [
                            InlineKeyboardButton(
                                text=i18n.t("card.booking.action.confirm", locale),
                                callback_data=await _encode_runtime_callback(
                                    profile=CardProfile.BOOKING,
                                    entity_type=EntityType.BOOKING,
                                    entity_id=booking.booking_id,
                                    action=CardAction.CONFIRM,
                                    source_context=SourceContext.BOOKING_LIST,
                                    source_ref="mybk.confirm",
                                    page_or_index="confirm",
                                    state_token=session_state_token,
                                ),
                            )
                        ]
                    ]
                    if booking.status == "pending_confirmation"
                    else []
                ),
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.booking.my.reschedule", locale),
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.BOOKING,
                            entity_type=EntityType.BOOKING,
                            entity_id=booking.booking_id,
                            action=CardAction.RESCHEDULE,
                            source_context=SourceContext.BOOKING_LIST,
                            source_ref="mybk.reschedule",
                            page_or_index="reschedule",
                            state_token=session_state_token,
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.booking.my.earlier_slot", locale),
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.BOOKING,
                            entity_type=EntityType.BOOKING,
                            entity_id=booking.booking_id,
                            action=CardAction.RESCHEDULE,
                            source_context=SourceContext.BOOKING_LIST,
                            source_ref="mybk.waitlist",
                            page_or_index="waitlist",
                            state_token=session_state_token,
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.booking.my.cancel", locale),
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.BOOKING,
                            entity_type=EntityType.BOOKING,
                            entity_id=booking.booking_id,
                            action=CardAction.CANCEL,
                            source_context=SourceContext.BOOKING_LIST,
                            source_ref="mybk.cancel_prompt",
                            page_or_index="cancel_prompt",
                            state_token=session_state_token,
                        ),
                    )
                ],
            ],
        )

    async def _send_fresh_booking_panel_from_callback(
        *,
        callback: CallbackQuery,
        actor_id: int,
        session_id: str,
        text: str,
        keyboard: InlineKeyboardMarkup | None = None,
    ) -> None:
        if callback.message is None:
            return
        sent = await callback.message.answer(text, reply_markup=keyboard)
        await card_runtime.bind_panel(
            actor_id=actor_id,
            chat_id=sent.chat.id,
            message_id=sent.message_id,
            panel_family=PanelFamily.BOOKING_DETAIL,
            profile=None,
            entity_id=session_id or None,
            source_context=SourceContext.BOOKING_LIST,
            source_ref=session_id,
            page_or_index=session_id,
            state_token=session_id or f"actor:{actor_id}",
        )

    async def _render_reschedule_start_panel(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        session_id: str,
        header: str | None = None,
        send_fresh_from_callback: bool = False,
    ) -> None:
        locale = _locale()
        lines = [line for line in (header, i18n.t("patient.booking.reschedule.start.header", locale), i18n.t("patient.booking.reschedule.start.body", locale)) if line]
        text = "\n\n".join(lines)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.booking.reschedule.start.cta", locale),
                        callback_data=f"rsch:start:{session_id}",
                    )
                ]
            ]
        )
        if send_fresh_from_callback and hasattr(message, "message"):
            await _send_fresh_booking_panel_from_callback(
                callback=message,
                actor_id=actor_id,
                session_id=session_id,
                text=text,
                keyboard=keyboard,
            )
            return
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=text,
            keyboard=keyboard,
        )

    async def _start_reschedule_mode_and_render_panel(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        booking_id: str,
        header: str | None = None,
        send_fresh_from_callback: bool = False,
    ) -> None:
        locale = _locale()
        clinic_id = _primary_clinic_id()
        fallback = i18n.t("patient.booking.reschedule.start.unavailable", locale)
        if clinic_id is None:
            text = f"{header}\n\n{fallback}" if header else fallback
            if send_fresh_from_callback and hasattr(message, "message"):
                await _send_fresh_booking_panel_from_callback(
                    callback=message,
                    actor_id=actor_id,
                    session_id=f"reschedule_unavailable:{actor_id}",
                    text=text,
                )
            else:
                await _send_or_edit_panel(
                    actor_id=actor_id,
                    message=message,
                    session_id=f"reschedule_unavailable:{actor_id}",
                    text=text,
                )
            return
        started = await booking_flow.start_patient_reschedule_session(
            clinic_id=clinic_id,
            telegram_user_id=actor_id,
            booking_id=booking_id,
        )
        if started.kind != "ready" or started.booking_session is None:
            text = f"{header}\n\n{fallback}" if header else fallback
            if send_fresh_from_callback and hasattr(message, "message"):
                await _send_fresh_booking_panel_from_callback(
                    callback=message,
                    actor_id=actor_id,
                    session_id=f"reschedule_unavailable:{actor_id}",
                    text=text,
                )
            else:
                await _send_or_edit_panel(
                    actor_id=actor_id,
                    message=message,
                    session_id=f"reschedule_unavailable:{actor_id}",
                    text=text,
                )
            return
        flow = await _load_flow_state(actor_id)
        flow.booking_session_id = started.booking_session.booking_session_id
        flow.booking_mode = "reschedule_booking_control"
        await _save_flow_state(actor_id, flow)
        await _render_reschedule_start_panel(
            message,
            actor_id=actor_id,
            session_id=started.booking_session.booking_session_id,
            header=header,
            send_fresh_from_callback=send_fresh_from_callback,
        )

    async def _handoff_reminder_action_to_booking_panel(callback: CallbackQuery, *, action: str, outcome) -> None:
        if not callback.from_user:
            return
        locale = _locale()
        header_key = f"patient.reminder.action.outcome.{outcome.reason}"
        header = i18n.t(header_key, locale)
        if header == header_key:
            header = i18n.t("patient.reminder.action.accepted", locale)
        if action == "reschedule":
            if not outcome.booking_id:
                await _send_fresh_booking_panel_from_callback(
                    callback=callback,
                    actor_id=callback.from_user.id,
                    session_id=f"reminder_outcome:{callback.from_user.id}",
                    text=f"{header}\n\n{i18n.t('patient.booking.reschedule.start.unavailable', locale)}",
                )
                return
            await _start_reschedule_mode_and_render_panel(
                callback,
                actor_id=callback.from_user.id,
                booking_id=outcome.booking_id,
                header=header,
                send_fresh_from_callback=True,
            )
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id or not outcome.booking_id:
            await _send_fresh_booking_panel_from_callback(
                callback=callback,
                actor_id=callback.from_user.id,
                session_id=f"reminder_outcome:{callback.from_user.id}",
                text=f"{header}\n\n{i18n.t('patient.reminder.action.handoff.unavailable', locale)}",
            )
            return
        started = await booking_flow.start_existing_booking_control_for_booking(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            booking_id=outcome.booking_id,
        )
        booking = started.booking
        session = started.booking_session
        if started.kind != "ready" or booking is None or session is None:
            await _send_fresh_booking_panel_from_callback(
                callback=callback,
                actor_id=callback.from_user.id,
                session_id=f"reminder_outcome:{callback.from_user.id}",
                text=f"{header}\n\n{i18n.t('patient.reminder.action.handoff.unavailable', locale)}",
            )
            return
        flow = await _load_flow_state(callback.from_user.id)
        flow.booking_session_id = session.booking_session_id
        flow.booking_mode = "existing_booking_control"
        await _save_flow_state(callback.from_user.id, flow)
        booking_text = _render_patient_booking_panel(booking=booking, session_state_token=session.booking_session_id, locale=locale)
        keyboard = await _build_patient_booking_controls_keyboard(
            booking=booking,
            session_state_token=session.booking_session_id,
            locale=locale,
        )
        await _send_fresh_booking_panel_from_callback(
            callback=callback,
            actor_id=callback.from_user.id,
            session_id=session.booking_session_id,
            text=f"{header}\n\n{booking_text}",
            keyboard=keyboard,
        )

    async def _show_existing_booking_result(message: Message, *, actor_id: int, result: BookingControlResolutionResult) -> None:
        locale = _locale()
        current_session_id = (await _load_flow_state(actor_id)).booking_session_id
        effective_session_id = result.booking_session.booking_session_id if result.booking_session else current_session_id
        if effective_session_id:
            flow = await _load_flow_state(actor_id)
            flow.booking_session_id = effective_session_id
            flow.booking_mode = "existing_booking_control"
            await _save_flow_state(actor_id, flow)
        if result.kind == "ambiguous_escalated":
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=effective_session_id, text=i18n.t("patient.booking.escalated", locale))
            return
        if result.kind == "no_match":
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=effective_session_id, text=i18n.t("patient.booking.my.no_match", locale))
            return
        if result.kind != "exact_match" or not result.bookings:
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=effective_session_id, text=i18n.t("patient.booking.finalize.invalid_state", locale))
            return
        booking = result.bookings[0]
        keyboard = await _build_patient_booking_controls_keyboard(booking=booking, session_state_token=effective_session_id, locale=locale)
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=effective_session_id,
            text=_render_patient_booking_panel(booking=booking, session_state_token=effective_session_id, locale=locale),
            keyboard=keyboard,
        )

    return router
