from __future__ import annotations

from dataclasses import dataclass

from app.domain.access_identity.models import RoleCode
from app.interfaces.cards.models import (
    CardAction,
    CardActionButton,
    CardBadge,
    CardMedia,
    CardMetaLine,
    CardMode,
    CardProfile,
    CardShell,
    EntityType,
    SourceContext,
    SourceRef,
)


@dataclass(slots=True, frozen=True)
class ProductCardSeed:
    product_id: str
    title: str
    price_label: str
    availability_label: str
    state_token: str
    short_label: str | None = None
    localized_description: str | None = None
    usage_hint: str | None = None
    category: str | None = None
    selected_branch_label: str | None = None
    recommendation_badge: str | None = None
    recommendation_rationale: str | None = None
    media_count: int = 0


@dataclass(slots=True, frozen=True)
class PatientCardSeed:
    patient_id: str
    display_name: str
    state_token: str
    patient_number: str | None = None
    contact_hint: str | None = None
    photo_present: bool = False
    active_flags_summary: str | None = None
    booking_snippet: str | None = None
    contact_block: str | None = None
    recommendation_summary: str | None = None
    care_order_summary: str | None = None
    chart_summary_entry: str | None = None


@dataclass(slots=True, frozen=True)
class DoctorCardSeed:
    doctor_id: str
    display_name: str
    specialty: str
    state_token: str
    branch_label: str | None = None
    operational_hint: str | None = None
    schedule_summary: str | None = None
    queue_summary: str | None = None
    service_tags: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class BookingCardSeed:
    booking_id: str
    title: str
    status_label: str
    datetime_label: str
    state_token: str


class ProductCardAdapter:
    @staticmethod
    def build(*, seed: ProductCardSeed, source: SourceRef, mode: CardMode = CardMode.COMPACT) -> CardShell:
        badges: list[CardBadge] = []
        if seed.recommendation_badge and source.context == SourceContext.RECOMMENDATION_DETAIL:
            badges.append(CardBadge(seed.recommendation_badge))

        meta_lines = [
            CardMetaLine(key="price", value=seed.price_label),
            CardMetaLine(key="availability", value=seed.availability_label),
        ]
        if seed.short_label:
            meta_lines.insert(0, CardMetaLine(key="label", value=seed.short_label))
        if seed.selected_branch_label:
            meta_lines.append(CardMetaLine(key="branch", value=seed.selected_branch_label))

        detail_lines: list[str] = []
        if mode == CardMode.EXPANDED:
            if seed.localized_description:
                detail_lines.append(seed.localized_description)
            if seed.usage_hint:
                detail_lines.append(f"Usage: {seed.usage_hint}")
            if seed.category:
                detail_lines.append(f"Category: {seed.category}")
            if source.context == SourceContext.RECOMMENDATION_DETAIL and seed.recommendation_rationale:
                detail_lines.append(f"Recommendation: {seed.recommendation_rationale}")
            if source.context == SourceContext.CARE_CATALOG_CATEGORY and seed.category:
                detail_lines.append(f"Opened from category: {seed.category}")

        actions: list[CardActionButton] = []
        actions.append(
            CardActionButton(action=CardAction.EXPAND, label="Подробнее")
            if mode == CardMode.COMPACT
            else CardActionButton(action=CardAction.COLLAPSE, label="Свернуть")
        )
        if mode == CardMode.EXPANDED:
            actions.extend(
                [
                    CardActionButton(action=CardAction.RESERVE, label="Забрать в клинике"),
                    CardActionButton(action=CardAction.CHANGE_BRANCH, label="Сменить филиал"),
                ]
            )
            if seed.media_count > 0:
                actions.append(CardActionButton(action=CardAction.COVER, label="Обложка"))
            if seed.media_count > 1:
                actions.append(CardActionButton(action=CardAction.GALLERY, label="Галерея"))
        actions.append(CardActionButton(action=CardAction.BACK, label="Назад"))

        return CardShell(
            profile=CardProfile.PRODUCT,
            entity_type=EntityType.CARE_PRODUCT,
            entity_id=seed.product_id,
            mode=mode,
            title=seed.title,
            subtitle=None,
            source=source,
            state_token=seed.state_token,
            badges=tuple(badges),
            meta_lines=tuple(meta_lines),
            detail_lines=tuple(detail_lines),
            actions=tuple(actions),
            media=CardMedia(has_cover=seed.media_count > 0, gallery_size=max(seed.media_count - 1, 0)),
        )


