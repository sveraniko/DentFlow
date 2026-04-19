from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

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


class CardLocalizer(Protocol):
    def t(self, key: str, locale: str | None = None) -> str: ...


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
    role_variant: str
    patient_label: str
    doctor_label: str
    service_label: str
    branch_label: str
    datetime_label: str
    local_time_hint: str | None
    status_label: str
    state_token: str
    compact_flags: tuple[str, ...] = ()
    reminder_summary: str | None = None
    reschedule_summary: str | None = None
    source_channel: str | None = None
    patient_contact_hint: str | None = None
    recommendation_summary: str | None = None
    care_order_summary: str | None = None
    chart_summary_entry: str | None = None
    next_step_note: str | None = None
    can_confirm: bool = False
    can_reschedule: bool = False
    can_cancel: bool = False
    can_mark_arrived: bool = False
    can_in_service: bool = False
    can_complete: bool = False
    can_open_patient: bool = False
    can_open_chart: bool = False
    can_open_recommendation: bool = False
    can_open_care_order: bool = False


@dataclass(slots=True, frozen=True)
class ProductRuntimeSnapshot:
    product_id: str
    sku: str
    state_token: str
    price_amount: int
    currency_code: str
    status: str
    available_qty: int | None = None
    title_by_locale: dict[str, str] | None = None
    description_by_locale: dict[str, str] | None = None
    category: str | None = None
    usage_hint: str | None = None
    selected_branch_label: str | None = None
    recommendation_badge: str | None = None
    recommendation_rationale: str | None = None
    media_count: int = 0


@dataclass(slots=True, frozen=True)
class PatientRuntimeSnapshot:
    patient_id: str
    state_token: str
    display_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    patient_number: str | None = None
    primary_contact: str | None = None
    is_photo_present: bool = False
    active_flags: tuple[str, ...] = ()
    upcoming_booking_label: str | None = None
    recommendation_summary: str | None = None
    care_order_summary: str | None = None
    chart_summary_entry: str | None = None


@dataclass(slots=True, frozen=True)
class DoctorRuntimeSnapshot:
    doctor_id: str
    state_token: str
    display_name: str
    specialty: str | None = None
    branch_label: str | None = None
    today_queue_size: int | None = None
    today_bookings: int | None = None
    schedule_summary: str | None = None
    service_tags: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class BookingRuntimeSnapshot:
    booking_id: str
    state_token: str
    role_variant: str
    scheduled_start_at: datetime
    timezone_name: str = "UTC"
    patient_label: str = "-"
    doctor_label: str = "-"
    service_label: str = "-"
    branch_label: str = "-"
    status: str = "pending_confirmation"
    compact_flags: tuple[str, ...] = ()
    reminder_summary: str | None = None
    reschedule_summary: str | None = None
    source_channel: str | None = None
    patient_contact: str | None = None
    recommendation_summary: str | None = None
    care_order_summary: str | None = None
    chart_summary_entry: str | None = None
    next_step_note_key: str | None = None


@dataclass(slots=True, frozen=True)
class ProductRuntimeViewBuilder:
    def build_seed(self, *, snapshot: ProductRuntimeSnapshot, i18n: CardLocalizer, locale: str) -> ProductCardSeed:
        title = (snapshot.title_by_locale or {}).get(locale) or (snapshot.title_by_locale or {}).get("en") or snapshot.sku
        description = None
        if snapshot.description_by_locale:
            description = snapshot.description_by_locale.get(locale) or snapshot.description_by_locale.get("en")
        availability = i18n.t("patient.care.availability.out", locale)
        if snapshot.status == "active" and (snapshot.available_qty or 0) > 0:
            availability = i18n.t("patient.care.availability.low", locale) if (snapshot.available_qty or 0) <= 2 else i18n.t("patient.care.availability.in", locale)
        return ProductCardSeed(
            product_id=snapshot.product_id,
            title=title,
            short_label=snapshot.sku,
            price_label=f"{snapshot.price_amount} {snapshot.currency_code}",
            availability_label=availability,
            localized_description=description,
            usage_hint=snapshot.usage_hint,
            category=snapshot.category,
            selected_branch_label=snapshot.selected_branch_label,
            recommendation_badge=snapshot.recommendation_badge,
            recommendation_rationale=snapshot.recommendation_rationale,
            media_count=snapshot.media_count,
            state_token=snapshot.state_token,
        )


