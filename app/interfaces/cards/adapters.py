from __future__ import annotations

from dataclasses import dataclass

from app.interfaces.cards.models import (
    CardAction,
    CardActionButton,
    CardMedia,
    CardMetaLine,
    CardMode,
    CardProfile,
    CardShell,
    EntityType,
    SourceRef,
)


@dataclass(slots=True, frozen=True)
class ProductCardSeed:
    product_id: str
    title: str
    price_label: str
    availability_label: str
    state_token: str


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
        detail = (f"Availability: {seed.availability_label}",) if mode == CardMode.EXPANDED else ()
        actions = (
            CardActionButton(action=CardAction.EXPAND, label="Подробнее")
            if mode == CardMode.COMPACT
            else CardActionButton(action=CardAction.COLLAPSE, label="Свернуть"),
            CardActionButton(action=CardAction.BACK, label="Назад"),
        )
        return CardShell(
            profile=CardProfile.PRODUCT,
            entity_type=EntityType.CARE_PRODUCT,
            entity_id=seed.product_id,
            mode=mode,
            title=seed.title,
            subtitle=None,
            source=source,
            state_token=seed.state_token,
            meta_lines=(
                CardMetaLine(key="price", value=seed.price_label),
                CardMetaLine(key="availability", value=seed.availability_label),
            ),
            detail_lines=detail,
            actions=actions,
            media=CardMedia(has_cover=True, gallery_size=0),
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
