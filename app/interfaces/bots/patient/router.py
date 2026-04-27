from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from app.application.communication import ReminderActionService
from app.application.care_commerce import CareCommerceService
from app.application.booking.orchestration_outcomes import ConflictOutcome, InvalidStateOutcome, OrchestrationSuccess, SlotUnavailableOutcome
from app.application.booking.telegram_flow import (
    BookingControlResolutionResult,
    BookingPatientFlowService,
    NEW_BOOKING_ROUTE_TYPES,
    RESCHEDULE_BOOKING_CONTROL_ROUTE_TYPES,
)
from app.application.clinic_reference import ClinicReferenceService
from app.common.i18n import I18nService
from app.application.recommendation import RecommendationService
from app.interfaces.cards import (
    BookingCardAdapter,
    BookingRuntimeViewBuilder,
    CardAction,
    CardCallback,
    CardCallbackCodec,
    CardCallbackError,
    CardMode,
    CardProfile,
    CardRuntimeCoordinator,
    EntityType,
    PanelFamily,
    ProductCardAdapter,
    ProductRuntimeSnapshot,
    ProductRuntimeViewBuilder,
    SourceContext,
    SourceRef,
)

_TERMINAL_RECOMMENDATION_STATUSES = {"accepted", "declined", "withdrawn", "expired", "completed"}
_TERMINAL_CARE_ORDER_STATUSES = {"fulfilled", "canceled", "expired"}


def _is_live_care_order_status(status: str) -> bool:
    return status not in _TERMINAL_CARE_ORDER_STATUSES


def _split_patient_orders_for_surface(rows: list[Any]) -> tuple[list[Any], list[Any]]:
    ordered = sorted(rows, key=lambda row: row.updated_at, reverse=True)
    live_rows = [row for row in ordered if _is_live_care_order_status(getattr(row, "status", ""))]
    history_rows = [row for row in ordered if not _is_live_care_order_status(getattr(row, "status", ""))]
    return live_rows, history_rows


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
    booking_mode: str = "new_booking_flow"
    reschedule_booking_id: str = ""
    slot_page: int = 0
    slot_date_from: str = ""
    slot_time_window: str = "all"
    slot_suppressed_ids: tuple[str, ...] = ()
    quick_booking_prefill: dict[str, str] | None = None
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
    short_ref: str = ""
    item_summary: str = ""
    branch_label: str = ""
    status_label: str = ""
    amount_label: str = ""
    pickup_hint: str | None = None
    reservation_hint: str | None = None
    shell: Any | None = None

    def reserve_label(self) -> str:
        if self.shell is None:
            return ""
        action = next((item for item in self.shell.actions if item.action == CardAction.RESERVE), None)
        return action.label if action else ""

    def object_block_lines(self, *, index: int) -> list[str]:
        if self.shell is not None:
            meta = {row.key: row.value for row in self.shell.meta_lines}
            lines = [f"{index}. {self.shell.title}"]
            for key in ("item", "branch"):
                value = meta.get(key)
                if value:
                    lines.append(f"   - {value}")
            status = self.shell.badges[0].text if self.shell.badges else None
            if status:
                lines.append(f"   - {status}")
            pickup = meta.get("pickup")
            if pickup:
                lines.append(f"   - {pickup}")
            return lines
        lines = [f"{index}. {self.short_ref}"]
        if self.item_summary:
            lines.append(f"   - {self.item_summary}")
        if self.branch_label:
            lines.append(f"   - {self.branch_label}")
        if self.status_label:
            lines.append(f"   - {self.status_label}")
        if self.pickup_hint:
            lines.append(f"   - {self.pickup_hint}")
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


def _service_button_emoji(*, service_code: str | None, service_title_key: str | None) -> str:
    marker = f"{(service_code or '').lower()} {(service_title_key or '').lower()}"
    if any(token in marker for token in ("consult", "консульт")):
        return "🦷"
    if any(token in marker for token in ("hygiene", "clean", "гигиен", "чист")):
        return "🪥"
    if any(token in marker for token in ("treat", "caries", "леч", "кариес")):
        return "🛠"
    if any(token in marker for token in ("white", "отбел")):
        return "✨"
    if any(token in marker for token in ("surgery", "implant", "хирург", "имплан")):
        return "⚕️"
    if any(token in marker for token in ("child", "pediatric", "дет")):
        return "🧒"
    return "🦷"


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