@dataclass(slots=True, frozen=True)
class PatientRuntimeViewBuilder:
    def build_seed(self, *, snapshot: PatientRuntimeSnapshot) -> PatientCardSeed:
        display_name = snapshot.display_name
        if not display_name:
            parts = [part for part in (snapshot.first_name, snapshot.last_name) if part]
            display_name = " ".join(parts) if parts else snapshot.patient_id
        active_flags_summary = ", ".join(snapshot.active_flags) if snapshot.active_flags else None
        return PatientCardSeed(
            patient_id=snapshot.patient_id,
            display_name=display_name,
            state_token=snapshot.state_token,
            patient_number=snapshot.patient_number,
            contact_hint=_masked_contact(snapshot.primary_contact),
            photo_present=snapshot.is_photo_present,
            active_flags_summary=active_flags_summary,
            booking_snippet=snapshot.upcoming_booking_label,
            contact_block=snapshot.primary_contact,
            recommendation_summary=snapshot.recommendation_summary,
            care_order_summary=snapshot.care_order_summary,
            chart_summary_entry=snapshot.chart_summary_entry,
        )


@dataclass(slots=True, frozen=True)
class DoctorRuntimeViewBuilder:
    def build_seed(self, *, snapshot: DoctorRuntimeSnapshot) -> DoctorCardSeed:
        queue_summary = None
        if snapshot.today_queue_size is not None:
            queue_summary = f"{snapshot.today_queue_size} waiting"
        operational_hint = None
        if snapshot.today_bookings is not None:
            operational_hint = f"Today: {snapshot.today_bookings} bookings"
        return DoctorCardSeed(
            doctor_id=snapshot.doctor_id,
            display_name=snapshot.display_name,
            specialty=snapshot.specialty or "general",
            state_token=snapshot.state_token,
            branch_label=snapshot.branch_label,
            operational_hint=operational_hint,
            schedule_summary=snapshot.schedule_summary,
            queue_summary=queue_summary,
            service_tags=snapshot.service_tags,
        )


@dataclass(slots=True, frozen=True)
class BookingRuntimeViewBuilder:
    def build_seed(self, *, snapshot: BookingRuntimeSnapshot, i18n: CardLocalizer, locale: str) -> BookingCardSeed:
        tz = ZoneInfo(snapshot.timezone_name) if snapshot.timezone_name else timezone.utc
        local_dt = snapshot.scheduled_start_at.astimezone(tz)
        status_label = i18n.t(f"booking.status.{snapshot.status}", locale)
        next_step_note = i18n.t(snapshot.next_step_note_key, locale) if snapshot.next_step_note_key else None
        visibility = _booking_visibility(snapshot.role_variant, snapshot.status)
        return BookingCardSeed(
            booking_id=snapshot.booking_id,
            role_variant=snapshot.role_variant,
            patient_label=snapshot.patient_label,
            doctor_label=snapshot.doctor_label,
            service_label=snapshot.service_label,
            branch_label=snapshot.branch_label,
            datetime_label=local_dt.strftime("%Y-%m-%d %H:%M"),
            local_time_hint=snapshot.timezone_name,
            status_label=status_label,
            state_token=snapshot.state_token,
            compact_flags=snapshot.compact_flags,
            reminder_summary=snapshot.reminder_summary,
            reschedule_summary=snapshot.reschedule_summary,
            source_channel=snapshot.source_channel,
            patient_contact_hint=_masked_contact(snapshot.patient_contact),
            recommendation_summary=snapshot.recommendation_summary,
            care_order_summary=snapshot.care_order_summary,
            chart_summary_entry=snapshot.chart_summary_entry,
            next_step_note=next_step_note,
            can_confirm=visibility["confirm"],
            can_reschedule=visibility["reschedule"],
            can_cancel=visibility["cancel"],
            can_mark_arrived=visibility["checked_in"],
            can_in_service=visibility["in_service"],
            can_complete=visibility["complete"],
            can_open_patient=visibility["open_patient"],
            can_open_chart=visibility["open_chart"],
            can_open_recommendation=visibility["open_recommendation"] and bool(snapshot.recommendation_summary),
            can_open_care_order=visibility["open_care_order"] and bool(snapshot.care_order_summary),
        )


