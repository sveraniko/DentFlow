from pathlib import Path

from app.common.i18n import I18nService
from app.interfaces.bots.patient.router import _CompactProductPickerItem, _resolve_media_ref
from app.interfaces.cards import CardAction, CardMode, ProductCardAdapter, ProductCardSeed, SourceContext, SourceRef


def test_compact_product_row_grammar_supports_recommendation_and_category_contexts() -> None:
    category_row = _CompactProductPickerItem(
        product_id="prod-1",
        title="Nano Brush",
        price_amount=25,
        currency_code="GEL",
        availability="In stock",
        short_label="Soft",
        branch_hint="Main branch",
    )
    recommendation_row = _CompactProductPickerItem(
        product_id="prod-1",
        title="Nano Brush",
        price_amount=25,
        currency_code="GEL",
        availability="In stock",
        short_label="Soft",
        badge="Recommended",
        branch_hint="Main branch",
    )

    assert category_row.button_label() == "Nano Brush · 25 GEL · In stock · Soft · Main branch"
    rec_label = recommendation_row.button_label()
    assert rec_label.startswith("Nano Brush · 25 GEL · In stock · Recommended")
    assert len(rec_label) <= 62


def test_media_ref_resolution_supports_photo_video_and_missing_values() -> None:
    photo = _resolve_media_ref("photo:AgAC-telegram-file-id")
    assert photo is not None
    assert photo.media_kind == "photo"
    assert photo.media_value == "AgAC-telegram-file-id"

    gallery_video = _resolve_media_ref("https://cdn.example.com/care-gallery.mp4")
    assert gallery_video is not None
    assert gallery_video.media_kind == "video"

    fallback_photo = _resolve_media_ref("https://cdn.example.com/care-cover.jpg")
    assert fallback_photo is not None
    assert fallback_photo.media_kind == "photo"

    assert _resolve_media_ref("   ") is None


def test_compact_product_row_object_uses_unified_card_primitive_for_category_and_recommendation() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    seed = ProductCardSeed(
        product_id="prod-1",
        title="Nano Brush",
        short_label="Soft",
        price_label="25 GEL",
        availability_label="In stock",
        selected_branch_label="Main branch",
        recommendation_badge="Recommended",
        state_token="care:1",
    )
    category_row = ProductCardAdapter.build(
        seed=seed,
        source=SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="care.catalog"),
        i18n=i18n,
        locale="en",
        mode=CardMode.LIST_ROW,
    )
    recommendation_row = ProductCardAdapter.build(
        seed=seed,
        source=SourceRef(context=SourceContext.RECOMMENDATION_DETAIL, source_ref="care.recommendation"),
        i18n=i18n,
        locale="en",
        mode=CardMode.LIST_ROW,
    )

    assert category_row.mode == CardMode.LIST_ROW
    assert recommendation_row.mode == CardMode.LIST_ROW
    assert any(meta.key == "availability" for meta in category_row.meta_lines)
    assert any(meta.key == "branch" for meta in recommendation_row.meta_lines)
    assert any(action.action == CardAction.OPEN for action in category_row.actions)
    assert any(action.action == CardAction.OPEN for action in recommendation_row.actions)
    assert recommendation_row.badges


def test_media_caption_templates_avoid_raw_media_refs() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    assert "{media_ref}" not in i18n.t("patient.care.product.media.cover", "en")
    assert "{media_ref}" not in i18n.t("patient.care.product.media.gallery", "en")


def test_reserve_again_object_action_labels_are_localized() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    assert "Reserve again" in i18n.t("patient.care.orders.repeat.action", "en")
    assert "Повторить" in i18n.t("patient.care.orders.repeat.action", "ru")