def _resolve_care_order_status_label(*, status: str, locale: str, i18n: I18nService) -> str:
    key = f"care.order.status.{status}"
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
            booking_mode=payload.get("booking_mode", "new_booking_flow"),
            reschedule_booking_id=payload.get("reschedule_booking_id", ""),
            slot_page=int(payload.get("slot_page", 0) or 0),
            slot_date_from=str(payload.get("slot_date_from", "") or ""),
            slot_time_window=str(payload.get("slot_time_window", "all") or "all"),
            slot_suppressed_ids=tuple(str(item) for item in (payload.get("slot_suppressed_ids") or [])),
            quick_booking_prefill=dict(payload.get("quick_booking_prefill") or {}),
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
                "reschedule_booking_id": state.reschedule_booking_id,
                "slot_page": int(state.slot_page),
                "slot_date_from": state.slot_date_from,
                "slot_time_window": state.slot_time_window,
                "slot_suppressed_ids": list(state.slot_suppressed_ids or ()),
                "quick_booking_prefill": dict(state.quick_booking_prefill or {}),
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

    def _reset_slot_view_state(flow: _PatientFlowState) -> None:
        flow.slot_page = 0
        flow.slot_date_from = ""
        flow.slot_time_window = "all"
        _reset_slot_suppression(flow)

    def _suppress_slot_in_flow(flow: _PatientFlowState, slot_id: str) -> None:
        if not slot_id:
            return
        existing = [item for item in flow.slot_suppressed_ids if item != slot_id]
        existing.append(slot_id)
        flow.slot_suppressed_ids = tuple(existing[-20:])

    def _reset_slot_suppression(flow: _PatientFlowState) -> None:
        flow.slot_suppressed_ids = ()

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
    SLOT_PAGE_SIZE = 5
    SLOT_PREFETCH_LIMIT = 80
    SLOT_DATE_PICKER_DAYS = 14

    def _page_slice(total: int, page: int, page_size: int = _LIST_PAGE_SIZE) -> tuple[int, int, int]:
        if total <= 0:
            return 0, 0, 0
        page_count = (total + page_size - 1) // page_size
        safe_page = min(max(page, 0), page_count - 1)
        start = safe_page * page_size
        end = min(start + page_size, total)
        return safe_page, start, end

    _RU_WEEKDAYS_SHORT = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
    _EN_WEEKDAYS_SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    _RU_MONTHS_GENITIVE = (
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    )
    _EN_MONTHS_SHORT = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

    def _is_ru_locale(locale: str) -> bool:
        return (locale or "").lower().startswith("ru")

    def _weekday_label(*, value: date, locale: str) -> str:
        return (_RU_WEEKDAYS_SHORT if _is_ru_locale(locale) else _EN_WEEKDAYS_SHORT)[value.weekday()]

    def _month_label(*, value: date, locale: str) -> str:
        return (_RU_MONTHS_GENITIVE if _is_ru_locale(locale) else _EN_MONTHS_SHORT)[value.month - 1]

    def _slot_date_label(*, value: date, locale: str) -> str:
        return f"{_weekday_label(value=value, locale=locale)}, {value.day} {_month_label(value=value, locale=locale)}"

    def _slot_datetime_label(*, value: datetime, locale: str) -> str:
        return f"{_slot_date_label(value=value.date(), locale=locale)} · {value:%H:%M}"

    def _format_patient_date(dt: datetime, *, locale: str) -> str:
        value = dt.date()
        if _is_ru_locale(locale):
            return f"{value.day} {_month_label(value=value, locale=locale)} {value.year}"
        return f"{value.day} {_month_label(value=value, locale=locale)} {value.year}"

    def _format_patient_time(dt: datetime, *, locale: str) -> str:  # noqa: ARG001
        return f"{dt:%H:%M}"

    def _format_patient_datetime_parts(dt: datetime, *, locale: str) -> tuple[str, str]:
        return _format_patient_date(dt, locale=locale), _format_patient_time(dt, locale=locale)

    def _format_patient_datetime_line(dt: datetime, *, locale: str) -> str:
        date_label, time_label = _format_patient_datetime_parts(dt, locale=locale)
        return f"{date_label} · {time_label}"

    def _parse_iso_date(value: str) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    def _resolve_time_window(*, value: str | None) -> str:
        token = (value or "all").strip().lower()
        return token if token in {"all", "morning", "day", "evening"} else "all"

    def _match_slot_time_window(*, local_start: datetime, time_window: str) -> bool:
        if time_window == "all":
            return True
        hour = local_start.hour
        if time_window == "morning":
            return 6 <= hour < 12
        if time_window == "day":
            return 12 <= hour < 17
        if time_window == "evening":
            return 17 <= hour < 22
        return True

    def _availability_label(row: Any, *, locale: str) -> str:
        if row is None or row.status != "active" or row.free_qty <= 0:
            return i18n.t("patient.care.availability.out", locale)
        if row.free_qty <= 2:
            return i18n.t("patient.care.availability.low", locale)
        return i18n.t("patient.care.availability.in", locale)

    def _render_patient_care_product_text(
        *,
        locale: str,
        title: str,
        sku: str,
        category: str,
        price: str,
        availability: str,
        branch: str,
        description: str | None,
        usage_hint: str | None,
        recommendation_reason: str | None,
    ) -> str:
        lines = [
            f"🪥 {title}",
            "",
            f"{i18n.t('patient.care.product.field.sku', locale)}: {sku}",
            f"{i18n.t('patient.care.product.field.category', locale)}: {category}",
            f"{i18n.t('patient.care.product.field.price', locale)}: {price}",
            f"{i18n.t('patient.care.product.field.availability', locale)}: {availability}",
            f"{i18n.t('patient.care.product.field.branch', locale)}: {branch}",
        ]
        description_value = (description or "").strip()
        if description_value:
            lines.extend(["", description_value])
        usage_value = (usage_hint or "").strip()
        if usage_value:
            lines.extend(["", i18n.t("patient.care.product.usage_hint", locale).format(usage_hint=usage_value)])
        recommendation_value = (recommendation_reason or "").strip()
        if recommendation_value:
            lines.extend(
                [
                    "",
                    i18n.t("patient.care.product.recommendation_reason", locale).format(reason=recommendation_value[:280]),
                ]
            )
        return "\n".join(lines)

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
                text=i18n.t("patient.care.catalog.empty.panel", locale),
                keyboard=_care_entry_nav_keyboard(locale=locale),
            )
            return
        state = await _care_state(actor_id)
        active_page, start, end = _page_slice(len(categories), state.category_page if page is None else page)
        state.category_page = active_page
        flow = await _load_flow_state(actor_id)
        flow.care = state
        await _save_flow_state(actor_id, flow)
        rows: list[list[InlineKeyboardButton]] = [
            [InlineKeyboardButton(text=i18n.t("patient.care.orders.entry.action", locale), callback_data="care:orders")]
        ]
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
                text=i18n.t("patient.care.catalog.category.empty.panel", locale),
                keyboard=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=i18n.t("patient.care.nav.back_to_categories", locale),
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
                        ],
                        [InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")],
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
            await _render_care_product_missing_panel(message, actor_id=actor_id)
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
        rows.append([InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")])
        price_label = (
            f"{int(product.price_amount)} {product.currency_code}" if product.price_amount is not None else i18n.t("patient.care.product.field.price_missing", locale)
        )
        branch_label = branch.display_name if branch else i18n.t("patient.care.product.field.branch_missing", locale)
        text = _render_patient_care_product_text(
            locale=locale,
            title=(content.title or i18n.t(product.title_key, locale)),
            sku=(content.short_label or product.sku or i18n.t("patient.booking.review.value.missing", locale)),
            category=await _category_label(category_code=product.category, locale=locale),
            price=price_label,
            availability=_availability_label(availability, locale=locale),
            branch=branch_label,
            description=content.description,
            usage_hint=content.usage_hint,
            recommendation_reason=(state.recommendation_reason if state.recommendation_id else None),
        )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=text,
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
        rows.append([InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")])
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
            await _render_care_product_missing_panel(message, actor_id=actor_id)
            return
        state = await _care_state(actor_id)
        branch_id = state.selected_branch_by_product.get(product_id) or await _resolve_preferred_branch_for_product(clinic_id=clinic_id, product_id=product_id)
        if not branch_id:
            await _render_branch_picker(message, actor_id=actor_id, clinic_id=clinic_id, product_id=product_id)
            return
        free_qty = await care_commerce_service.compute_free_qty(branch_id=branch_id, care_product_id=product_id)
        branch_label = _resolve_care_order_branch_label(clinic_id=clinic_id, branch_id=branch_id, locale=locale)
        if free_qty < 1:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="care",
                text=i18n.t("patient.care.order.out_of_stock.panel", locale).format(
                    product=i18n.t(product.title_key, locale),
                    branch=branch_label,
                ),
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
                        ],
                        [_care_catalog_nav_button(locale=locale)],
                        [InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")],
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
        await care_commerce_service.create_reservation(
            care_order_id=order.care_order_id,
            care_product_id=product.care_product_id,
            branch_id=branch_id,
            reserved_qty=1,
        )
        await _render_care_order_created_panel(
            message,
            actor_id=actor_id,
            clinic_id=clinic_id,
            order=order,
            product=product,
            branch_id=branch_id,
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
        if reply_keyboard is not None:
            if isinstance(message, CallbackQuery):
                current_message = message.message
                if current_message is None:
                    await message.answer(i18n.t("common.card.callback.stale", _locale()), show_alert=True)
                    return
                sent = await current_message.answer(text, reply_markup=reply_keyboard)
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
                await message.answer()
                return
            sent = await message.answer(text, reply_markup=reply_keyboard)
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
            return
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
        branch_map = {branch.branch_id: branch.display_name for branch in reference.list_branches(clinic_id)}
        selected_branch_label = branch_map.get(outcome.selected_branch_id or "", outcome.selected_branch_id or "")
        if outcome.ok and outcome.created_order and outcome.selected_branch_id:
            product_name = i18n.t("patient.booking.review.value.missing", locale)
            if outcome.product is not None:
                content = await care_commerce_service.resolve_product_content(
                    clinic_id=clinic_id,
                    product=outcome.product,
                    locale=locale,
                    fallback_locale=locale,
                )
                product_name = content.title or i18n.t(outcome.product.title_key, locale)
            return _RepeatActionView(
                text=i18n.t("patient.care.orders.repeat.success.panel", locale).format(
                    product=product_name,
                    branch=selected_branch_label or _resolve_reference_label(display_name=None, fallback_id=None, locale=locale, i18n=i18n),
                    status=i18n.t(f"care.order.status.{outcome.created_order.status}", locale),
                    next_step=i18n.t("patient.care.orders.repeat.next_step", locale),
                ),
                created_order_id=outcome.created_order.care_order_id,
                source_order_id=care_order_id,
            )
        if outcome.reason in {"source_not_found", "source_empty"}:
            return _RepeatActionView(text=i18n.t("patient.care.orders.repeat.not_found", locale))
        if outcome.reason == "product_unavailable":
            return _RepeatActionView(text=i18n.t("patient.care.orders.repeat.unavailable.panel", locale))
        if outcome.reason in {"branch_selection_required", "branch_required"} and outcome.available_branch_ids:
            return _RepeatActionView(
                text=i18n.t("patient.care.orders.repeat.choose_branch.panel", locale),
                choose_branch=True,
                branch_choices=outcome.available_branch_ids,
            )
        if outcome.reason == "branch_invalid":
            if outcome.available_branch_ids:
                return _RepeatActionView(
                    text=i18n.t("patient.care.orders.repeat.choose_branch.panel", locale),
                    choose_branch=True,
                    branch_choices=outcome.available_branch_ids,
                )
            return _RepeatActionView(text=i18n.t("patient.care.orders.repeat.unavailable.panel", locale))
        if outcome.reason in {"availability_inactive", "insufficient_stock", "branch_unavailable"}:
            if outcome.available_branch_ids:
                return _RepeatActionView(
                    text=i18n.t("patient.care.orders.repeat.choose_branch.panel", locale),
                    choose_branch=True,
                    branch_choices=outcome.available_branch_ids,
                )
            return _RepeatActionView(text=i18n.t("patient.care.orders.repeat.unavailable.panel", locale))
        return _RepeatActionView(text=i18n.t("patient.care.orders.repeat.unavailable.panel", locale))

    async def _repeat_action_keyboard(*, actor_id: int, care_order_id: str, view: _RepeatActionView) -> InlineKeyboardMarkup | None:
        locale = _locale()
        rows: list[list[InlineKeyboardButton]] = []
        clinic_id = _primary_clinic_id()
        branch_map = {branch.branch_id: branch.display_name for branch in reference.list_branches(clinic_id)} if clinic_id else {}
        if view.choose_branch and view.branch_choices:
            for branch_id in view.branch_choices:
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=i18n.t("patient.care.orders.repeat.branch_option", locale).format(
                                branch=branch_map.get(branch_id, branch_id),
                                branch_id=branch_map.get(branch_id, branch_id),
                            ),
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
                        text=i18n.t("patient.care.orders.repeat.open_new", locale),
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
                    text=i18n.t("patient.care.orders.repeat.back_to_orders", locale),
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
        rows.append([InlineKeyboardButton(text=i18n.t("patient.care.orders.repeat.open_catalog", locale), callback_data="phome:care")])
        rows.append([InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")])
        return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

    def _safe_order_ref(care_order_id: str, *, locale: str) -> str:
        ref = (care_order_id or "").strip()
        if not ref:
            return i18n.t("patient.booking.review.value.missing", locale)
        return f"№ …{ref[-6:]}" if len(ref) > 6 else f"№ {ref}"

    def _resolve_care_order_branch_label(*, clinic_id: str, branch_id: str | None, locale: str) -> str:
        if branch_id:
            branch = reference.get_branch(clinic_id, branch_id)
            if branch and branch.display_name:
                return branch.display_name
        return i18n.t("patient.care.order.card.branch_missing", locale)

    def _format_care_money(amount: Any, currency_code: str | None, *, locale: str) -> str:
        if amount is None:
            return i18n.t("patient.care.order.card.amount_missing", locale)
        try:
            value = float(amount)
        except (TypeError, ValueError):
            return i18n.t("patient.care.order.card.amount_missing", locale)
        rendered = f"{value:.2f}".rstrip("0").rstrip(".")
        currency = (currency_code or "").strip()
        return f"{rendered} {currency}".strip()

    async def _build_care_order_items_summary(*, clinic_id: str, order_id: str, locale: str) -> str:
        items = await care_commerce_service.repository.list_order_items(order_id)
        if not items:
            return i18n.t("patient.booking.review.value.missing", locale)
        first = items[0]
        title = i18n.t("patient.booking.review.value.missing", locale)
        product = await care_commerce_service.repository.get_product(first.care_product_id)
        if product is not None:
            content = await care_commerce_service.resolve_product_content(
                clinic_id=clinic_id,
                product=product,
                locale=locale,
                fallback_locale=locale,
            )
            title = content.title or i18n.t(product.title_key, locale)
        suffix = f" +{len(items) - 1}" if len(items) > 1 else ""
        return f"{title} x{first.quantity}{suffix}"

    async def _build_care_order_row_card(*, clinic_id: str, actor_id: int, order: Any, locale: str) -> _CompactCareOrderRowCard:
        _ = actor_id
        item_summary = await _build_care_order_items_summary(clinic_id=clinic_id, order_id=order.care_order_id, locale=locale)
        items = await care_commerce_service.repository.list_order_items(order.care_order_id)
        reservation_hint = None
        if items and order.pickup_branch_id:
            row = await care_commerce_service.get_branch_product_availability(
                branch_id=order.pickup_branch_id,
                care_product_id=items[0].care_product_id,
            )
            if row is not None and row.status == "active" and row.free_qty >= items[0].quantity:
                reservation_hint = i18n.t("patient.care.order.card.reservation_hint", locale)
        return _CompactCareOrderRowCard(
            care_order_id=order.care_order_id,
            short_ref=_safe_order_ref(order.care_order_id, locale=locale),
            item_summary=item_summary,
            branch_label=_resolve_care_order_branch_label(clinic_id=clinic_id, branch_id=order.pickup_branch_id, locale=locale),
            status_label=_resolve_care_order_status_label(status=order.status, locale=locale, i18n=i18n),
            amount_label=_format_care_money(order.total_amount, order.currency_code, locale=locale),
            pickup_hint=i18n.t("patient.care.order.card.pickup_hint", locale) if order.status in {"ready_for_pickup", "issued", "fulfilled"} else None,
            reservation_hint=reservation_hint,
        )

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
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="care",
                text=i18n.t("patient.care.orders.list.empty.panel", locale),
                keyboard=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [_care_catalog_nav_button(locale=locale)],
                        [InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")],
                    ]
                ),
            )
            return

        live_rows, history_rows = _split_patient_orders_for_surface(rows)
        state = await _care_state(actor_id)
        active_page, start, end = _page_slice(len(history_rows), state.care_order_page if page is None else page)
        state.care_order_page = active_page
        flow = await _load_flow_state(actor_id)
        flow.care = state
        await _save_flow_state(actor_id, flow)

        current_cards = [
            await _build_care_order_row_card(clinic_id=clinic_id, actor_id=actor_id, order=order, locale=locale)
            for order in live_rows[:1]
        ]
        history_cards = [
            await _build_care_order_row_card(clinic_id=clinic_id, actor_id=actor_id, order=order, locale=locale)
            for order in history_rows[start:end]
        ]

        lines: list[str] = [i18n.t("patient.care.orders.list.title", locale)]

        def _append_row(row: _CompactCareOrderRowCard) -> None:
            lines.append(f"• {row.short_ref}")
            lines.append(f"  {row.item_summary}")
            lines.append(f"  {i18n.t('patient.care.order.card.field.status', locale)}: {row.status_label}")
            lines.append(f"  {i18n.t('patient.care.order.card.field.branch', locale)}: {row.branch_label}")
            lines.append(f"  {i18n.t('patient.care.order.card.field.total', locale)}: {row.amount_label}")
            if row.pickup_hint:
                lines.append(f"  {row.pickup_hint}")
            if row.reservation_hint:
                lines.append(f"  {row.reservation_hint}")

        if current_cards:
            lines.append("")
            lines.append(i18n.t("patient.care.orders.list.current", locale))
            _append_row(current_cards[0])
        if history_rows:
            lines.append("")
            lines.append(i18n.t("patient.care.orders.list.history", locale))
            for idx, card in enumerate(history_cards):
                _append_row(card)
                if idx < len(history_cards) - 1:
                    lines.append("")
            if history_cards:
                lines.append("")
                lines.append(i18n.t("patient.care.catalog.page_indicator", locale).format(page=active_page + 1))

        keyboard_rows: list[list[InlineKeyboardButton]] = []

        async def _order_row_buttons(*, row_card: _CompactCareOrderRowCard) -> list[InlineKeyboardButton]:
            buttons = [
                InlineKeyboardButton(
                    text=i18n.t("patient.care.orders.open.action", locale),
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
                )
            ]
            order = await care_commerce_service.get_order(row_card.care_order_id)
            if order is not None and _is_live_care_order_status(order.status):
                buttons.append(
                    InlineKeyboardButton(
                        text=i18n.t("patient.care.orders.repeat.action", locale),
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
                    )
                )
            return buttons

        for row_card in current_cards:
            keyboard_rows.append(await _order_row_buttons(row_card=row_card))
        for row_card in history_cards:
            keyboard_rows.append(await _order_row_buttons(row_card=row_card))

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
        if end < len(history_rows):
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
        keyboard_rows.append([_care_catalog_nav_button(locale=locale)])
        keyboard_rows.append([InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")])

        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text="\n".join(lines),
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
        _ = mode
        locale = _locale()
        order = await care_commerce_service.get_order(care_order_id)
        if order is None or order.patient_id != patient_id:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="care",
                text=i18n.t("patient.care.order.card.not_found.panel", locale),
                keyboard=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=i18n.t("patient.care.order.result.open_orders", locale), callback_data="care:orders")],
                        [InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")],
                    ]
                ),
            )
            return

        row = await _build_care_order_row_card(clinic_id=clinic_id, actor_id=actor_id, order=order, locale=locale)
        status_badge = f"🟢 {row.status_label}" if _is_live_care_order_status(order.status) else f"⚪ {row.status_label}"
        next_step = i18n.t("patient.care.order.next_step", locale) if _is_live_care_order_status(order.status) else ""

        lines = [
            i18n.t("patient.care.order.card.title", locale),
            "",
            status_badge,
            "",
            f"{i18n.t('patient.care.order.card.field.items', locale)}: {row.item_summary}",
            f"{i18n.t('patient.care.order.card.field.branch', locale)}: {row.branch_label}",
            f"{i18n.t('patient.care.order.card.field.total', locale)}: {row.amount_label}",
            f"{i18n.t('patient.care.order.card.field.status', locale)}: {row.status_label}",
            f"{i18n.t('patient.care.order.card.field.ref', locale)}: {row.short_ref}",
        ]
        if row.pickup_hint:
            lines.extend(["", row.pickup_hint])
        if row.reservation_hint:
            lines.extend(["", row.reservation_hint])
        if next_step:
            lines.extend(["", next_step])

        buttons: list[list[InlineKeyboardButton]] = []
        if _is_live_care_order_status(order.status):
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.care.orders.repeat.action", locale),
                        callback_data=await _encode_runtime_callback(
                            profile=CardProfile.CARE_ORDER,
                            entity_type=EntityType.CARE_ORDER,
                            entity_id=order.care_order_id,
                            action=CardAction.RESERVE,
                            source_context=SourceContext.CARE_ORDER_LIST,
                            source_ref="care.orders.object.repeat",
                            page_or_index="repeat",
                            state_token=f"care:{actor_id}",
                        ),
                    )
                ]
            )
        buttons.append(
            [
                InlineKeyboardButton(
                    text=i18n.t("patient.care.orders.repeat.back_to_orders", locale),
                    callback_data=await _encode_runtime_callback(
                        profile=CardProfile.CARE_ORDER,
                        entity_type=EntityType.CARE_ORDER,
                        entity_id=order.care_order_id,
                        action=CardAction.BACK,
                        source_context=SourceContext.CARE_ORDER_LIST,
                        source_ref="care.orders.object.back",
                        page_or_index="back_orders",
                        state_token=f"care:{actor_id}",
                    ),
                )
            ]
        )
        buttons.append([InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")])

        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text="\n".join(lines),
            keyboard=InlineKeyboardMarkup(inline_keyboard=buttons),
        )


    async def _render_service_panel(message: Message | CallbackQuery, *, actor_id: int, session_id: str, clinic_id: str) -> None:
        locale = _locale()
        services = booking_flow.list_services(clinic_id=clinic_id)
        if not services:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.service.empty", locale),
                keyboard=InlineKeyboardMarkup(inline_keyboard=[[ _patient_home_nav_button(locale=locale) ]]),
            )
            return
        buttons: list[list[InlineKeyboardButton]] = []
        for svc in services[:8]:
            base_label = _resolve_service_label(
                service_title_key=svc.title_key,
                service_code=svc.code,
                fallback_id=svc.service_id,
                locale=locale,
                fallback_locale="en",
                i18n=i18n,
            )
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{_service_button_emoji(service_code=svc.code, service_title_key=svc.title_key)} {base_label}",
                        callback_data=f"book:svc:{session_id}:{svc.service_id}",
                    )
                ]
            )
        buttons.append(
            [
                InlineKeyboardButton(text=i18n.t("patient.home.nav.back", locale), callback_data="phome:home"),
                _patient_home_nav_button(locale=locale),
            ]
        )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=i18n.t("patient.booking.service.prompt", locale),
            keyboard=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

    async def _render_quick_booking_suggestion_panel(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        session_id: str,
        prefill: dict[str, str],
    ) -> None:
        locale = _locale()
        service_label = _resolve_service_label(
            service_title_key=prefill.get("service_title_key"),
            service_code=prefill.get("service_code"),
            fallback_id=prefill.get("service_label"),
            locale=locale,
            fallback_locale="en",
            i18n=i18n,
        )
        doctor_label = prefill.get("doctor_label") or i18n.t("patient.booking.review.value.missing", locale)
        branch_label = prefill.get("branch_label") or i18n.t("patient.booking.review.value.missing", locale)
        text = i18n.t("patient.booking.quick.panel", locale).format(
            service=service_label,
            doctor=doctor_label,
            branch=branch_label,
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=i18n.t("patient.booking.quick.repeat", locale), callback_data=f"qbook:repeat:{session_id}")],
                [InlineKeyboardButton(text=i18n.t("patient.booking.quick.same_doctor", locale), callback_data=f"qbook:same_doctor:{session_id}")],
                [InlineKeyboardButton(text=i18n.t("patient.booking.quick.other", locale), callback_data=f"qbook:other:{session_id}")],
                [_patient_home_nav_button(locale=locale)],
            ]
        )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=text,
            keyboard=keyboard,
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
        rows.append([InlineKeyboardButton(text=i18n.t("patient.booking.doctor.code.cta", locale), callback_data=f"book:doc_code:{session_id}")])
        rows.append(
            [
                InlineKeyboardButton(text=i18n.t("patient.home.nav.back", locale), callback_data=f"book:back:doctors:{session_id}"),
                _patient_home_nav_button(locale=locale),
            ]
        )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=i18n.t("patient.booking.doctor.prompt", locale),
            keyboard=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    async def _render_doctor_code_prompt(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        session_id: str,
        error_key: str | None = None,
    ) -> None:
        locale = _locale()
        text = i18n.t("patient.booking.doctor.code.prompt", locale)
        if error_key:
            text = f"{text}\n\n{i18n.t(error_key, locale)}"
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=text,
            keyboard=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text=i18n.t("patient.home.nav.back", locale), callback_data=f"book:back:doctors:{session_id}"),
                        _patient_home_nav_button(locale=locale),
                    ]
                ]
            ),
        )

    async def _render_slot_panel(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        session_id: str,
        prompt_key: str = "patient.booking.slot.prompt",
        notice_key: str | None = None,
        notice_text: str | None = None,
    ) -> None:
        locale = _locale()
        flow = await _load_flow_state(actor_id)
        flow.slot_time_window = _resolve_time_window(value=flow.slot_time_window)
        session = await booking_flow.get_booking_session(booking_session_id=session_id)
        if session is None:
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=session_id, text=i18n.t("patient.booking.session.missing", locale))
            return
        timezone_name = _resolve_booking_timezone_name(clinic_id=session.clinic_id, branch_id=session.branch_id)
        zone = _zone_or_utc(timezone_name)
        effective_date = _parse_iso_date(flow.slot_date_from) or datetime.now(zone).date()
        slots = await booking_flow.list_slots_for_session(booking_session_id=session_id, limit=SLOT_PREFETCH_LIMIT)
        filtered: list[tuple[Any, datetime]] = []
        for slot in slots:
            local_start = slot.start_at.astimezone(zone)
            if local_start.date() < effective_date:
                continue
            if not _match_slot_time_window(local_start=local_start, time_window=flow.slot_time_window):
                continue
            if slot.slot_id in flow.slot_suppressed_ids:
                continue
            filtered.append((slot, local_start))
        filtered.sort(key=lambda item: item[1])
        page_count = (len(filtered) + SLOT_PAGE_SIZE - 1) // SLOT_PAGE_SIZE if filtered else 1
        safe_page = min(max(flow.slot_page, 0), page_count - 1)
        if safe_page != flow.slot_page:
            flow.slot_page = safe_page
            await _save_flow_state(actor_id, flow)
        start = safe_page * SLOT_PAGE_SIZE
        page_items = filtered[start : start + SLOT_PAGE_SIZE]
        has_more = start + SLOT_PAGE_SIZE < len(filtered)

        rows: list[list[InlineKeyboardButton]] = []
        for slot, local_start in page_items:
            rows.append([InlineKeyboardButton(text=_slot_datetime_label(value=local_start, locale=locale), callback_data=f"book:slot:{slot.slot_id}")])
        if has_more:
            rows.append([InlineKeyboardButton(text=i18n.t("patient.booking.slot.more", locale), callback_data=f"book:slots:more:{session_id}")])
        rows.append(
            [
                InlineKeyboardButton(text=i18n.t("patient.booking.slot.another_date", locale), callback_data=f"book:slots:dates:{session_id}"),
                InlineKeyboardButton(text=i18n.t("patient.booking.slot.time_of_day", locale), callback_data=f"book:slots:windows:{session_id}"),
            ]
        )
        rows.append([InlineKeyboardButton(text=i18n.t("patient.booking.slot.change_doctor", locale), callback_data=f"book:back:doctors:{session_id}")])
        rows.append(
            [
                InlineKeyboardButton(text=i18n.t("patient.home.nav.back", locale), callback_data=f"book:back:doctors:{session_id}"),
                _patient_home_nav_button(locale=locale),
            ]
        )
        body_text = "\n".join(
            [
                i18n.t("patient.booking.slot.panel.title", locale),
                "",
                i18n.t("patient.booking.slot.panel.timezone_hint", locale),
                f"{i18n.t('patient.booking.slot.panel.date', locale)}: {_slot_date_label(value=effective_date, locale=locale)}",
                f"{i18n.t('patient.booking.slot.panel.time_window', locale)}: {i18n.t(f'patient.booking.slot.time_window.{flow.slot_time_window}', locale)}",
                "",
                i18n.t("patient.booking.slot.panel.choose", locale),
            ]
        )
        if not page_items:
            body_text = i18n.t("patient.booking.slot.empty.filtered", locale)
        notice_block = notice_text or (i18n.t(notice_key, locale) if notice_key else "")
        text = f"{notice_block}\n\n{body_text}" if notice_block else body_text
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=text,
            keyboard=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    async def _render_slot_date_picker_panel(message: Message | CallbackQuery, *, actor_id: int, session_id: str) -> None:
        locale = _locale()
        flow = await _load_flow_state(actor_id)
        session = await booking_flow.get_booking_session(booking_session_id=session_id)
        if session is None:
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=session_id, text=i18n.t("patient.booking.session.missing", locale))
            return
        zone = _zone_or_utc(_resolve_booking_timezone_name(clinic_id=session.clinic_id, branch_id=session.branch_id))
        start_date = _parse_iso_date(flow.slot_date_from) or datetime.now(zone).date()
        rows = [
            [
                InlineKeyboardButton(
                    text=_slot_date_label(value=start_date + timedelta(days=offset), locale=locale),
                    callback_data=f"book:slots:date:{session_id}:{(start_date + timedelta(days=offset)).isoformat()}",
                )
            ]
            for offset in range(SLOT_DATE_PICKER_DAYS)
        ]
        rows.append(
            [
                InlineKeyboardButton(text=i18n.t("patient.home.nav.back", locale), callback_data=f"book:slots:back:{session_id}"),
                _patient_home_nav_button(locale=locale),
            ]
        )
        text = "\n".join([i18n.t("patient.booking.slot.date_picker.title", locale), "", i18n.t("patient.booking.slot.date_picker.body", locale)])
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=text,
            keyboard=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    async def _render_slot_window_picker_panel(message: Message | CallbackQuery, *, actor_id: int, session_id: str) -> None:
        locale = _locale()
        windows = ("all", "morning", "day", "evening")
        rows = [
            [
                InlineKeyboardButton(
                    text=i18n.t(f"patient.booking.slot.time_window.{window}", locale),
                    callback_data=f"book:slots:window:{session_id}:{window}",
                )
            ]
            for window in windows
        ]
        rows.append(
            [
                InlineKeyboardButton(text=i18n.t("patient.home.nav.back", locale), callback_data=f"book:slots:back:{session_id}"),
                _patient_home_nav_button(locale=locale),
            ]
        )
        text = "\n".join([i18n.t("patient.booking.slot.time_window_picker.title", locale), "", i18n.t("patient.booking.slot.time_window_picker.body", locale)])
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=text,
            keyboard=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    async def _render_reschedule_review_panel(message: Message | CallbackQuery, *, actor_id: int, session_id: str) -> None:
        locale = _locale()
        flow = await _load_flow_state(actor_id)
        source_booking_id = flow.reschedule_booking_id
        if not source_booking_id:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.reschedule.start.unavailable", locale),
            )
            return
        source_booking = await booking_flow.get_booking(booking_id=source_booking_id)
        session = await booking_flow.get_booking_session(booking_session_id=session_id)
        if source_booking is None or session is None or not session.selected_slot_id:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.reschedule.start.unavailable", locale),
            )
            return
        if (
            source_booking.clinic_id != session.clinic_id
            or source_booking.patient_id != (session.resolved_patient_id or "")
            or source_booking.service_id != (session.service_id or "")
            or source_booking.doctor_id != (session.doctor_id or "")
            or source_booking.branch_id != (session.branch_id or "")
        ):
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.reschedule.start.unavailable", locale),
            )
            return
        fallback_locale = _fallback_locale_for_clinic(session.clinic_id)
        service = reference.get_service(session.clinic_id, session.service_id or "") if session.service_id else None
        service_label = _resolve_service_label(
            service_title_key=(service.title_key if service is not None else None),
            service_code=(service.code if service is not None else None),
            fallback_id=session.service_id,
            locale=locale,
            fallback_locale=fallback_locale,
            i18n=i18n,
        )
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
        timezone_name = _resolve_booking_timezone_name(clinic_id=session.clinic_id, branch_id=session.branch_id)
        current_time = _format_patient_datetime_line(
            source_booking.scheduled_start_at.astimezone(_zone_or_utc(timezone_name)),
            locale=locale,
        )
        selected_slot = await booking_flow.get_availability_slot(slot_id=session.selected_slot_id)
        new_time = i18n.t("patient.booking.review.value.missing", locale)
        if selected_slot is not None:
            new_time = _format_patient_datetime_line(
                selected_slot.start_at.astimezone(_zone_or_utc(timezone_name)),
                locale=locale,
            )
        text = i18n.t("patient.booking.reschedule.review.panel", locale).format(
            current_time=current_time,
            new_time=new_time,
            service=service_label,
            doctor=doctor_label,
            branch=branch_label,
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.booking.reschedule.review.confirm_cta", locale),
                        callback_data=f"rsch:confirm:{session_id}",
                    )
                ],
                [
                    InlineKeyboardButton(text=i18n.t("patient.home.nav.back", locale), callback_data=f"book:slots:back:{session_id}"),
                    _patient_home_nav_button(locale=locale),
                ],
            ]
        )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=text,
            keyboard=keyboard,
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
                fallback_id=None,
                locale=locale,
                fallback_locale=fallback_locale,
                i18n=i18n,
            )

        doctor_label = i18n.t("patient.booking.review.value.any_doctor", locale)
        if session.doctor_preference_type == "specific":
            doctor = reference.get_doctor(session.clinic_id, session.doctor_id or "") if session.doctor_id else None
            doctor_label = _resolve_reference_label(
                display_name=(doctor.display_name if doctor is not None else None),
                fallback_id=None,
                locale=locale,
                i18n=i18n,
            )

        branch = reference.get_branch(session.clinic_id, session.branch_id or "") if session.branch_id else None
        branch_label = _resolve_reference_label(
            display_name=(branch.display_name if branch is not None else None),
            fallback_id=None,
            locale=locale,
            i18n=i18n,
        )
        if branch_label == i18n.t("patient.booking.review.value.missing", locale):
            branch_label = i18n.t("patient.booking.review.field.branch_missing", locale)

        date_label = i18n.t("patient.booking.review.value.missing", locale)
        time_label = i18n.t("patient.booking.review.value.missing", locale)
        if session.selected_slot_id:
            slot = await booking_flow.get_availability_slot(slot_id=session.selected_slot_id)
            if slot is not None:
                timezone_name = _resolve_booking_timezone_name(clinic_id=session.clinic_id, branch_id=slot.branch_id or session.branch_id)
                date_label, time_label = _format_patient_datetime_parts(slot.start_at.astimezone(_zone_or_utc(timezone_name)), locale=locale)

        phone_label = (session.contact_phone_snapshot or "").strip() or i18n.t("patient.booking.review.field.phone_missing", locale)
        text = i18n.t("patient.booking.review.panel_v2", locale).format(
            service=service_label,
            doctor=doctor_label,
            date=date_label,
            time=time_label,
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
                ],
                [InlineKeyboardButton(text=i18n.t("patient.booking.review.edit.service", locale), callback_data=f"book:review:edit:service:{session_id}")],
                [InlineKeyboardButton(text=i18n.t("patient.booking.review.edit.doctor", locale), callback_data=f"book:review:edit:doctor:{session_id}")],
                [InlineKeyboardButton(text=i18n.t("patient.booking.review.edit.time", locale), callback_data=f"book:review:edit:time:{session_id}")],
                [InlineKeyboardButton(text=i18n.t("patient.booking.review.edit.phone", locale), callback_data=f"book:review:edit:phone:{session_id}")],
                [InlineKeyboardButton(text=i18n.t("patient.booking.review.back", locale), callback_data=f"book:review:back:{session_id}")],
                [_patient_home_nav_button(locale=locale)],
            ]
        )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=text,
            keyboard=keyboard,
        )

    def _resolve_patient_booking_status_label(*, status: str, locale: str) -> str:
        key = f"patient.booking.status.{status}"
        translated = i18n.t(key, locale)
        if translated and translated != key:
            return translated
        fallback = i18n.t("patient.booking.status.fallback", locale)
        return fallback.format(status=status.replace("_", " ").strip())

    async def _render_finalize_outcome(message: Message | CallbackQuery, *, actor_id: int, session_id: str, finalized) -> None:
        locale = _locale()
        if isinstance(finalized, OrchestrationSuccess):
            booking = finalized.entity
            clinic_fallback_locale = _fallback_locale_for_clinic(booking.clinic_id)
            service = reference.get_service(booking.clinic_id, booking.service_id)
            service_label = _resolve_service_label(
                service_title_key=(service.title_key if service is not None else None),
                service_code=(service.code if service is not None else None),
                fallback_id=None,
                locale=locale,
                fallback_locale=clinic_fallback_locale,
                i18n=i18n,
            )
            doctor = reference.get_doctor(booking.clinic_id, booking.doctor_id or "") if booking.doctor_id else None
            doctor_label = _resolve_reference_label(
                display_name=(doctor.display_name if doctor is not None else None),
                fallback_id=None,
                locale=locale,
                i18n=i18n,
            )
            branch = reference.get_branch(booking.clinic_id, booking.branch_id or "") if booking.branch_id else None
            branch_label = _resolve_reference_label(
                display_name=(branch.display_name if branch is not None else None),
                fallback_id=None,
                locale=locale,
                i18n=i18n,
            )
            if branch_label == i18n.t("patient.booking.review.value.missing", locale):
                branch_label = i18n.t("patient.booking.review.field.branch_missing", locale)
            timezone_name = _resolve_booking_timezone_name(clinic_id=booking.clinic_id, branch_id=booking.branch_id)
            date_label, time_label = _format_patient_datetime_parts(booking.scheduled_start_at.astimezone(_zone_or_utc(timezone_name)), locale=locale)
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.success.panel_v2", locale).format(
                    doctor=doctor_label,
                    service=service_label,
                    date=date_label,
                    time=time_label,
                    branch=branch_label,
                    status=_resolve_patient_booking_status_label(status=booking.status, locale=locale),
                    reminder_hint=i18n.t("patient.booking.success.reminder_hint", locale),
                ),
                keyboard=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=i18n.t("patient.home.action.my_booking", locale),
                        callback_data="phome:my_booking",
                    )],
                    [InlineKeyboardButton(
                        text=i18n.t("patient.home.back", locale),
                        callback_data="phome:home",
                    )],
                ]),
            )
            return
        if isinstance(finalized, InvalidStateOutcome):
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.finalize.failure.invalid.panel", locale),
                keyboard=InlineKeyboardMarkup(inline_keyboard=[[_patient_home_nav_button(locale=locale)]]),
            )
            return
        if isinstance(finalized, (SlotUnavailableOutcome, ConflictOutcome)):
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.finalize.failure.slot_unavailable.panel", locale),
                keyboard=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=i18n.t("patient.booking.finalize.failure.choose_another_time", locale), callback_data=f"book:slots:back:{session_id}")],
                        [_patient_home_nav_button(locale=locale)],
                    ]
                ),
            )
            return
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=i18n.t("patient.booking.escalated", locale),
            keyboard=InlineKeyboardMarkup(inline_keyboard=[[_patient_home_nav_button(locale=locale)]]),
        )

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

    def _patient_home_nav_button(*, locale: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(text=i18n.t("patient.home.nav.home", locale), callback_data="phome:home")

    def _care_entry_nav_keyboard(*, locale: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=i18n.t("patient.care.nav.my_booking", locale), callback_data="phome:my_booking")],
                [InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")],
            ]
        )

    def _care_catalog_nav_button(*, locale: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(text=i18n.t("patient.care.nav.open_catalog", locale), callback_data="phome:care")

    def _care_command_recovery_keyboard(
        *,
        locale: str,
        include_orders: bool = True,
        include_catalog: bool = True,
        include_my_booking: bool = False,
    ) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        if include_catalog:
            rows.append([InlineKeyboardButton(text=i18n.t("patient.care.command.nav.catalog", locale), callback_data="phome:care")])
        if include_orders:
            rows.append([InlineKeyboardButton(text=i18n.t("patient.care.command.nav.orders", locale), callback_data="care:orders")])
        if include_my_booking:
            rows.append([InlineKeyboardButton(text=i18n.t("patient.care.command.nav.my_booking", locale), callback_data="phome:my_booking")])
        rows.append([InlineKeyboardButton(text=i18n.t("patient.care.command.nav.home", locale), callback_data="phome:home")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def _recommendation_command_recovery_keyboard(
        *,
        locale: str,
        include_care_catalog: bool = False,
    ) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton(
                    text=i18n.t("patient.recommendations.command.nav.recommendations", locale),
                    callback_data="phome:recommendations",
                )
            ]
        ]
        if include_care_catalog:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.recommendations.command.nav.care_catalog", locale),
                        callback_data="phome:care",
                    )
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.recommendations.command.nav.my_booking", locale),
                        callback_data="phome:my_booking",
                    )
                ]
            )
        rows.append(
            [
                InlineKeyboardButton(
                    text=i18n.t("patient.recommendations.command.nav.home", locale),
                    callback_data="phome:home",
                )
            ]
        )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    async def _render_care_orders_patient_resolution_failed_panel(message: Message | CallbackQuery, *, actor_id: int) -> None:
        locale = _locale()
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=i18n.t("patient.care.orders.patient_resolution_failed.panel", locale),
            keyboard=_care_entry_nav_keyboard(locale=locale),
        )

    async def _render_care_reserve_patient_resolution_failed_panel(message: Message | CallbackQuery, *, actor_id: int) -> None:
        locale = _locale()
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=i18n.t("patient.care.reserve.patient_resolution_failed.panel", locale),
            keyboard=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=i18n.t("patient.care.nav.my_booking", locale), callback_data="phome:my_booking")],
                    [_care_catalog_nav_button(locale=locale)],
                    [InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")],
                ]
            ),
        )

    async def _render_recommendations_patient_resolution_failed_panel(message: Message | CallbackQuery, *, actor_id: int) -> None:
        locale = _locale()
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="patient_home",
            text=i18n.t("patient.recommendations.patient_resolution_failed.panel", locale),
            keyboard=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=i18n.t("patient.recommendations.nav.my_booking", locale), callback_data="phome:my_booking")],
                    [InlineKeyboardButton(text=i18n.t("patient.recommendations.nav.home", locale), callback_data="phome:home")],
                ]
            ),
        )

    async def _render_care_product_missing_panel(message: Message | CallbackQuery, *, actor_id: int) -> None:
        locale = _locale()
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=i18n.t("patient.care.product.missing.panel", locale),
            keyboard=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=i18n.t("patient.care.products.open_catalog", locale), callback_data="phome:care")],
                    [InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")],
                ]
            ),
        )

    async def _render_recommendation_products_recovery_panel(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        recommendation_id: str,
        text_key: str,
    ) -> None:
        locale = _locale()
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=i18n.t(text_key, locale),
            keyboard=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=i18n.t("patient.care.products.back_to_recommendation", locale),
                            callback_data=f"prec:open:{recommendation_id}",
                        )
                    ],
                    [InlineKeyboardButton(text=i18n.t("patient.care.products.open_catalog", locale), callback_data="phome:care")],
                    [InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")],
                ]
            ),
        )

    async def _render_care_order_created_panel(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        clinic_id: str,
        order: Any,
        product: Any,
        branch_id: str,
    ) -> None:
        locale = _locale()
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="care",
            text=i18n.t("patient.care.order.result.panel", locale).format(
                product=i18n.t(product.title_key, locale),
                branch=_resolve_care_order_branch_label(clinic_id=clinic_id, branch_id=branch_id, locale=locale),
                status=i18n.t("patient.care.order.result.status.confirmed", locale),
                next_step=i18n.t("patient.care.order.next_step", locale),
            ),
            keyboard=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=i18n.t("patient.care.order.result.open_current", locale), callback_data=f"careo:open:{order.care_order_id}")],
                    [InlineKeyboardButton(text=i18n.t("patient.care.order.result.open_orders", locale), callback_data="care:orders")],
                    [InlineKeyboardButton(text=i18n.t("patient.care.order.result.open_catalog", locale), callback_data="phome:care")],
                    [InlineKeyboardButton(text=i18n.t("patient.care.nav.home", locale), callback_data="phome:home")],
                ]
            ),
        )

    def _patient_back_nav_text(*, locale: str) -> str:
        return i18n.t("patient.home.nav.back", locale)

    def _patient_contact_reply_keyboard(*, locale: str, include_back: bool) -> ReplyKeyboardMarkup:
        rows: list[list[KeyboardButton]] = [[KeyboardButton(text=i18n.t("patient.booking.contact.share", locale), request_contact=True)]]
        nav_row: list[KeyboardButton] = []
        if include_back:
            nav_row.append(KeyboardButton(text=_patient_back_nav_text(locale=locale)))
        nav_row.append(KeyboardButton(text=i18n.t("patient.home.nav.home", locale)))
        rows.append(nav_row)
        return ReplyKeyboardMarkup(
            keyboard=rows,
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    async def _remove_patient_reply_keyboard(message: Message) -> None:
        try:
            cleanup = await message.answer("↩️", reply_markup=ReplyKeyboardRemove())
            try:
                await cleanup.delete()
            except Exception:
                pass
        except Exception:
            pass

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
        if await _resume_active_reschedule_context(
            message,
            actor_id=actor_id,
            clinic_id=clinic_id,
            on_stale_key="patient.booking.reschedule.start.unavailable",
        ):
            return
        trusted_patient_id, trusted_phone = await _resolve_trusted_returning_patient_identity(actor_id)
        started = await booking_flow.start_or_resume_returning_patient_booking(
            clinic_id=clinic_id,
            telegram_user_id=actor_id,
            trusted_patient_id=trusted_patient_id,
            trusted_phone_snapshot=trusted_phone,
        )
        flow = await _load_flow_state(actor_id)
        flow.booking_session_id = started.booking_session.booking_session_id
        flow.booking_mode = "new_booking_flow"
        flow.reschedule_booking_id = ""
        flow.quick_booking_prefill = {}
        _reset_slot_view_state(flow)
        if started.trusted_shortcut_applied and trusted_patient_id:
            recent_prefill = await booking_flow.get_recent_booking_prefill(clinic_id=clinic_id, patient_id=trusted_patient_id)
            if recent_prefill is not None:
                flow.quick_booking_prefill = {
                    "service_id": recent_prefill.service_id,
                    "doctor_id": recent_prefill.doctor_id,
                    "branch_id": recent_prefill.branch_id,
                    "service_title_key": recent_prefill.service_title_key or "",
                    "service_code": recent_prefill.service_code or "",
                    "service_label": recent_prefill.service_label or "",
                    "doctor_label": recent_prefill.doctor_label or "",
                    "branch_label": recent_prefill.branch_label or "",
                }
                await _save_flow_state(actor_id, flow)
                await _render_quick_booking_suggestion_panel(
                    message,
                    actor_id=actor_id,
                    session_id=started.booking_session.booking_session_id,
                    prefill=flow.quick_booking_prefill,
                )
                return
        await _save_flow_state(actor_id, flow)
        await _render_resume_panel(message, actor_id=actor_id, session_id=started.booking_session.booking_session_id, clinic_id=clinic_id)

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
        if await _resume_active_reschedule_context(
            message,
            actor_id=actor_id,
            clinic_id=clinic_id,
            on_stale_key="patient.booking.reschedule.start.unavailable",
        ):
            return

        direct_result = await _try_resolve_existing_booking_shortcut(clinic_id=clinic_id, actor_id=actor_id)
        if direct_result is not None:
            await _show_existing_booking_result(message, actor_id=actor_id, result=direct_result)
            return

        session = await booking_flow.start_or_resume_existing_booking_session(clinic_id=clinic_id, telegram_user_id=actor_id)
        flow = await _load_flow_state(actor_id)
        flow.booking_session_id = session.booking_session_id
        flow.booking_mode = "existing_lookup_contact"
        flow.reschedule_booking_id = ""
        _reset_slot_suppression(flow)
        await _save_flow_state(actor_id, flow)
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session.booking_session_id,
            text=i18n.t("patient.booking.my.contact_prompt", _locale()),
            reply_keyboard=_patient_contact_reply_keyboard(locale=_locale(), include_back=False),
        )

    async def _enter_recommendations_list(message: Message | CallbackQuery, *, actor_id: int) -> None:
        locale = _locale()
        entry_nav_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.recommendations.nav.my_booking", locale),
                        callback_data="phome:my_booking",
                    )
                ],
                [InlineKeyboardButton(text=i18n.t("patient.recommendations.nav.home", locale), callback_data="phome:home")],
            ]
        )
        if recommendation_service is None:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.recommendations.unavailable.panel", locale),
                keyboard=entry_nav_keyboard,
            )
            return
        patient_id = await _resolve_patient_id_for_user(actor_id)
        if not patient_id:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.recommendations.patient_resolution_failed.panel", locale),
                keyboard=entry_nav_keyboard,
            )
            return
        rows = await recommendation_service.list_for_patient(patient_id=patient_id)
        await _render_recommendations_panel(
            actor_id=actor_id,
            message=message,
            session_id="patient_home",
            rows=rows,
        )

    def _recommendation_type_label(*, recommendation_type: str, locale: str) -> str:
        key = f"patient.recommendations.type.{recommendation_type}"
        translated = i18n.t(key, locale)
        if translated != key:
            return translated
        return recommendation_type.replace("_", " ").strip().title() or i18n.t("patient.booking.review.value.missing", locale)

    def _recommendation_status_label(*, status: str, locale: str) -> str:
        key = f"patient.recommendations.status.{status}"
        translated = i18n.t(key, locale)
        if translated != key:
            return translated
        return status.replace("_", " ").strip().title() or i18n.t("patient.booking.review.value.missing", locale)

    def _recommendation_value_or_missing(value: str | None, *, locale: str) -> str:
        trusted = (value or "").strip()
        return trusted or i18n.t("patient.recommendations.detail.value_missing", locale)

    def _recommendation_readable_body(body: str | None, *, locale: str) -> str:
        trusted = _recommendation_value_or_missing(body, locale=locale)
        if trusted == i18n.t("patient.recommendations.detail.value_missing", locale):
            return trusted
        max_len = 1200
        if len(trusted) <= max_len:
            return trusted
        suffix = i18n.t("patient.recommendations.detail.body_trimmed_suffix", locale)
        return f"{trusted[:max_len].rstrip()}\n\n{suffix}"

    def _recommendation_is_terminal(status: str) -> bool:
        return status in _TERMINAL_RECOMMENDATION_STATUSES

    def _recommendation_status_badge(*, status: str, locale: str) -> str:
        key = f"patient.recommendations.detail.status_badge.{status}"
        translated = i18n.t(key, locale)
        if translated != key:
            return translated
        return _recommendation_status_label(status=status, locale=locale)

    def _recommendation_next_step(*, status: str, locale: str) -> str:
        key = f"patient.recommendations.detail.next.{status}"
        translated = i18n.t(key, locale)
        if translated != key:
            return translated
        return ""

    def _recommendation_action_buttons_for_status(*, recommendation: Any, locale: str) -> list[list[InlineKeyboardButton]]:
        status = (getattr(recommendation, "status", "") or "").strip()
        rows: list[list[InlineKeyboardButton]] = []
        if _recommendation_is_terminal(status):
            return rows
        mutation_buttons: list[InlineKeyboardButton] = []
        if status in {"issued", "viewed"}:
            mutation_buttons.append(
                InlineKeyboardButton(
                    text=i18n.t("patient.recommendations.action.ack.button", locale),
                    callback_data=f"prec:act:ack:{recommendation.recommendation_id}",
                )
            )
        if status in {"issued", "viewed", "acknowledged"}:
            mutation_buttons.extend(
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.recommendations.action.accept.button", locale),
                        callback_data=f"prec:act:accept:{recommendation.recommendation_id}",
                    ),
                    InlineKeyboardButton(
                        text=i18n.t("patient.recommendations.action.decline.button", locale),
                        callback_data=f"prec:act:decline:{recommendation.recommendation_id}",
                    ),
                ]
            )
        if mutation_buttons:
            rows.append(mutation_buttons)
        return rows

    async def _recommendation_detail_keyboard(*, recommendation: Any, locale: str) -> InlineKeyboardMarkup:
        rows = _recommendation_action_buttons_for_status(recommendation=recommendation, locale=locale)
        products_allowed = recommendation.status not in {"withdrawn", "expired"}
        if products_allowed and await _has_recommendation_products_target(recommendation=recommendation):
            rows.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.recommendations.action.products.button", locale),
                        callback_data=f"prec:products:{recommendation.recommendation_id}",
                    )
                ]
            )
        rows.append([InlineKeyboardButton(text=i18n.t("patient.recommendations.nav.back_to_list", locale), callback_data="phome:recommendations")])
        rows.append([InlineKeyboardButton(text=i18n.t("patient.recommendations.nav.home", locale), callback_data="phome:home")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def _recommendation_not_found_keyboard(*, locale: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=i18n.t("patient.recommendations.command.nav.recommendations", locale), callback_data="phome:recommendations")],
                [InlineKeyboardButton(text=i18n.t("patient.recommendations.command.nav.my_booking", locale), callback_data="phome:my_booking")],
                [InlineKeyboardButton(text=i18n.t("patient.recommendations.command.nav.home", locale), callback_data="phome:home")],
            ]
        )

    def _pick_latest_recommendation(rows: list[Any]) -> tuple[Any, list[Any]]:
        if not rows:
            return None, []
        latest = next((row for row in rows if row.status not in _TERMINAL_RECOMMENDATION_STATUSES), rows[0])
        history = [row for row in rows if row.recommendation_id != latest.recommendation_id]
        return latest, history

    async def _has_recommendation_products_target(*, recommendation: Any) -> bool:
        if care_commerce_service is None:
            return False
        try:
            resolution = await care_commerce_service.resolve_recommendation_target_result(
                clinic_id=_primary_clinic_id() or recommendation.clinic_id,
                recommendation_id=recommendation.recommendation_id,
                recommendation_type=recommendation.recommendation_type,
                locale=_locale(),
            )
        except Exception:
            return False
        return bool(resolution.products)

    def _parse_recommendation_callback_data(
        *,
        raw_data: str,
        expected_prefix: str,
        expected_parts: int,
    ) -> list[str] | None:
        parts = raw_data.split(":", expected_parts - 1)
        if len(parts) != expected_parts:
            return None
        if ":".join(parts[:2]) != expected_prefix:
            return None
        if not all(part.strip() for part in parts[2:]):
            return None
        return parts

    async def _render_recommendation_detail_panel(
        *,
        message: Message | CallbackQuery,
        actor_id: int,
        recommendation: Any,
        session_id: str = "patient_home",
    ) -> None:
        locale = _locale()
        status_key = (recommendation.status or "").strip()
        type_label = _recommendation_type_label(recommendation_type=recommendation.recommendation_type, locale=locale)
        status_label = _recommendation_status_label(status=status_key, locale=locale)
        status_badge = _recommendation_status_badge(status=status_key, locale=locale)
        next_step = _recommendation_next_step(status=status_key, locale=locale)
        next_step_block = f"\n\n{next_step}" if next_step else ""
        text = i18n.t("patient.recommendations.detail.card", locale).format(
            panel_title=i18n.t("patient.recommendations.detail.title", locale),
            status_badge=status_badge,
            topic_field=i18n.t("patient.recommendations.detail.field.topic", locale),
            type_field=i18n.t("patient.recommendations.detail.field.type", locale),
            status_field=i18n.t("patient.recommendations.detail.field.status", locale),
            title_value=_recommendation_value_or_missing(recommendation.title, locale=locale),
            recommendation_type=type_label,
            status=status_label,
            body=_recommendation_readable_body(recommendation.body_text, locale=locale),
            next_step_optional=next_step_block,
        )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=text,
            keyboard=await _recommendation_detail_keyboard(recommendation=recommendation, locale=locale),
        )

    async def _render_recommendation_not_found_panel(message: Message | CallbackQuery, *, actor_id: int) -> None:
        locale = _locale()
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id="patient_home",
            text=i18n.t("patient.recommendations.command.not_found.panel", locale),
            keyboard=_recommendation_not_found_keyboard(locale=locale),
        )

    async def _render_recommendations_panel(
        *,
        actor_id: int,
        message: Message | CallbackQuery,
        session_id: str,
        rows: list[Any],
    ) -> None:
        locale = _locale()
        if not rows:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.recommendations.empty.panel", locale),
                keyboard=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=i18n.t("patient.recommendations.nav.my_booking", locale), callback_data="phome:my_booking")],
                        [InlineKeyboardButton(text=i18n.t("patient.recommendations.nav.home", locale), callback_data="phome:home")],
                    ]
                ),
            )
            return
        latest, history = _pick_latest_recommendation(rows)
        if latest is None:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.recommendations.empty.panel", locale),
                keyboard=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=i18n.t("patient.recommendations.nav.my_booking", locale), callback_data="phome:my_booking")],
                        [InlineKeyboardButton(text=i18n.t("patient.recommendations.nav.home", locale), callback_data="phome:home")],
                    ]
                ),
            )
            return
        lines = [
            i18n.t("patient.recommendations.title", locale),
            "",
            i18n.t("patient.recommendations.latest.label", locale),
            f"• {latest.title}",
            i18n.t("patient.recommendations.summary.line", locale).format(
                recommendation_type=_recommendation_type_label(recommendation_type=latest.recommendation_type, locale=locale),
                status=_recommendation_status_label(status=latest.status, locale=locale),
            ),
        ]
        if history:
            lines.extend(["", i18n.t("patient.recommendations.history.label", locale)])
            for index, row in enumerate(history[:5], start=1):
                lines.append(
                    i18n.t("patient.recommendations.history.item", locale).format(
                        index=index,
                        title=row.title,
                        status=_recommendation_status_label(status=row.status, locale=locale),
                    )
                )
        keyboard_rows: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton(
                    text=i18n.t("patient.recommendations.open_latest.button", locale),
                    callback_data=f"prec:open:{latest.recommendation_id}",
                )
            ]
        ]
        for index, row in enumerate(history[:5], start=1):
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.recommendations.open_history.button", locale).format(index=index),
                        callback_data=f"prec:open:{row.recommendation_id}",
                    )
                ]
            )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text="\n".join(lines),
            keyboard=InlineKeyboardMarkup(inline_keyboard=[*keyboard_rows, [_patient_home_nav_button(locale=locale)]]),
        )

    async def _resume_active_reschedule_context(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        clinic_id: str,
        on_stale_key: str,
    ) -> bool:
        flow = await _load_flow_state(actor_id)
        if flow.booking_mode != "reschedule_booking_control" or not flow.booking_session_id:
            return False
        callback_session_id = flow.booking_session_id
        is_active = await booking_flow.validate_active_session_callback(
            clinic_id=clinic_id,
            telegram_user_id=actor_id,
            callback_session_id=callback_session_id,
            allowed_route_types=RESCHEDULE_BOOKING_CONTROL_ROUTE_TYPES,
        )
        session = await booking_flow.get_booking_session(booking_session_id=callback_session_id)
        if is_active and session is not None and session.route_type in RESCHEDULE_BOOKING_CONTROL_ROUTE_TYPES:
            if session.selected_slot_id:
                await _render_reschedule_review_panel(message, actor_id=actor_id, session_id=callback_session_id)
            else:
                await _render_reschedule_start_panel(message, actor_id=actor_id, session_id=callback_session_id)
            return True
        flow.booking_mode = "new_booking_flow"
        flow.booking_session_id = ""
        flow.reschedule_booking_id = ""
        await _save_flow_state(actor_id, flow)
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=f"reschedule_stale:{actor_id}",
            text=i18n.t(on_stale_key, _locale()),
        )
        return False

    async def _enter_care_catalog(message: Message | CallbackQuery, *, actor_id: int) -> None:
        if care_commerce_service is None:
            locale = _locale()
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.care.unavailable.panel", locale),
                keyboard=_care_entry_nav_keyboard(locale=locale),
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

    async def _resolve_trusted_returning_patient_identity(telegram_user_id: int) -> tuple[str | None, str | None]:
        clinic_id = _primary_clinic_id()
        if clinic_id is None or recommendation_repository is None:
            return None, None
        patient_id = await _resolve_patient_id_for_user(telegram_user_id)
        if not patient_id:
            return None, None
        phone_finder = getattr(recommendation_repository, "find_primary_phone_by_patient", None)
        if not callable(phone_finder):
            return None, None
        try:
            phone = await phone_finder(clinic_id=clinic_id, patient_id=patient_id)
        except Exception:
            return None, None
        if not isinstance(phone, str):
            return None, None
        trusted_phone = phone.strip()
        if not trusted_phone:
            return None, None
        return patient_id, trusted_phone

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
        locale = _locale()
        if len(parts) != 2:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.recommendations.command.open.usage.panel", locale),
                keyboard=_recommendation_command_recovery_keyboard(locale=locale),
            )
            return
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        if not patient_id:
            await _render_recommendations_patient_resolution_failed_panel(message, actor_id=message.from_user.id)
            return
        recommendation = await recommendation_service.get(parts[1].strip())
        if recommendation is None or recommendation.patient_id != patient_id:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.recommendations.command.not_found.panel", locale),
                keyboard=_recommendation_command_recovery_keyboard(locale=locale),
            )
            return
        if recommendation.status == "issued":
            recommendation = await recommendation_service.mark_viewed(recommendation_id=recommendation.recommendation_id)
        if recommendation is None:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.recommendations.command.not_found.panel", locale),
                keyboard=_recommendation_command_recovery_keyboard(locale=locale),
            )
            return
        await _render_recommendation_detail_panel(
            message=message,
            actor_id=message.from_user.id,
            recommendation=recommendation,
            session_id="patient_home",
        )

    @router.message(Command("recommendation_action"))
    async def recommendations_action(message: Message) -> None:
        if not message.from_user or not message.text or recommendation_service is None:
            return
        locale = _locale()
        parts = message.text.split(maxsplit=3)
        if len(parts) != 3:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.recommendations.command.action.usage.panel", locale),
                keyboard=_recommendation_command_recovery_keyboard(locale=locale),
            )
            return
        action = parts[1].strip()
        recommendation_id = parts[2].strip()
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        if not patient_id:
            await _render_recommendations_patient_resolution_failed_panel(message, actor_id=message.from_user.id)
            return
        recommendation = await recommendation_service.get(recommendation_id)
        if recommendation is None or recommendation.patient_id != patient_id:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.recommendations.command.not_found.panel", locale),
                keyboard=_recommendation_command_recovery_keyboard(locale=locale),
            )
            return
        try:
            if action == "ack":
                updated = await recommendation_service.acknowledge(recommendation_id=recommendation_id)
            elif action == "accept":
                updated = await recommendation_service.accept(recommendation_id=recommendation_id)
            elif action == "decline":
                updated = await recommendation_service.decline(recommendation_id=recommendation_id)
            else:
                await _send_or_edit_panel(
                    actor_id=message.from_user.id,
                    message=message,
                    session_id="patient_home",
                    text=i18n.t("patient.recommendations.command.action.usage.panel", locale),
                    keyboard=_recommendation_command_recovery_keyboard(locale=locale),
                )
                return
        except ValueError:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.recommendations.command.action.invalid_state.panel", locale),
                keyboard=_recommendation_command_recovery_keyboard(locale=locale),
            )
            return
        resolved = updated or recommendation
        if resolved is None:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.recommendations.command.not_found.panel", locale),
                keyboard=_recommendation_command_recovery_keyboard(locale=locale),
            )
            return
        await _render_recommendation_detail_panel(
            message=message,
            actor_id=message.from_user.id,
            recommendation=resolved,
            session_id="patient_home",
        )

    @router.message(Command("recommendation_products"))
    async def recommendation_products(message: Message) -> None:
        if not message.from_user or not message.text or recommendation_service is None or care_commerce_service is None:
            return
        locale = _locale()
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="care",
                text=i18n.t("patient.recommendations.command.products.usage.panel", locale),
                keyboard=_recommendation_command_recovery_keyboard(locale=locale, include_care_catalog=True),
            )
            return
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        if not patient_id:
            await _render_recommendations_patient_resolution_failed_panel(message, actor_id=message.from_user.id)
            return
        recommendation = await recommendation_service.get(parts[1].strip())
        if recommendation is None or recommendation.patient_id != patient_id:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="patient_home",
                text=i18n.t("patient.recommendations.command.not_found.panel", locale),
                keyboard=_recommendation_command_recovery_keyboard(locale=locale),
            )
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
            await _render_recommendation_products_recovery_panel(
                message,
                actor_id=message.from_user.id,
                recommendation_id=recommendation.recommendation_id,
                text_key="patient.care.products.manual_target_invalid.panel",
            )
            return
        resolved = resolution.products
        if not resolved:
            await _render_recommendation_products_recovery_panel(
                message,
                actor_id=message.from_user.id,
                recommendation_id=recommendation.recommendation_id,
                text_key="patient.care.products.empty.panel",
            )
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
        locale = _locale()
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="care",
                text=i18n.t("patient.care.command.product_open.usage.panel", locale),
                keyboard=_care_command_recovery_keyboard(locale=locale),
            )
            return
        clinic_id = _primary_clinic_id()
        if clinic_id is None:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="care",
                text=i18n.t("patient.care.command.clinic_unavailable.panel", locale),
                keyboard=_care_command_recovery_keyboard(locale=locale, include_orders=False, include_catalog=False),
            )
            return
        await _render_product_card(message, actor_id=message.from_user.id, clinic_id=clinic_id, product_id=parts[1].strip())

    @router.message(Command("care_order_create"))
    async def care_order_create(message: Message) -> None:
        if not message.from_user or not message.text or recommendation_service is None or care_commerce_service is None:
            return
        locale = _locale()
        parts = message.text.split(maxsplit=3)
        if len(parts) != 4:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="care",
                text=i18n.t("patient.care.command.order_create.usage.panel", locale),
                keyboard=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=i18n.t("patient.care.command.nav.recommendations", locale), callback_data="phome:recommendations")],
                        [InlineKeyboardButton(text=i18n.t("patient.care.command.nav.catalog", locale), callback_data="phome:care")],
                        [InlineKeyboardButton(text=i18n.t("patient.care.command.nav.orders", locale), callback_data="care:orders")],
                        [InlineKeyboardButton(text=i18n.t("patient.care.command.nav.home", locale), callback_data="phome:home")],
                    ]
                ),
            )
            return
        recommendation_id, care_product_id, pickup_branch_id = parts[1], parts[2], parts[3]
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        clinic_id = _primary_clinic_id()
        if not patient_id or clinic_id is None:
            await _render_care_reserve_patient_resolution_failed_panel(message, actor_id=message.from_user.id)
            return
        recommendation = await recommendation_service.get(recommendation_id)
        if recommendation is None or recommendation.patient_id != patient_id:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="care",
                text=i18n.t("patient.recommendations.command.not_found.panel", locale),
                keyboard=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=i18n.t("patient.care.command.nav.recommendations", locale), callback_data="phome:recommendations")],
                        [InlineKeyboardButton(text=i18n.t("patient.care.command.nav.my_booking", locale), callback_data="phome:my_booking")],
                        [InlineKeyboardButton(text=i18n.t("patient.care.command.nav.home", locale), callback_data="phome:home")],
                    ]
                ),
            )
            return
        branches = reference.list_branches(clinic_id)
        if not any(branch.branch_id == pickup_branch_id for branch in branches):
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="care",
                text=i18n.t("patient.care.command.order_create.branch_invalid.panel", locale),
                keyboard=_care_command_recovery_keyboard(locale=locale, include_orders=False),
            )
            return
        linked_resolution = await care_commerce_service.resolve_recommendation_target_result(
            clinic_id=clinic_id,
            recommendation_id=recommendation_id,
            recommendation_type=recommendation.recommendation_type,
            locale=locale,
        )
        linked = linked_resolution.products
        match = None
        for item in linked:
            if item.care_product_id != care_product_id:
                continue
            maybe_product = getattr(item, "product", None)
            if maybe_product is not None:
                match = maybe_product
                break
            match = await care_commerce_service.repository.get_product(care_product_id)
            break
        if match is None:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="care",
                text=i18n.t("patient.care.command.order_create.product_not_linked.panel", locale),
                keyboard=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=i18n.t("patient.care.products.open_for_recommendation", locale),
                                callback_data=f"prec:products:{recommendation_id}",
                            )
                        ],
                        [InlineKeyboardButton(text=i18n.t("patient.care.command.nav.catalog", locale), callback_data="phome:care")],
                        [InlineKeyboardButton(text=i18n.t("patient.care.command.nav.home", locale), callback_data="phome:home")],
                    ]
                ),
            )
            return
        free_qty = await care_commerce_service.compute_free_qty(branch_id=pickup_branch_id, care_product_id=match.care_product_id)
        if free_qty < 1:
            content = await care_commerce_service.resolve_product_content(
                clinic_id=clinic_id,
                product=match,
                locale=locale,
                fallback_locale=locale,
            )
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="care",
                text=i18n.t("patient.care.order.out_of_stock.panel", locale).format(
                    product=content.title or i18n.t(match.title_key, locale),
                    branch=_resolve_care_order_branch_label(clinic_id=clinic_id, branch_id=pickup_branch_id, locale=locale),
                ),
                keyboard=_care_command_recovery_keyboard(locale=locale, include_orders=False),
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
        await _render_care_order_created_panel(
            message,
            actor_id=message.from_user.id,
            clinic_id=clinic_id,
            order=order,
            product=match,
            branch_id=pickup_branch_id,
        )

    @router.message(Command("care_orders"))
    async def care_orders(message: Message) -> None:
        if not message.from_user or care_commerce_service is None:
            return
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        clinic_id = _primary_clinic_id()
        if not patient_id or clinic_id is None:
            await _render_care_orders_patient_resolution_failed_panel(message, actor_id=message.from_user.id)
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
        locale = _locale()
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await _send_or_edit_panel(
                actor_id=message.from_user.id,
                message=message,
                session_id="care",
                text=i18n.t("patient.care.command.order_repeat.usage.panel", locale),
                keyboard=_care_command_recovery_keyboard(locale=locale),
            )
            return
        clinic_id = _primary_clinic_id()
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        if clinic_id is None or patient_id is None:
            await _render_care_orders_patient_resolution_failed_panel(message, actor_id=message.from_user.id)
            return
        care_order_id = parts[1].strip()
        view = await _reserve_again_from_order(clinic_id=clinic_id, patient_id=patient_id, care_order_id=care_order_id)
        await _send_or_edit_panel(
            actor_id=message.from_user.id,
            message=message,
            session_id="care",
            text=view.text,
            keyboard=await _repeat_action_keyboard(actor_id=message.from_user.id, care_order_id=care_order_id, view=view),
        )

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

    @router.callback_query(F.data == "phome:my_booking")
    async def patient_home_my_booking(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        await _enter_existing_booking_lookup(callback, actor_id=callback.from_user.id)

    @router.callback_query(F.data == "phome:home")
    async def patient_home_main(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        await _render_patient_home_panel(callback, actor_id=callback.from_user.id)

    @router.callback_query(F.data == "phome:recommendations")
    async def patient_home_recommendations(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        await _enter_recommendations_list(callback, actor_id=callback.from_user.id)

    @router.callback_query(F.data.startswith("prec:open:"))
    async def recommendation_open_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data or recommendation_service is None:
            return
        parts = _parse_recommendation_callback_data(
            raw_data=callback.data,
            expected_prefix="prec:open",
            expected_parts=3,
        )
        if parts is None:
            await callback.answer(i18n.t("patient.recommendations.callback.unavailable", _locale()), show_alert=True)
            return
        recommendation_id = parts[2]
        patient_id = await _resolve_patient_id_for_user(callback.from_user.id)
        if not patient_id:
            await _render_recommendations_patient_resolution_failed_panel(callback, actor_id=callback.from_user.id)
            return
        recommendation = await recommendation_service.get(recommendation_id)
        if recommendation is None or recommendation.patient_id != patient_id:
            await _render_recommendation_not_found_panel(callback, actor_id=callback.from_user.id)
            return
        if recommendation.status == "issued":
            recommendation = await recommendation_service.mark_viewed(recommendation_id=recommendation.recommendation_id)
        if recommendation is None:
            await _render_recommendation_not_found_panel(callback, actor_id=callback.from_user.id)
            return
        await _render_recommendation_detail_panel(
            message=callback,
            actor_id=callback.from_user.id,
            recommendation=recommendation,
        )

    @router.callback_query(F.data.startswith("prec:act:"))
    async def recommendation_action_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data or recommendation_service is None:
            return
        parts = _parse_recommendation_callback_data(
            raw_data=callback.data,
            expected_prefix="prec:act",
            expected_parts=4,
        )
        if parts is None:
            await callback.answer(i18n.t("patient.recommendations.callback.unavailable", _locale()), show_alert=True)
            return
        action, recommendation_id = parts[2], parts[3]
        patient_id = await _resolve_patient_id_for_user(callback.from_user.id)
        recommendation = await recommendation_service.get(recommendation_id)
        if not patient_id or recommendation is None or recommendation.patient_id != patient_id:
            await callback.answer(i18n.t("patient.recommendations.not_found", _locale()), show_alert=True)
            return
        try:
            if action == "ack":
                updated = await recommendation_service.acknowledge(recommendation_id=recommendation_id)
            elif action == "accept":
                updated = await recommendation_service.accept(recommendation_id=recommendation_id)
            elif action == "decline":
                updated = await recommendation_service.decline(recommendation_id=recommendation_id)
            else:
                await callback.answer(i18n.t("patient.recommendations.callback.unavailable", _locale()), show_alert=True)
                return
        except ValueError:
            await _render_recommendation_detail_panel(
                message=callback,
                actor_id=callback.from_user.id,
                recommendation=recommendation,
            )
            await callback.answer(i18n.t("patient.recommendations.action.invalid_state", _locale()), show_alert=True)
            return
        resolved = updated or recommendation
        if resolved is None:
            await callback.answer(i18n.t("patient.recommendations.not_found", _locale()), show_alert=True)
            return
        await _render_recommendation_detail_panel(
            message=callback,
            actor_id=callback.from_user.id,
            recommendation=resolved,
        )
        await callback.answer(i18n.t("patient.recommendations.action.ok", _locale()).format(status=_recommendation_status_label(status=resolved.status, locale=_locale())))

    @router.callback_query(F.data.startswith("prec:products:"))
    async def recommendation_products_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data or recommendation_service is None or care_commerce_service is None:
            return
        parts = _parse_recommendation_callback_data(
            raw_data=callback.data,
            expected_prefix="prec:products",
            expected_parts=3,
        )
        if parts is None:
            await callback.answer(i18n.t("patient.recommendations.callback.unavailable", _locale()), show_alert=True)
            return
        recommendation_id = parts[2]
        patient_id = await _resolve_patient_id_for_user(callback.from_user.id)
        if not patient_id:
            await _render_recommendations_patient_resolution_failed_panel(callback, actor_id=callback.from_user.id)
            return
        recommendation = await recommendation_service.get(recommendation_id)
        if recommendation is None or recommendation.patient_id != patient_id:
            await callback.answer(i18n.t("patient.recommendations.not_found", _locale()), show_alert=True)
            return
        resolution = await care_commerce_service.resolve_recommendation_target_result(
            clinic_id=_primary_clinic_id() or recommendation.clinic_id,
            recommendation_id=recommendation.recommendation_id,
            recommendation_type=recommendation.recommendation_type,
            locale=_locale(),
        )
        if resolution.status == "manual_target_invalid":
            state = await _care_state(callback.from_user.id)
            state.recommendation_id = recommendation.recommendation_id
            state.recommendation_type = recommendation.recommendation_type
            state.recommendation_reason = recommendation.rationale_text or recommendation.body_text
            flow = await _load_flow_state(callback.from_user.id)
            flow.care = state
            await _save_flow_state(callback.from_user.id, flow)
            await _render_recommendation_products_recovery_panel(
                callback,
                actor_id=callback.from_user.id,
                recommendation_id=recommendation.recommendation_id,
                text_key="patient.care.products.manual_target_invalid.panel",
            )
            return
        resolved = resolution.products
        if not resolved:
            await _render_recommendation_products_recovery_panel(
                callback,
                actor_id=callback.from_user.id,
                recommendation_id=recommendation.recommendation_id,
                text_key="patient.care.products.empty.panel",
            )
            return
        state = await _care_state(callback.from_user.id)
        state.recommendation_id = recommendation.recommendation_id
        state.recommendation_type = recommendation.recommendation_type
        state.recommendation_reason = recommendation.rationale_text or recommendation.body_text
        state.recommendation_products = [item.care_product_id for item in resolved]
        state.recommendation_page = 0
        state.recommendation_source_ref = f"care.recommendation.{recommendation.recommendation_id}"
        flow = await _load_flow_state(callback.from_user.id)
        flow.care = state
        await _save_flow_state(callback.from_user.id, flow)
        await _render_recommendation_picker(
            callback,
            actor_id=callback.from_user.id,
            clinic_id=_primary_clinic_id() or recommendation.clinic_id,
            recommendation_id=recommendation.recommendation_id,
        )

    @router.callback_query(F.data == "phome:care")
    async def patient_home_care(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        await _enter_care_catalog(callback, actor_id=callback.from_user.id)

    @router.callback_query(F.data == "care:catalog")
    async def care_catalog_callback(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        await _enter_care_catalog(callback, actor_id=callback.from_user.id)

    @router.callback_query(F.data == "care:orders")
    async def care_orders_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or care_commerce_service is None:
            return
        patient_id = await _resolve_patient_id_for_user(callback.from_user.id)
        clinic_id = _primary_clinic_id()
        if not patient_id or clinic_id is None:
            await _render_care_orders_patient_resolution_failed_panel(callback, actor_id=callback.from_user.id)
            return
        await _render_care_orders_panel(
            callback,
            actor_id=callback.from_user.id,
            clinic_id=clinic_id,
            patient_id=patient_id,
            page=0,
        )

    async def _open_patient_care_order_from_callback(
        callback: CallbackQuery,
        *,
        care_order_id: str,
        mode: CardMode = CardMode.COMPACT,
    ) -> bool:
        if not callback.from_user or care_commerce_service is None:
            return False
        clinic_id = _primary_clinic_id()
        patient_id = await _resolve_patient_id_for_user(callback.from_user.id)
        if clinic_id is None or patient_id is None:
            await _render_care_orders_patient_resolution_failed_panel(callback, actor_id=callback.from_user.id)
            return False
        target_order_id = care_order_id.strip()
        if not target_order_id:
            await callback.answer(i18n.t("patient.care.order.open.denied", _locale()), show_alert=True)
            return False
        await _render_care_order_card(
            callback,
            actor_id=callback.from_user.id,
            clinic_id=clinic_id,
            patient_id=patient_id,
            care_order_id=target_order_id,
            mode=mode,
        )
        return True

    @router.callback_query(F.data.startswith("careo:open:"))
    async def care_order_open_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data or care_commerce_service is None:
            return
        parts = callback.data.split(":")
        if len(parts) != 3:
            await callback.answer(i18n.t("patient.care.order.open.denied", _locale()), show_alert=True)
            return
        opened = await _open_patient_care_order_from_callback(
            callback,
            care_order_id=parts[2],
            mode=CardMode.COMPACT,
        )
        if not opened:
            return

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
        try:
            session = await booking_flow.update_service(booking_session_id=callback_session_id, service_id=service_id)
            flow = await _load_flow_state(callback.from_user.id)
            if flow.booking_mode == "review_edit_service":
                await booking_flow.clear_doctor_preference(booking_session_id=callback_session_id)
                flow.booking_mode = "review_edit_doctor"
            _reset_slot_view_state(flow)
            await _save_flow_state(callback.from_user.id, flow)
            await _render_doctor_pref_panel(
                callback,
                actor_id=callback.from_user.id,
                session_id=session.booking_session_id,
                clinic_id=session.clinic_id,
                branch_id=session.branch_id,
            )
        except Exception:
            await callback.answer(i18n.t("patient.booking.unavailable", _locale()), show_alert=True)

    @router.callback_query(F.data.startswith("qbook:repeat:"))
    async def quick_book_repeat(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        _, _, callback_session_id = callback.data.split(":", 2)
        flow = await _load_flow_state(callback.from_user.id)
        prefill = flow.quick_booking_prefill or {}
        if flow.booking_session_id != callback_session_id or not prefill:
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        if not await booking_flow.validate_active_session_callback(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
        ):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        required = ("service_id", "doctor_id", "branch_id")
        if any(not prefill.get(key) for key in required):
            flow.quick_booking_prefill = {}
            await _save_flow_state(callback.from_user.id, flow)
            await _render_service_panel(
                callback,
                actor_id=callback.from_user.id,
                session_id=callback_session_id,
                clinic_id=clinic_id,
            )
            return
        updated = await booking_flow.apply_recent_booking_prefill(
            booking_session_id=callback_session_id,
            service_id=prefill["service_id"],
            doctor_id=prefill["doctor_id"],
            branch_id=prefill["branch_id"],
        )
        if updated is None:
            flow.quick_booking_prefill = {}
            await _save_flow_state(callback.from_user.id, flow)
            await _render_service_panel(
                callback,
                actor_id=callback.from_user.id,
                session_id=callback_session_id,
                clinic_id=clinic_id,
            )
            return
        flow.quick_booking_prefill = {}
        _reset_slot_view_state(flow)
        await _save_flow_state(callback.from_user.id, flow)
        await _render_slot_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)

    @router.callback_query(F.data.startswith("qbook:same_doctor:"))
    async def quick_book_same_doctor(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        _, _, callback_session_id = callback.data.split(":", 2)
        flow = await _load_flow_state(callback.from_user.id)
        prefill = flow.quick_booking_prefill or {}
        if flow.booking_session_id != callback_session_id or not prefill:
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        if not await booking_flow.validate_active_session_callback(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
        ):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        required = ("doctor_id", "branch_id")
        if any(not prefill.get(key) for key in required):
            flow.quick_booking_prefill = {}
            await _save_flow_state(callback.from_user.id, flow)
            await _render_service_panel(
                callback,
                actor_id=callback.from_user.id,
                session_id=callback_session_id,
                clinic_id=clinic_id,
            )
            return
        updated = await booking_flow.apply_recent_booking_same_doctor_prefill(
            booking_session_id=callback_session_id,
            doctor_id=prefill["doctor_id"],
            branch_id=prefill["branch_id"],
        )
        flow.quick_booking_prefill = {}
        _reset_slot_view_state(flow)
        await _save_flow_state(callback.from_user.id, flow)
        await _render_service_panel(
            callback,
            actor_id=callback.from_user.id,
            session_id=callback_session_id,
            clinic_id=clinic_id,
        )
        if updated is None:
            await callback.answer(i18n.t("patient.booking.quick.same_doctor.fallback", _locale()), show_alert=False)

    @router.callback_query(F.data.startswith("qbook:other:"))
    async def quick_book_other(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        _, _, callback_session_id = callback.data.split(":", 2)
        flow = await _load_flow_state(callback.from_user.id)
        if flow.booking_session_id != callback_session_id:
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        if not await booking_flow.validate_active_session_callback(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
        ):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        flow.quick_booking_prefill = {}
        await _save_flow_state(callback.from_user.id, flow)
        await _render_service_panel(
            callback,
            actor_id=callback.from_user.id,
            session_id=callback_session_id,
            clinic_id=clinic_id,
        )

    @router.callback_query(F.data.startswith("care:repeat:"))
    async def care_repeat_from_order_surface(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data or care_commerce_service is None:
            return
        clinic_id = _primary_clinic_id()
        patient_id = await _resolve_patient_id_for_user(callback.from_user.id)
        if clinic_id is None or patient_id is None:
            await _render_care_orders_patient_resolution_failed_panel(callback, actor_id=callback.from_user.id)
            return
        care_order_id = callback.data.split(":", 2)[2]
        view = await _reserve_again_from_order(clinic_id=clinic_id, patient_id=patient_id, care_order_id=care_order_id)
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
                if product is None or product.status != "active":
                    await _render_care_product_missing_panel(callback, actor_id=callback.from_user.id)
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
                    await _render_care_reserve_patient_resolution_failed_panel(callback, actor_id=callback.from_user.id)
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
                await _render_care_orders_patient_resolution_failed_panel(callback, actor_id=callback.from_user.id)
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
                return
            if decoded.page_or_index == "open":
                await _open_patient_care_order_from_callback(
                    callback,
                    care_order_id=decoded.entity_id,
                    mode=CardMode.COMPACT,
                )
                return
            if decoded.page_or_index == "open_expand":
                await _open_patient_care_order_from_callback(
                    callback,
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
                    await _render_existing_booking_control_panel(
                        callback,
                        actor_id=callback.from_user.id,
                        booking=result.entity,
                        session_state_token=callback_session_id,
                    )
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
                    await _render_waitlist_success_panel(
                        callback,
                        actor_id=callback.from_user.id,
                        callback_session_id=callback_session_id,
                        booking_id=booking_id,
                    )
                    return
                await callback.answer(i18n.t("patient.booking.finalize.invalid_state", _locale()), show_alert=True)
                return
            if decoded.page_or_index == "cancel_prompt":
                await cancel_prompt_by_runtime(callback, callback_session_id=callback_session_id, booking_id=booking_id)
                return
            if decoded.page_or_index == "cancel_abort":
                clinic_id = _primary_clinic_id()
                if not clinic_id:
                    await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
                    return
                started = await booking_flow.start_existing_booking_control_for_booking(
                    clinic_id=clinic_id,
                    telegram_user_id=callback.from_user.id,
                    booking_id=booking_id,
                )
                if started.kind != "ready" or started.booking is None or started.booking_session is None:
                    await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
                    return
                await _render_existing_booking_control_panel(
                    callback,
                    actor_id=callback.from_user.id,
                    booking=started.booking,
                    session_state_token=started.booking_session.booking_session_id,
                    header=i18n.t("patient.booking.cancel.aborted", _locale()),
                )
                return
            if decoded.page_or_index == "cancel_confirm":
                result = await booking_flow.cancel_booking(
                    clinic_id=clinic_id,
                    telegram_user_id=callback.from_user.id,
                    callback_session_id=callback_session_id,
                    booking_id=booking_id,
                )
                if isinstance(result, OrchestrationSuccess):
                    await _render_existing_booking_control_panel(
                        callback,
                        actor_id=callback.from_user.id,
                        booking=result.entity,
                        session_state_token=callback_session_id,
                    )
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
            await _render_care_reserve_patient_resolution_failed_panel(callback, actor_id=callback.from_user.id)
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
            await callback.answer()
            return
        if not (await _load_flow_state(callback.from_user.id)).booking_session_id:
            await callback.answer(i18n.t("patient.booking.session.missing", _locale()), show_alert=True)
            return
        _, _, callback_session_id, doctor_token = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        try:
            if doctor_token == "any":
                await booking_flow.update_doctor_preference(booking_session_id=callback_session_id, doctor_preference_type="any", doctor_id=None)
            else:
                await booking_flow.update_doctor_preference(
                    booking_session_id=callback_session_id,
                    doctor_preference_type="specific",
                    doctor_id=doctor_token,
                )
            flow = await _load_flow_state(callback.from_user.id)
            if flow.booking_mode not in {"review_edit_doctor", "review_edit_time"}:
                _reset_slot_view_state(flow)
            await _save_flow_state(callback.from_user.id, flow)
            await _render_slot_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)
        except Exception:
            await callback.answer(i18n.t("patient.booking.unavailable", _locale()), show_alert=True)

    @router.callback_query(F.data.startswith("book:back:services:"))
    async def booking_back_to_services(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await callback.answer()
            return
        _, _, _, callback_session_id = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        flow = await _load_flow_state(callback.from_user.id)
        flow.booking_mode = "new_booking_flow"
        await _save_flow_state(callback.from_user.id, flow)
        await _render_patient_home_panel(callback, actor_id=callback.from_user.id)

    @router.callback_query(F.data.startswith("book:back:doctors:"))
    async def booking_back_to_doctors(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await callback.answer()
            return
        _, _, _, callback_session_id = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        session = await booking_flow.get_booking_session(booking_session_id=callback_session_id)
        if session is None:
            await callback.answer(i18n.t("patient.booking.session.missing", _locale()), show_alert=True)
            return
        flow = await _load_flow_state(callback.from_user.id)
        flow.booking_mode = "new_booking_flow"
        await _save_flow_state(callback.from_user.id, flow)
        await _render_doctor_pref_panel(
            callback,
            actor_id=callback.from_user.id,
            session_id=callback_session_id,
            clinic_id=session.clinic_id,
            branch_id=session.branch_id,
        )

    @router.callback_query(F.data.startswith("book:slots:more:"))
    async def booking_slots_more(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await callback.answer()
            return
        _, _, _, callback_session_id = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        flow = await _load_flow_state(callback.from_user.id)
        flow.slot_page = max(flow.slot_page, 0) + 1
        await _save_flow_state(callback.from_user.id, flow)
        await _render_slot_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)

    @router.callback_query(F.data.startswith("book:slots:dates:"))
    async def booking_slots_dates(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await callback.answer()
            return
        _, _, _, callback_session_id = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        await _render_slot_date_picker_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)

    @router.callback_query(F.data.startswith("book:slots:date:"))
    async def booking_slots_date_select(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await callback.answer()
            return
        _, _, _, callback_session_id, selected_date_iso = callback.data.split(":", 4)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        if _parse_iso_date(selected_date_iso) is None:
            await callback.answer(i18n.t("patient.booking.unavailable", _locale()), show_alert=True)
            return
        flow = await _load_flow_state(callback.from_user.id)
        flow.slot_date_from = selected_date_iso
        flow.slot_page = 0
        _reset_slot_suppression(flow)
        await _save_flow_state(callback.from_user.id, flow)
        await _render_slot_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)

    @router.callback_query(F.data.startswith("book:slots:windows:"))
    async def booking_slots_windows(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await callback.answer()
            return
        _, _, _, callback_session_id = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        await _render_slot_window_picker_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)

    @router.callback_query(F.data.startswith("book:slots:window:"))
    async def booking_slots_window_select(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await callback.answer()
            return
        _, _, _, callback_session_id, requested_window = callback.data.split(":", 4)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        flow = await _load_flow_state(callback.from_user.id)
        flow.slot_time_window = _resolve_time_window(value=requested_window)
        flow.slot_page = 0
        _reset_slot_suppression(flow)
        await _save_flow_state(callback.from_user.id, flow)
        await _render_slot_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)

    @router.callback_query(F.data.startswith("book:slots:back:"))
    async def booking_slots_back(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await callback.answer()
            return
        _, _, _, callback_session_id = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        await _render_slot_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)

    @router.callback_query(F.data.startswith("book:doc_code:"))
    async def booking_doctor_code_prompt(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await callback.answer()
            return
        _, _, callback_session_id = callback.data.split(":", 2)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        flow = await _load_flow_state(callback.from_user.id)
        flow.booking_mode = "new_booking_doctor_code"
        await _save_flow_state(callback.from_user.id, flow)
        await _render_doctor_code_prompt(callback, actor_id=callback.from_user.id, session_id=callback_session_id)

    @router.callback_query(F.data.startswith("book:slot:"))
    async def select_slot(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        locale = _locale()
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        callback_session_id = (await _load_flow_state(callback.from_user.id)).booking_session_id
        if not callback_session_id:
            await callback.answer(i18n.t("patient.booking.session.missing", locale), show_alert=True)
            return
        _, _, slot_id = callback.data.split(":", 2)
        callback_session = await booking_flow.get_booking_session(booking_session_id=callback_session_id)
        if callback_session is None or callback_session.clinic_id != clinic_id or callback_session.telegram_user_id != callback.from_user.id:
            await callback.answer(i18n.t("patient.booking.callback.stale", locale), show_alert=True)
            return
        allowed_route_types = NEW_BOOKING_ROUTE_TYPES
        slot_prompt_key = "patient.booking.slot.prompt"
        if callback_session.route_type in RESCHEDULE_BOOKING_CONTROL_ROUTE_TYPES:
            allowed_route_types = RESCHEDULE_BOOKING_CONTROL_ROUTE_TYPES
            slot_prompt_key = "patient.booking.reschedule.slot.prompt"
        if not await booking_flow.validate_active_session_callback(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
            allowed_route_types=allowed_route_types,
        ):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        selected = await booking_flow.select_slot(booking_session_id=callback_session_id, slot_id=slot_id)
        if isinstance(selected, (SlotUnavailableOutcome, ConflictOutcome)):
            flow = await _load_flow_state(callback.from_user.id)
            _suppress_slot_in_flow(flow, slot_id)
            flow.slot_page = max(flow.slot_page, 0)
            await _save_flow_state(callback.from_user.id, flow)
            await _render_slot_panel(
                callback,
                actor_id=callback.from_user.id,
                session_id=callback_session_id,
                prompt_key=slot_prompt_key,
                notice_key="patient.booking.slot.notice.unavailable",
            )
            return
        if isinstance(selected, InvalidStateOutcome):
            await _render_slot_panel(
                callback,
                actor_id=callback.from_user.id,
                session_id=callback_session_id,
                prompt_key=slot_prompt_key,
                notice_key="patient.booking.slot.notice.unavailable",
            )
            return
        if callback_session.route_type in RESCHEDULE_BOOKING_CONTROL_ROUTE_TYPES:
            flow = await _load_flow_state(callback.from_user.id)
            flow.booking_mode = "reschedule_booking_control"
            await _save_flow_state(callback.from_user.id, flow)
            await _render_reschedule_review_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)
            return
        flow = await _load_flow_state(callback.from_user.id)
        if flow.booking_mode in {"review_edit_service", "review_edit_doctor", "review_edit_time"}:
            refreshed = await booking_flow.get_booking_session(booking_session_id=callback_session_id)
            if refreshed and refreshed.contact_phone_snapshot and refreshed.resolved_patient_id:
                review = await booking_flow.mark_review_ready(booking_session_id=callback_session_id)
                if not isinstance(review, InvalidStateOutcome):
                    flow.booking_mode = "new_booking_flow"
                    flow.reschedule_booking_id = ""
                    await _save_flow_state(callback.from_user.id, flow)
                    await _render_review_finalize_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)
                    return
        flow.booking_mode = "new_booking_contact"
        flow.reschedule_booking_id = ""
        await _save_flow_state(callback.from_user.id, flow)
        contact_keyboard = _patient_contact_reply_keyboard(locale=locale, include_back=True)
        await _send_or_edit_panel(
            actor_id=callback.from_user.id,
            message=callback,
            session_id=callback_session_id,
            text=i18n.t("patient.booking.contact.prompt", locale),
            reply_keyboard=contact_keyboard,
        )

    async def _render_review_edit_failed_panel(callback: CallbackQuery, *, session_id: str, text_key: str) -> None:
        locale = _locale()
        await _send_or_edit_panel(
            actor_id=callback.from_user.id,
            message=callback,
            session_id=session_id,
            text=i18n.t(text_key, locale),
            keyboard=InlineKeyboardMarkup(inline_keyboard=[[_patient_home_nav_button(locale=locale)]]),
        )

    @router.callback_query(F.data.startswith("book:review:edit:"))
    async def booking_review_edit(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        locale = _locale()
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await callback.answer()
            return
        _, _, _, field, callback_session_id = callback.data.split(":", 4)
        if field not in {"service", "doctor", "time", "phone"}:
            await callback.answer(i18n.t("patient.booking.review.edit.unavailable", locale), show_alert=True)
            return
        if not await booking_flow.validate_active_session_callback(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
        ):
            await callback.answer(i18n.t("patient.booking.callback.stale", locale), show_alert=True)
            return
        session = await booking_flow.get_booking_session(booking_session_id=callback_session_id)
        if session is None or session.clinic_id != clinic_id or session.telegram_user_id != callback.from_user.id:
            await _render_review_edit_failed_panel(callback, session_id=callback_session_id, text_key="patient.booking.review.edit.unavailable")
            return
        if session.status in {"admin_escalated", "completed", "canceled", "expired"}:
            await _render_review_edit_failed_panel(callback, session_id=callback_session_id, text_key="patient.booking.review.edit.unavailable")
            return
        flow = await _load_flow_state(callback.from_user.id)
        flow.booking_session_id = callback_session_id
        flow.reschedule_booking_id = ""
        flow.quick_booking_prefill = {}
        if field in {"service", "doctor", "time"}:
            released = await booking_flow.release_selected_slot_for_reselect(booking_session_id=callback_session_id)
            if isinstance(released, InvalidStateOutcome):
                await _render_review_edit_failed_panel(callback, session_id=callback_session_id, text_key="patient.booking.review.edit.release_failed")
                return
            _reset_slot_view_state(flow)
        if field == "service":
            flow.booking_mode = "review_edit_service"
            await _save_flow_state(callback.from_user.id, flow)
            await _render_service_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id, clinic_id=clinic_id)
            return
        if field == "doctor":
            flow.booking_mode = "review_edit_doctor"
            await _save_flow_state(callback.from_user.id, flow)
            await _render_doctor_pref_panel(
                callback,
                actor_id=callback.from_user.id,
                session_id=callback_session_id,
                clinic_id=session.clinic_id,
                branch_id=session.branch_id,
            )
            return
        if field == "time":
            flow.booking_mode = "review_edit_time"
            await _save_flow_state(callback.from_user.id, flow)
            await _render_slot_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)
            return
        flow.booking_mode = "review_edit_phone"
        await _save_flow_state(callback.from_user.id, flow)
        await _send_or_edit_panel(
            actor_id=callback.from_user.id,
            message=callback,
            session_id=callback_session_id,
            text=i18n.t("patient.booking.contact.prompt", locale),
            reply_keyboard=_patient_contact_reply_keyboard(locale=locale, include_back=True),
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

    @router.callback_query(F.data.startswith("book:review:back:"))
    async def booking_review_back(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        locale = _locale()
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        _, _, _, callback_session_id = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
        ):
            await callback.answer(i18n.t("patient.booking.callback.stale", locale), show_alert=True)
            return
        flow = await _load_flow_state(callback.from_user.id)
        flow.booking_mode = "new_booking_contact"
        await _save_flow_state(callback.from_user.id, flow)
        await _send_or_edit_panel(
            actor_id=callback.from_user.id,
            message=callback,
            session_id=callback_session_id,
            text=i18n.t("patient.booking.contact.prompt", locale),
            reply_keyboard=_patient_contact_reply_keyboard(locale=locale, include_back=True),
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
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await callback.answer(i18n.t("patient.booking.unavailable", _locale()), show_alert=True)
            return
        _, _, callback_session_id = callback.data.split(":", 2)
        flow = await _load_flow_state(callback.from_user.id)
        if flow.booking_mode != "reschedule_booking_control" or flow.booking_session_id != callback_session_id:
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        if not await booking_flow.validate_active_session_callback(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
            allowed_route_types=RESCHEDULE_BOOKING_CONTROL_ROUTE_TYPES,
        ):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        await _render_slot_panel(
            callback,
            actor_id=callback.from_user.id,
            session_id=callback_session_id,
            prompt_key="patient.booking.reschedule.slot.prompt",
        )

    @router.callback_query(F.data.startswith("rsch:confirm:"))
    async def reschedule_confirm(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await callback.answer(i18n.t("patient.booking.unavailable", _locale()), show_alert=True)
            return
        _, _, callback_session_id = callback.data.split(":", 2)
        flow = await _load_flow_state(callback.from_user.id)
        if flow.booking_mode != "reschedule_booking_control" or flow.booking_session_id != callback_session_id:
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        if not await booking_flow.validate_active_session_callback(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
            allowed_route_types=RESCHEDULE_BOOKING_CONTROL_ROUTE_TYPES,
        ):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        if not flow.reschedule_booking_id:
            await callback.answer(i18n.t("patient.booking.reschedule.complete.unavailable", _locale()), show_alert=True)
            return
        completed = await booking_flow.complete_patient_reschedule(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
            source_booking_id=flow.reschedule_booking_id,
        )
        if isinstance(completed, SlotUnavailableOutcome):
            await _render_slot_panel(
                callback,
                actor_id=callback.from_user.id,
                session_id=callback_session_id,
                prompt_key="patient.booking.reschedule.slot.prompt",
                notice_key="patient.booking.slot.notice.unavailable",
            )
            return
        if isinstance(completed, ConflictOutcome):
            await _render_slot_panel(
                callback,
                actor_id=callback.from_user.id,
                session_id=callback_session_id,
                prompt_key="patient.booking.reschedule.slot.prompt",
                notice_key="patient.booking.slot.notice.unavailable",
            )
            return
        if not isinstance(completed, OrchestrationSuccess):
            await callback.answer(i18n.t("patient.booking.reschedule.complete.unavailable", _locale()), show_alert=True)
            await _render_reschedule_review_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)
            return
        locale = _locale()
        started = await booking_flow.start_existing_booking_control_for_booking(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            booking_id=completed.entity.booking_id,
        )
        booking = started.booking
        session = started.booking_session
        if started.kind != "ready" or booking is None or session is None:
            await callback.answer(i18n.t("patient.booking.reschedule.complete.unavailable", locale), show_alert=True)
            return
        flow.booking_session_id = session.booking_session_id
        flow.booking_mode = "existing_booking_control"
        flow.reschedule_booking_id = ""
        await _save_flow_state(callback.from_user.id, flow)
        header = i18n.t("patient.booking.reschedule.complete.success", locale)
        await _render_existing_booking_control_panel(
            callback,
            actor_id=callback.from_user.id,
            booking=booking,
            session_state_token=session.booking_session_id,
            header=header,
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
        if action == "cancel":
            await _show_reminder_cancel_confirm_prompt(callback, reminder_id=reminder_id)
            await callback.answer()
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

    def _encode_reminder_cancel_callback(*, action: str, reminder_id: str, provider_message_id: str) -> str:
        return f"remc:{action}:{reminder_id}:{provider_message_id}"

    def _parse_reminder_cancel_callback_payload(data: str) -> tuple[str, str, str] | None:
        callback_parts = data.split(":", 3)
        if len(callback_parts) != 4:
            return None
        _, action, reminder_id, provider_message_id = callback_parts
        if action not in {"confirm", "abort"}:
            return None
        if not reminder_id or not provider_message_id or not provider_message_id.isdigit():
            return None
        return action, reminder_id, provider_message_id

    async def _show_reminder_cancel_confirm_prompt(callback: CallbackQuery, *, reminder_id: str) -> None:
        if callback.message is None:
            await callback.answer(i18n.t("patient.reminder.cancel.confirm", _locale()), show_alert=True)
            return
        original_message_id = str(callback.message.message_id)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("common.yes", _locale()),
                        callback_data=_encode_reminder_cancel_callback(
                            action="confirm",
                            reminder_id=reminder_id,
                            provider_message_id=original_message_id,
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=i18n.t("common.no", _locale()),
                        callback_data=_encode_reminder_cancel_callback(
                            action="abort",
                            reminder_id=reminder_id,
                            provider_message_id=original_message_id,
                        ),
                    )
                ],
            ]
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.answer(
            i18n.t("patient.reminder.cancel.confirm", _locale()),
            reply_markup=keyboard,
        )

    @router.callback_query(F.data.startswith("remc:"))
    async def reminder_cancel_confirm_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        payload = _parse_reminder_cancel_callback_payload(callback.data)
        if payload is None:
            await callback.answer(i18n.t("patient.reminder.action.invalid", _locale()), show_alert=True)
            return
        action, reminder_id, original_provider_message_id = payload
        if action == "abort":
            if callback.message:
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
            continued = await _handoff_reminder_cancel_abort_to_booking_panel(callback, reminder_id=reminder_id)
            if not continued:
                await callback.answer(i18n.t("patient.reminder.cancel.aborted", _locale()), show_alert=True)
            else:
                await callback.answer()
            return
        outcome = await reminder_actions.handle_action(
            reminder_id=reminder_id,
            action="cancel",
            provider_message_id=original_provider_message_id,
        )
        if outcome.kind == "accepted":
            if callback.message:
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
            await _handoff_reminder_action_to_booking_panel(callback, action="cancel", outcome=outcome)
            await callback.answer()
            return
        if outcome.kind == "stale":
            await callback.answer(i18n.t("patient.reminder.action.stale", _locale()), show_alert=True)
            return
        await callback.answer(i18n.t("patient.reminder.action.invalid", _locale()), show_alert=True)

    async def _handoff_reminder_cancel_abort_to_booking_panel(callback: CallbackQuery, *, reminder_id: str) -> bool:
        if not callback.from_user:
            return False
        repository = getattr(reminder_actions, "repository", None)
        get_reminder = getattr(repository, "get_reminder", None)
        if get_reminder is None:
            return False
        reminder = await get_reminder(reminder_id=reminder_id)
        booking_id = getattr(reminder, "booking_id", None) if reminder is not None else None
        clinic_id = _primary_clinic_id()
        if not clinic_id or not booking_id:
            return False
        started = await booking_flow.start_existing_booking_control_for_booking(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            booking_id=booking_id,
        )
        booking = started.booking
        session = started.booking_session
        if started.kind != "ready" or booking is None or session is None:
            return False
        flow = await _load_flow_state(callback.from_user.id)
        flow.booking_session_id = session.booking_session_id
        flow.booking_mode = "existing_booking_control"
        flow.reschedule_booking_id = ""
        await _save_flow_state(callback.from_user.id, flow)
        locale = _locale()
        header = i18n.t("patient.reminder.cancel.aborted", locale)
        await _render_existing_booking_control_panel(
            callback,
            actor_id=callback.from_user.id,
            booking=booking,
            session_state_token=session.booking_session_id,
            header=header,
            send_fresh_from_callback=True,
        )
        return True

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
            await _render_waitlist_success_panel(
                callback,
                actor_id=callback.from_user.id,
                callback_session_id=callback_session_id,
                booking_id=booking_id,
            )
            return
        await callback.answer(i18n.t("patient.booking.finalize.invalid_state", _locale()), show_alert=True)

    async def cancel_prompt_by_runtime(callback: CallbackQuery, *, callback_session_id: str, booking_id: str) -> None:
        locale = _locale()
        clinic_id = _primary_clinic_id()
        booking = None
        if clinic_id:
            started = await booking_flow.start_existing_booking_control_for_booking(
                clinic_id=clinic_id,
                telegram_user_id=callback.from_user.id,
                booking_id=booking_id,
            )
            if started.kind == "ready":
                booking = started.booking
                if started.booking_session is not None:
                    callback_session_id = started.booking_session.booking_session_id
        panel_lines = [i18n.t("patient.booking.cancel.panel.title", locale)]
        if booking is not None:
            timezone_name = _resolve_booking_timezone_name(clinic_id=booking.clinic_id, branch_id=booking.branch_id)
            local_start = booking.scheduled_start_at.astimezone(_zone_or_utc(timezone_name))
            date_label, time_label = _format_patient_datetime_parts(local_start, locale=locale)
            panel_lines.extend(
                [
                    "",
                    i18n.t("patient.booking.cancel.panel.body", locale).format(
                        service=_resolve_booking_service_label_for_patient(booking=booking, locale=locale),
                        doctor=_resolve_booking_doctor_label_for_patient(booking=booking, locale=locale),
                        date=date_label,
                        time=time_label,
                    ),
                ]
            )
        else:
            panel_lines.extend(["", i18n.t("patient.booking.cancel.confirm", locale)])
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.booking.cancel.confirm_cta", locale),
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
                        text=i18n.t("patient.booking.cancel.back_to_booking", locale),
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
                [InlineKeyboardButton(text=i18n.t("patient.home.nav.home", locale), callback_data="phome:home")],
            ]
        )
        await _send_or_edit_panel(
            actor_id=callback.from_user.id,
            message=callback,
            session_id=callback_session_id,
            text="\n".join(panel_lines),
            keyboard=keyboard,
        )

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
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        _, _, callback_session_id, booking_id = callback.data.split(":", 3)
        started = await booking_flow.start_existing_booking_control_for_booking(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            booking_id=booking_id,
        )
        if started.kind != "ready" or started.booking is None or started.booking_session is None:
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        await _render_existing_booking_control_panel(
            callback,
            actor_id=callback.from_user.id,
            booking=started.booking,
            session_state_token=started.booking_session.booking_session_id or callback_session_id,
            header=i18n.t("patient.booking.cancel.aborted", _locale()),
        )

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
            await _render_existing_booking_control_panel(
                callback,
                actor_id=callback.from_user.id,
                booking=result.entity,
                session_state_token=callback_session_id,
            )
            return
        await callback.answer(i18n.t("patient.booking.finalize.invalid_state", _locale()), show_alert=True)

    @router.message(F.contact)
    async def on_contact_share(message: Message) -> None:
        if not message.from_user or not message.contact:
            return
        await _handle_contact_submission(message, actor_id=message.from_user.id, phone=message.contact.phone_number)
        try:
            await message.delete()
        except Exception:
            pass

    @router.message(F.text.regexp(r"^\+?\d[\d\-\s\(\)]{6,}$"))
    async def on_contact_text(message: Message) -> None:
        if not message.from_user or not message.text:
            return
        flow = await _load_flow_state(message.from_user.id)
        if flow.booking_mode in {"new_booking_contact", "existing_lookup_contact", "review_edit_phone"}:
            await _handle_contact_submission(message, actor_id=message.from_user.id, phone=message.text)
            try:
                await message.delete()
            except Exception:
                pass
            return
        if flow.booking_mode == "new_booking_doctor_code":
            await _handle_doctor_code_submission(message, actor_id=message.from_user.id, code=message.text)

    @router.message(F.text)
    async def on_contact_navigation(message: Message) -> None:
        if not message.from_user or not message.text:
            return
        locale = _locale()
        flow = await _load_flow_state(message.from_user.id)
        if message.text == i18n.t("patient.home.nav.home", locale):
            if flow.booking_mode in {"new_booking_contact", "existing_lookup_contact", "new_booking_doctor_code", "review_edit_phone"}:
                await _remove_patient_reply_keyboard(message)
            await _render_patient_home_panel(message, actor_id=message.from_user.id)
            return
        if message.text != _patient_back_nav_text(locale=locale):
            if flow.booking_mode == "new_booking_doctor_code":
                await _handle_doctor_code_submission(message, actor_id=message.from_user.id, code=message.text)
            return
        if flow.booking_mode == "new_booking_contact" and flow.booking_session_id:
            await _remove_patient_reply_keyboard(message)
            await _render_slot_panel(message, actor_id=message.from_user.id, session_id=flow.booking_session_id)
            return
        if flow.booking_mode == "review_edit_phone" and flow.booking_session_id:
            await _remove_patient_reply_keyboard(message)
            flow.booking_mode = "new_booking_flow"
            await _save_flow_state(message.from_user.id, flow)
            await _render_review_finalize_panel(message, actor_id=message.from_user.id, session_id=flow.booking_session_id)
            return
        if flow.booking_mode == "new_booking_doctor_code" and flow.booking_session_id:
            session = await booking_flow.get_booking_session(booking_session_id=flow.booking_session_id)
            if session is not None:
                await _remove_patient_reply_keyboard(message)
                flow.booking_mode = "new_booking_flow"
                await _save_flow_state(message.from_user.id, flow)
                await _render_doctor_pref_panel(
                    message,
                    actor_id=message.from_user.id,
                    session_id=flow.booking_session_id,
                    clinic_id=session.clinic_id,
                    branch_id=session.branch_id,
                )
                return
            return
        await _render_patient_home_panel(message, actor_id=message.from_user.id)

    async def _handle_doctor_code_submission(message: Message, *, actor_id: int, code: str) -> None:
        flow = await _load_flow_state(actor_id)
        session_id = flow.booking_session_id
        if flow.booking_mode != "new_booking_doctor_code" or not session_id:
            return
        session = await booking_flow.get_booking_session(booking_session_id=session_id)
        if session is None:
            return
        resolved = reference.resolve_doctor_access_code(
            clinic_id=session.clinic_id,
            code=code,
            service_id=session.service_id,
            branch_id=session.branch_id,
        )
        if resolved is None:
            await _render_doctor_code_prompt(
                message,
                actor_id=actor_id,
                session_id=session_id,
                error_key="patient.booking.doctor.code.invalid",
            )
            return
        await booking_flow.update_doctor_preference(
            booking_session_id=session_id,
            doctor_preference_type="specific",
            doctor_id=resolved.doctor_id,
        )
        flow.booking_mode = "new_booking_flow"
        _reset_slot_view_state(flow)
        await _save_flow_state(actor_id, flow)
        await _render_slot_panel(message, actor_id=actor_id, session_id=session_id)

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
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.reschedule.start.contact_ignored", locale),
            )
            return
        if mode not in {"new_booking_contact", "review_edit_phone"}:
            return
        session = await booking_flow.get_booking_session(booking_session_id=session_id)
        if session is None:
            flow.booking_session_id = ""
            flow.booking_mode = "new_booking_flow"
            flow.reschedule_booking_id = ""
            await _save_flow_state(actor_id, flow)
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
        await _remove_patient_reply_keyboard(message)
        flow.booking_mode = "new_booking_flow"
        await _save_flow_state(actor_id, flow)
        await _render_review_finalize_panel(message, actor_id=actor_id, session_id=session_id)

    async def _render_resume_panel(message: Message | CallbackQuery, *, actor_id: int, session_id: str, clinic_id: str) -> None:
        if await _resume_active_reschedule_context(
            message,
            actor_id=actor_id,
            clinic_id=clinic_id,
            on_stale_key="patient.booking.reschedule.start.unavailable",
        ):
            return
        resume = await booking_flow.determine_resume_panel(booking_session_id=session_id)
        if resume is None:
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=session_id, text=i18n.t("patient.booking.session.missing", _locale()))
            return
        if resume.panel_key == "service_selection":
            flow = await _load_flow_state(actor_id)
            flow.booking_mode = "new_booking_flow"
            flow.reschedule_booking_id = ""
            flow.quick_booking_prefill = {}
            await _save_flow_state(actor_id, flow)
            await _render_service_panel(message, actor_id=actor_id, session_id=session_id, clinic_id=clinic_id)
            return
        if resume.panel_key == "doctor_preference_selection":
            flow = await _load_flow_state(actor_id)
            flow.booking_mode = "new_booking_flow"
            flow.reschedule_booking_id = ""
            flow.quick_booking_prefill = {}
            await _save_flow_state(actor_id, flow)
            await _render_doctor_pref_panel(
                message,
                actor_id=actor_id,
                session_id=session_id,
                clinic_id=resume.booking_session.clinic_id,
                branch_id=resume.booking_session.branch_id,
            )
            return
        if resume.panel_key == "slot_selection":
            flow = await _load_flow_state(actor_id)
            flow.booking_mode = "new_booking_flow"
            flow.reschedule_booking_id = ""
            flow.quick_booking_prefill = {}
            await _save_flow_state(actor_id, flow)
            await _render_slot_panel(message, actor_id=actor_id, session_id=session_id)
            return
        if resume.panel_key == "contact_collection":
            flow = await _load_flow_state(actor_id)
            flow.booking_mode = "new_booking_contact"
            flow.reschedule_booking_id = ""
            flow.quick_booking_prefill = {}
            await _save_flow_state(actor_id, flow)
            contact_keyboard = _patient_contact_reply_keyboard(locale=_locale(), include_back=True)
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.contact.prompt", _locale()),
                reply_keyboard=contact_keyboard,
            )
            return
        if resume.panel_key == "review_finalize":
            flow = await _load_flow_state(actor_id)
            flow.booking_mode = "new_booking_flow"
            flow.reschedule_booking_id = ""
            flow.quick_booking_prefill = {}
            await _save_flow_state(actor_id, flow)
            await _render_review_finalize_panel(message, actor_id=actor_id, session_id=session_id)
            return
        await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=session_id, text=i18n.t("patient.booking.resume.terminal", _locale()))

    def _render_patient_booking_panel(*, booking, session_state_token: str, locale: str) -> str:
        timezone_name = _resolve_booking_timezone_name(clinic_id=booking.clinic_id, branch_id=booking.branch_id)
        local_start = booking.scheduled_start_at.astimezone(_zone_or_utc(timezone_name))
        date_label, time_label = _format_patient_datetime_parts(local_start, locale=locale)
        status_label = _resolve_patient_my_booking_status_label(status=booking.status, locale=locale)
        service_label = _resolve_booking_service_label_for_patient(booking=booking, locale=locale)
        doctor_label = _resolve_booking_doctor_label_for_patient(booking=booking, locale=locale)
        branch_label = _resolve_booking_branch_label_for_patient(booking=booking, locale=locale)
        reminders_label = _resolve_patient_my_booking_reminder_label(booking=booking, locale=locale)
        next_step = _resolve_patient_my_booking_next_step(status=booking.status, locale=locale)
        lines = [
            i18n.t("patient.booking.my.panel.title", locale),
            "",
            status_label,
            "",
            f"{i18n.t('patient.booking.my.field.service', locale)}: {service_label}",
            f"{i18n.t('patient.booking.my.field.doctor', locale)}: {doctor_label}",
            f"{i18n.t('patient.booking.my.field.date', locale)}: {date_label}",
            f"{i18n.t('patient.booking.my.field.time', locale)}: {time_label}",
            f"{i18n.t('patient.booking.my.field.branch', locale)}: {branch_label}",
            "",
            f"{i18n.t('patient.booking.my.field.reminders', locale)}: {reminders_label}",
        ]
        if next_step:
            lines.extend(["", next_step])
        return "\n".join(lines)

    def _resolve_booking_service_label_for_patient(*, booking, locale: str) -> str:
        service = reference.get_service(booking.clinic_id, booking.service_id or "") if booking.service_id else None
        if service is None:
            return i18n.t("patient.booking.review.value.missing", locale)
        fallback_locale = _fallback_locale_for_clinic(booking.clinic_id)
        return _resolve_service_label(
            service_title_key=service.title_key,
            service_code=service.code,
            fallback_id=None,
            locale=locale,
            fallback_locale=fallback_locale,
            i18n=i18n,
        )

    def _resolve_booking_doctor_label_for_patient(*, booking, locale: str) -> str:
        doctor = reference.get_doctor(booking.clinic_id, booking.doctor_id or "") if booking.doctor_id else None
        return _resolve_reference_label(
            display_name=(doctor.display_name if doctor is not None else None),
            fallback_id=None,
            locale=locale,
            i18n=i18n,
        )

    def _resolve_booking_branch_label_for_patient(*, booking, locale: str) -> str:
        if not booking.branch_id:
            return i18n.t("patient.booking.my.branch_missing", locale)
        branch = reference.get_branch(booking.clinic_id, booking.branch_id)
        display_name = (branch.display_name or "").strip() if branch is not None else ""
        return display_name or i18n.t("patient.booking.my.branch_missing", locale)

    def _resolve_patient_my_booking_status_label(*, status: str, locale: str) -> str:
        status_key = f"patient.booking.my.status.{status}"
        status_text = i18n.t(status_key, locale)
        if status_text == status_key:
            status_text = i18n.t("patient.booking.my.status.fallback", locale).format(status=status.replace("_", " "))
        icon_by_status = {
            "pending_confirmation": "⏳",
            "confirmed": "✅",
            "reschedule_requested": "🔁",
            "canceled": "❌",
            "checked_in": "✅",
            "in_service": "🦷",
            "completed": "✅",
            "no_show": "❌",
        }
        return f"{icon_by_status.get(status, 'ℹ️')} {status_text}"

    def _resolve_patient_my_booking_reminder_label(*, booking, locale: str) -> str:
        if booking.status in {"canceled", "completed", "no_show"}:
            return i18n.t("patient.booking.my.reminders.not_needed", locale)
        return i18n.t("patient.booking.my.reminders.default", locale)

    def _resolve_patient_my_booking_next_step(*, status: str, locale: str) -> str:
        key = f"patient.booking.my.next.{status}"
        value = i18n.t(key, locale)
        return "" if value == key else value

    async def _build_patient_booking_controls_keyboard(*, booking, session_state_token: str, locale: str) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        is_terminal = booking.status in {"canceled", "completed", "no_show", "checked_in", "in_service"}
        if booking.status == "pending_confirmation":
            rows.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.booking.my.confirm", locale),
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
            )
        if not is_terminal:
            rows.append(
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
                ]
            )
            if booking.status in {"pending_confirmation", "confirmed"}:
                rows.append(
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
                    ]
                )
            rows.append(
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
                ]
            )
        rows.append([InlineKeyboardButton(text=i18n.t("patient.home.nav.home", locale), callback_data="phome:home")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

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

    async def _render_existing_booking_control_panel(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        booking,
        session_state_token: str,
        header: str | None = None,
        send_fresh_from_callback: bool = False,
    ) -> None:
        locale = _locale()
        panel = _render_patient_booking_panel(booking=booking, session_state_token=session_state_token, locale=locale)
        keyboard = await _build_patient_booking_controls_keyboard(
            booking=booking,
            session_state_token=session_state_token,
            locale=locale,
        )
        flow = await _load_flow_state(actor_id)
        flow.booking_session_id = session_state_token
        flow.booking_mode = "existing_booking_control"
        flow.reschedule_booking_id = ""
        await _save_flow_state(actor_id, flow)
        text = f"{header}\n\n{panel}" if header else panel
        if send_fresh_from_callback and hasattr(message, "message"):
            await _send_fresh_booking_panel_from_callback(
                callback=message,
                actor_id=actor_id,
                session_id=session_state_token,
                text=text,
                keyboard=keyboard,
            )
            return
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_state_token,
            text=text,
            keyboard=keyboard,
        )

    def _render_waitlist_success_panel_header(*, locale: str) -> str:
        return "\n".join(
            [
                i18n.t("patient.booking.waitlist.created.title", locale),
                "",
                i18n.t("patient.booking.waitlist.created.body", locale),
                "",
                i18n.t("patient.booking.waitlist.created.current_booking", locale),
            ]
        )

    async def _render_waitlist_success_panel(
        message: Message | CallbackQuery,
        *,
        actor_id: int,
        callback_session_id: str,
        booking_id: str,
    ) -> None:
        locale = _locale()
        clinic_id = _primary_clinic_id()
        if clinic_id:
            started = await booking_flow.start_existing_booking_control_for_booking(
                clinic_id=clinic_id,
                telegram_user_id=actor_id,
                booking_id=booking_id,
            )
            booking = started.booking
            session = started.booking_session
            if started.kind == "ready" and booking is not None and session is not None:
                await _render_existing_booking_control_panel(
                    message,
                    actor_id=actor_id,
                    booking=booking,
                    session_state_token=session.booking_session_id,
                    header=_render_waitlist_success_panel_header(locale=locale),
                )
                return
        text = "\n".join([i18n.t("patient.booking.waitlist.created.title", locale), "", i18n.t("patient.booking.waitlist.created.body", locale)])
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=i18n.t("patient.booking.my.panel.title", locale), callback_data="phome:my_booking")],
                [InlineKeyboardButton(text=i18n.t("patient.home.nav.home", locale), callback_data="phome:home")],
            ]
        )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=callback_session_id,
            text=text,
            keyboard=keyboard,
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
        lines = [line for line in (header, i18n.t("patient.booking.reschedule.start.title", locale), i18n.t("patient.booking.reschedule.start.body_v2", locale), i18n.t("patient.booking.reschedule.start.note", locale)) if line]
        text = "\n\n".join(lines)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("patient.booking.reschedule.start.cta", locale),
                        callback_data=f"rsch:start:{session_id}",
                    )
                ],
                [InlineKeyboardButton(text=i18n.t("patient.booking.my.panel.title", locale), callback_data="phome:my_booking")],
                [InlineKeyboardButton(text=i18n.t("patient.home.nav.home", locale), callback_data="phome:home")],
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
        unavailable_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=i18n.t("patient.booking.my.panel.title", locale), callback_data="phome:my_booking")],
                [InlineKeyboardButton(text=i18n.t("patient.home.nav.home", locale), callback_data="phome:home")],
            ]
        )
        if clinic_id is None:
            text = f"{header}\n\n{fallback}" if header else fallback
            if send_fresh_from_callback and hasattr(message, "message"):
                await _send_fresh_booking_panel_from_callback(
                    callback=message,
                    actor_id=actor_id,
                    session_id=f"reschedule_unavailable:{actor_id}",
                    text=text,
                    keyboard=unavailable_keyboard,
                )
            else:
                await _send_or_edit_panel(
                    actor_id=actor_id,
                    message=message,
                    session_id=f"reschedule_unavailable:{actor_id}",
                    text=text,
                    keyboard=unavailable_keyboard,
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
                    keyboard=unavailable_keyboard,
                )
            else:
                await _send_or_edit_panel(
                    actor_id=actor_id,
                    message=message,
                    session_id=f"reschedule_unavailable:{actor_id}",
                    text=text,
                    keyboard=unavailable_keyboard,
                )
            return
        flow = await _load_flow_state(actor_id)
        flow.booking_session_id = started.booking_session.booking_session_id
        flow.booking_mode = "reschedule_booking_control"
        flow.reschedule_booking_id = booking_id
        _reset_slot_view_state(flow)
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
        flow.reschedule_booking_id = ""
        await _save_flow_state(callback.from_user.id, flow)
        await _render_existing_booking_control_panel(
            callback,
            actor_id=callback.from_user.id,
            booking=booking,
            session_state_token=session.booking_session_id,
            header=header,
            send_fresh_from_callback=True,
        )

    async def _show_existing_booking_result(message: Message, *, actor_id: int, result: BookingControlResolutionResult) -> None:
        locale = _locale()
        current_session_id = (await _load_flow_state(actor_id)).booking_session_id
        effective_session_id = result.booking_session.booking_session_id if result.booking_session else current_session_id
        if effective_session_id:
            flow = await _load_flow_state(actor_id)
            flow.booking_session_id = effective_session_id
            flow.booking_mode = "existing_booking_control"
            flow.reschedule_booking_id = ""
            await _save_flow_state(actor_id, flow)
        if result.kind == "ambiguous_escalated":
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=effective_session_id, text=i18n.t("patient.booking.escalated", locale))
            return
        if result.kind == "no_match":
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=effective_session_id,
                text=i18n.t("patient.booking.my.no_match", locale),
                keyboard=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text=i18n.t("patient.home.action.book", locale), callback_data="phome:book")],
                        [_patient_home_nav_button(locale=locale)],
                    ]
                ),
            )
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