def _booking_visibility(role_variant: str, status: str) -> dict[str, bool]:
    terminal = status in {"completed", "canceled", "no_show"}
    patient = role_variant == "patient"
    admin = role_variant == "admin"
    doctor = role_variant == "doctor"
    owner = role_variant == "owner"
    return {
        "confirm": (patient or admin) and status == "pending_confirmation",
        "reschedule": (patient or admin) and not terminal,
        "cancel": (patient or admin) and not terminal,
        "checked_in": admin and status in {"confirmed", "reschedule_requested"},
        "in_service": doctor and status in {"checked_in", "confirmed"},
        "complete": doctor and status == "in_service",
        "open_patient": admin or doctor,
        "open_chart": admin or doctor,
        "open_recommendation": not owner,
        "open_care_order": not owner,
    }


def _masked_contact(contact: str | None) -> str | None:
    if not contact:
        return None
    if len(contact) <= 4:
        return "***"
    return f"***{contact[-4:]}"


class ProductCardAdapter:
    @staticmethod
    def build(
        *,
        seed: ProductCardSeed,
        source: SourceRef,
        i18n: CardLocalizer,
        locale: str,
        mode: CardMode = CardMode.COMPACT,
    ) -> CardShell:
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
                detail_lines.append(i18n.t("card.product.detail.usage", locale).format(value=seed.usage_hint))
            if seed.category:
                detail_lines.append(i18n.t("card.product.detail.category", locale).format(value=seed.category))
            if source.context == SourceContext.RECOMMENDATION_DETAIL and seed.recommendation_rationale:
                detail_lines.append(i18n.t("card.product.detail.recommendation", locale).format(value=seed.recommendation_rationale))
            if source.context == SourceContext.CARE_CATALOG_CATEGORY and seed.category:
                detail_lines.append(i18n.t("card.product.detail.opened_from_category", locale).format(value=seed.category))

        actions: list[CardActionButton] = []
        actions.append(
            CardActionButton(action=CardAction.EXPAND, label=i18n.t("card.action.expand", locale))
            if mode == CardMode.COMPACT
            else CardActionButton(action=CardAction.COLLAPSE, label=i18n.t("card.action.collapse", locale))
        )
        if mode == CardMode.EXPANDED:
            actions.extend(
                [
                    CardActionButton(action=CardAction.RESERVE, label=i18n.t("card.product.action.reserve", locale)),
                    CardActionButton(action=CardAction.CHANGE_BRANCH, label=i18n.t("card.product.action.change_branch", locale)),
                ]
            )
            if seed.media_count > 0:
                actions.append(CardActionButton(action=CardAction.COVER, label=i18n.t("card.action.cover", locale)))
            if seed.media_count > 1:
                actions.append(CardActionButton(action=CardAction.GALLERY, label=i18n.t("card.action.gallery", locale)))
        actions.append(CardActionButton(action=CardAction.BACK, label=i18n.t("common.back", locale)))

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
        i18n: CardLocalizer,
        locale: str,
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
                subtitle=i18n.t("card.common.limited_access", locale),
                source=source,
                state_token=seed.state_token,
                detail_lines=(i18n.t("card.common.access_denied", locale),),
                actions=(CardActionButton(action=CardAction.BACK, label=i18n.t("common.back", locale)),),
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
                detail_lines.append(i18n.t("card.patient.detail.contact", locale).format(value=seed.contact_block))
            if seed.active_flags_summary:
                detail_lines.append(i18n.t("card.patient.detail.flags", locale).format(value=seed.active_flags_summary))
            if seed.booking_snippet:
                detail_lines.append(i18n.t("card.patient.detail.upcoming", locale).format(value=seed.booking_snippet))
            if source.context in {SourceContext.SEARCH_RESULTS, SourceContext.BOOKING_LIST} and seed.recommendation_summary:
                detail_lines.append(i18n.t("card.patient.detail.recommendations", locale).format(value=seed.recommendation_summary))
            if seed.care_order_summary:
                detail_lines.append(i18n.t("card.patient.detail.orders", locale).format(value=seed.care_order_summary))
            if seed.chart_summary_entry:
                detail_lines.append(i18n.t("card.patient.detail.chart", locale).format(value=seed.chart_summary_entry))

        actions = [
            CardActionButton(
                action=(CardAction.EXPAND if mode == CardMode.COMPACT else CardAction.COLLAPSE),
                label=(i18n.t("card.action.expand", locale) if mode == CardMode.COMPACT else i18n.t("card.action.collapse", locale)),
            ),
            CardActionButton(action=CardAction.BOOKINGS, label=i18n.t("card.patient.action.bookings", locale)),
        ]
        if RoleCode.DOCTOR in actor_roles or RoleCode.ADMIN in actor_roles:
            actions.append(CardActionButton(action=CardAction.RECOMMENDATIONS, label=i18n.t("card.patient.action.recommendations", locale)))
            actions.append(CardActionButton(action=CardAction.CHART, label=i18n.t("card.patient.action.chart", locale)))
            actions.append(CardActionButton(action=CardAction.ORDERS, label=i18n.t("card.patient.action.orders", locale)))
        actions.append(CardActionButton(action=CardAction.BACK, label=i18n.t("common.back", locale)))

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
        i18n: CardLocalizer,
        locale: str,
        mode: CardMode = CardMode.COMPACT,
    ) -> CardShell:
        if not actor_roles.intersection(DoctorCardAdapter._ALLOWED_ROLES):
            return CardShell(
                profile=CardProfile.DOCTOR,
                entity_type=EntityType.DOCTOR,
                entity_id=seed.doctor_id,
                mode=mode,
                title=seed.display_name,
                subtitle=i18n.t("card.common.limited_access", locale),
                source=source,
                state_token=seed.state_token,
                detail_lines=(i18n.t("card.common.access_denied", locale),),
                actions=(CardActionButton(action=CardAction.BACK, label=i18n.t("common.back", locale)),),
            )

        meta_lines = [CardMetaLine(key="specialty", value=seed.specialty)]
        if seed.branch_label:
            meta_lines.append(CardMetaLine(key="branch", value=seed.branch_label))
        if seed.operational_hint:
            meta_lines.append(CardMetaLine(key="hint", value=seed.operational_hint))

        detail_lines: list[str] = []
        if mode == CardMode.EXPANDED:
            if seed.schedule_summary:
                detail_lines.append(i18n.t("card.doctor.detail.schedule", locale).format(value=seed.schedule_summary))
            if seed.queue_summary:
                detail_lines.append(i18n.t("card.doctor.detail.queue", locale).format(value=seed.queue_summary))
            if seed.service_tags:
                detail_lines.append(i18n.t("card.doctor.detail.tags", locale).format(value=", ".join(seed.service_tags)))

        actions = [
            CardActionButton(
                action=(CardAction.EXPAND if mode == CardMode.COMPACT else CardAction.COLLAPSE),
                label=(i18n.t("card.action.expand", locale) if mode == CardMode.COMPACT else i18n.t("card.action.collapse", locale)),
            ),
            CardActionButton(action=CardAction.TODAY, label=i18n.t("card.doctor.action.today", locale)),
            CardActionButton(action=CardAction.SCHEDULE, label=i18n.t("card.doctor.action.schedule", locale)),
            CardActionButton(action=CardAction.OPEN, label=i18n.t("card.doctor.action.open", locale)),
            CardActionButton(action=CardAction.BACK, label=i18n.t("common.back", locale)),
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
    def build(*, seed: BookingCardSeed, source: SourceRef, i18n: CardLocalizer, locale: str, mode: CardMode = CardMode.COMPACT) -> CardShell:
        title = f"{seed.datetime_label} · {seed.patient_label}"
        subtitle = f"{seed.doctor_label} · {seed.service_label} · {seed.branch_label}"
        badges = [CardBadge(seed.status_label), *[CardBadge(flag) for flag in seed.compact_flags[:3]]]
        meta_lines = [
            CardMetaLine(key="patient", value=seed.patient_label),
            CardMetaLine(key="doctor", value=seed.doctor_label),
            CardMetaLine(key="service", value=seed.service_label),
            CardMetaLine(key="branch", value=seed.branch_label),
            CardMetaLine(key="status", value=seed.status_label),
        ]
        if seed.local_time_hint:
            meta_lines.insert(0, CardMetaLine(key="time", value=f"{seed.datetime_label} ({seed.local_time_hint})"))

        detail_lines: list[str] = []
        if mode == CardMode.EXPANDED:
            if seed.source_channel:
                detail_lines.append(i18n.t("card.booking.detail.source", locale).format(value=seed.source_channel))
            if seed.patient_contact_hint and seed.role_variant in {"admin", "doctor"}:
                detail_lines.append(i18n.t("card.booking.detail.contact", locale).format(value=seed.patient_contact_hint))
            if seed.reminder_summary:
                detail_lines.append(i18n.t("card.booking.detail.reminder", locale).format(value=seed.reminder_summary))
            if seed.reschedule_summary:
                detail_lines.append(i18n.t("card.booking.detail.reschedule", locale).format(value=seed.reschedule_summary))
            if seed.recommendation_summary:
                detail_lines.append(i18n.t("card.booking.detail.recommendation", locale).format(value=seed.recommendation_summary))
            if seed.care_order_summary:
                detail_lines.append(i18n.t("card.booking.detail.care_order", locale).format(value=seed.care_order_summary))
            if seed.chart_summary_entry:
                detail_lines.append(i18n.t("card.booking.detail.chart", locale).format(value=seed.chart_summary_entry))
            if seed.next_step_note:
                detail_lines.append(i18n.t("card.booking.detail.next_step", locale).format(value=seed.next_step_note))

        actions: list[CardActionButton] = [
            CardActionButton(
                action=(CardAction.EXPAND if mode == CardMode.COMPACT else CardAction.COLLAPSE),
                label=(i18n.t("card.action.expand", locale) if mode == CardMode.COMPACT else i18n.t("card.action.collapse", locale)),
            )
        ]
        if seed.can_confirm:
            actions.append(CardActionButton(action=CardAction.CONFIRM, label=i18n.t("card.booking.action.confirm", locale)))
        if seed.can_mark_arrived:
            actions.append(CardActionButton(action=CardAction.CHECKED_IN, label=i18n.t("card.booking.action.arrived", locale)))
        if seed.can_in_service:
            actions.append(CardActionButton(action=CardAction.IN_SERVICE, label=i18n.t("card.booking.action.in_service", locale)))
        if seed.can_complete:
            actions.append(CardActionButton(action=CardAction.COMPLETE, label=i18n.t("card.booking.action.complete", locale)))
        if seed.can_reschedule:
            actions.append(CardActionButton(action=CardAction.RESCHEDULE, label=i18n.t("card.booking.action.reschedule", locale)))
        if seed.can_cancel:
            actions.append(CardActionButton(action=CardAction.CANCEL, label=i18n.t("card.booking.action.cancel", locale)))
        if mode == CardMode.EXPANDED and seed.can_open_patient:
            actions.append(CardActionButton(action=CardAction.OPEN_PATIENT, label=i18n.t("card.booking.action.patient", locale)))
        if mode == CardMode.EXPANDED and seed.can_open_chart:
            actions.append(CardActionButton(action=CardAction.OPEN_CHART, label=i18n.t("card.booking.action.chart", locale)))
        if mode == CardMode.EXPANDED and seed.can_open_recommendation:
            actions.append(CardActionButton(action=CardAction.OPEN_RECOMMENDATION, label=i18n.t("card.booking.action.recommendation", locale)))
        if mode == CardMode.EXPANDED and seed.can_open_care_order:
            actions.append(CardActionButton(action=CardAction.OPEN_CARE_ORDER, label=i18n.t("card.booking.action.care_order", locale)))
        actions.append(CardActionButton(action=CardAction.BACK, label=i18n.t("common.back", locale)))

        return CardShell(
            profile=CardProfile.BOOKING,
            entity_type=EntityType.BOOKING,
            entity_id=seed.booking_id,
            mode=mode,
            title=title,
            subtitle=subtitle,
            source=source,
            state_token=seed.state_token,
            badges=tuple(badges),
            meta_lines=tuple(meta_lines),
            detail_lines=tuple(detail_lines),
            actions=tuple(actions),
        )