class PatientCardAdapter:
    _ALLOWED_ROLES = {RoleCode.ADMIN, RoleCode.DOCTOR}

    @staticmethod
    def build(
        *,
        seed: PatientCardSeed,
        source: SourceRef,
        actor_roles: set[RoleCode],
        mode: CardMode = CardMode.COMPACT,
    ) -> CardShell:
        role_safe = bool(actor_roles.intersection(PatientCardAdapter._ALLOWED_ROLES))
        if not role_safe:
            return CardShell(
                profile=CardProfile.PATIENT,
                entity_type=EntityType.PATIENT,
                entity_id=seed.patient_id,
                mode=mode,
                title=seed.display_name,
                subtitle="Limited access",
                source=source,
                state_token=seed.state_token,
                detail_lines=("Access denied for this profile.",),
                actions=(CardActionButton(action=CardAction.BACK, label="Назад"),),
            )

        meta_lines = []
        if seed.patient_number:
            meta_lines.append(CardMetaLine(key="patient_no", value=seed.patient_number))
        if seed.contact_hint:
            meta_lines.append(CardMetaLine(key="contact", value=seed.contact_hint))
        meta_lines.append(CardMetaLine(key="photo", value=("yes" if seed.photo_present else "no")))
        if seed.active_flags_summary:
            meta_lines.append(CardMetaLine(key="flags", value=seed.active_flags_summary))
        if seed.booking_snippet:
            meta_lines.append(CardMetaLine(key="booking", value=seed.booking_snippet))

        detail_lines: list[str] = []
        if mode == CardMode.EXPANDED:
            if seed.contact_block:
                detail_lines.append(f"Contact: {seed.contact_block}")
            if seed.active_flags_summary:
                detail_lines.append(f"Flags: {seed.active_flags_summary}")
            if seed.booking_snippet:
                detail_lines.append(f"Upcoming: {seed.booking_snippet}")
            if source.context in {SourceContext.SEARCH_RESULTS, SourceContext.BOOKING_LIST} and seed.recommendation_summary:
                detail_lines.append(f"Recommendations: {seed.recommendation_summary}")
            if seed.care_order_summary:
                detail_lines.append(f"Orders: {seed.care_order_summary}")
            if seed.chart_summary_entry:
                detail_lines.append(f"Chart: {seed.chart_summary_entry}")

        actions = [
            CardActionButton(action=(CardAction.EXPAND if mode == CardMode.COMPACT else CardAction.COLLAPSE), label=("Подробнее" if mode == CardMode.COMPACT else "Свернуть")),
            CardActionButton(action=CardAction.BOOKINGS, label="Записи"),
        ]
        if RoleCode.DOCTOR in actor_roles or RoleCode.ADMIN in actor_roles:
            actions.append(CardActionButton(action=CardAction.RECOMMENDATIONS, label="Рекомендации"))
            actions.append(CardActionButton(action=CardAction.CHART, label="Карта"))
            actions.append(CardActionButton(action=CardAction.ORDERS, label="Заказы"))
        actions.append(CardActionButton(action=CardAction.BACK, label="Назад"))

        return CardShell(
            profile=CardProfile.PATIENT,
            entity_type=EntityType.PATIENT,
            entity_id=seed.patient_id,
            mode=mode,
            title=seed.display_name,
            subtitle=seed.booking_snippet,
            source=source,
            state_token=seed.state_token,
            meta_lines=tuple(meta_lines),
            detail_lines=tuple(detail_lines),
            actions=tuple(actions),
        )


class DoctorCardAdapter:
    _ALLOWED_ROLES = {RoleCode.ADMIN, RoleCode.DOCTOR}

    @staticmethod
    def build(
        *,
        seed: DoctorCardSeed,
        source: SourceRef,
        actor_roles: set[RoleCode],
        mode: CardMode = CardMode.COMPACT,
    ) -> CardShell:
        if not actor_roles.intersection(DoctorCardAdapter._ALLOWED_ROLES):
            return CardShell(
                profile=CardProfile.DOCTOR,
                entity_type=EntityType.DOCTOR,
                entity_id=seed.doctor_id,
                mode=mode,
                title=seed.display_name,
                subtitle="Limited access",
                source=source,
                state_token=seed.state_token,
                detail_lines=("Access denied for this profile.",),
                actions=(CardActionButton(action=CardAction.BACK, label="Назад"),),
            )

        meta_lines = [CardMetaLine(key="specialty", value=seed.specialty)]
        if seed.branch_label:
            meta_lines.append(CardMetaLine(key="branch", value=seed.branch_label))
        if seed.operational_hint:
            meta_lines.append(CardMetaLine(key="hint", value=seed.operational_hint))

        detail_lines: list[str] = []
        if mode == CardMode.EXPANDED:
            if seed.schedule_summary:
                detail_lines.append(f"Schedule: {seed.schedule_summary}")
            if seed.queue_summary:
                detail_lines.append(f"Queue: {seed.queue_summary}")
            if seed.service_tags:
                detail_lines.append("Tags: " + ", ".join(seed.service_tags))

        actions = [
            CardActionButton(action=(CardAction.EXPAND if mode == CardMode.COMPACT else CardAction.COLLAPSE), label=("Подробнее" if mode == CardMode.COMPACT else "Свернуть")),
            CardActionButton(action=CardAction.TODAY, label="Сегодня"),
            CardActionButton(action=CardAction.SCHEDULE, label="График"),
            CardActionButton(action=CardAction.OPEN, label="Открыть"),
            CardActionButton(action=CardAction.BACK, label="Назад"),
        ]

        return CardShell(
            profile=CardProfile.DOCTOR,
            entity_type=EntityType.DOCTOR,
            entity_id=seed.doctor_id,
            mode=mode,
            title=seed.display_name,
            subtitle=seed.operational_hint,
            source=source,
            state_token=seed.state_token,
            meta_lines=tuple(meta_lines),
            detail_lines=tuple(detail_lines),
            actions=tuple(actions),
        )


class BookingCardAdapter:
    @staticmethod
    def build(*, seed: BookingCardSeed, source: SourceRef, mode: CardMode = CardMode.COMPACT) -> CardShell:
        actions = (
            CardActionButton(action=CardAction.EXPAND, label="Подробнее")
            if mode == CardMode.COMPACT
            else CardActionButton(action=CardAction.COLLAPSE, label="Свернуть"),
            CardActionButton(action=CardAction.BACK, label="Назад"),
        )
        return CardShell(
            profile=CardProfile.BOOKING,
            entity_type=EntityType.BOOKING,
            entity_id=seed.booking_id,
            mode=mode,
            title=seed.title,
            subtitle=seed.datetime_label,
            source=source,
            state_token=seed.state_token,
            meta_lines=(CardMetaLine(key="status", value=seed.status_label),),
            detail_lines=((f"Time: {seed.datetime_label}",) if mode == CardMode.EXPANDED else ()),
            actions=actions,
        )
