from pathlib import Path

from app.common.i18n import I18nService
from app.interfaces.bots.patient.router import (
    _CompactProductRowCard,
    _compose_product_object_list_text,
    _parse_gallery_index,
    _resolve_media_ref,
)
from app.interfaces.cards import (
    CareOrderCardAdapter,
    CareOrderRuntimeSnapshot,
    CareOrderRuntimeViewBuilder,
    CardAction,
    CardMode,
    ProductCardAdapter,
    ProductCardSeed,
    SourceContext,
    SourceRef,
)


def test_compact_product_row_grammar_supports_recommendation_and_category_contexts() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    seed = ProductCardSeed(
        product_id="prod-1",
        title="Nano Brush",
        price_label="25 GEL",
        availability_label="In stock",
        short_label="Soft",
        selected_branch_label="Main branch",
        recommendation_badge="Recommended",
        state_token="care:1",
    )
    category_row = _CompactProductRowCard(
        product_id="prod-1",
        shell=ProductCardAdapter.build(
            seed=seed,
            source=SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="care.catalog"),
            i18n=i18n,
            locale="en",
            mode=CardMode.LIST_ROW,
        ),
    )
    recommendation_row = _CompactProductRowCard(
        product_id="prod-1",
        shell=ProductCardAdapter.build(
            seed=seed,
            source=SourceRef(context=SourceContext.RECOMMENDATION_DETAIL, source_ref="care.recommendation"),
            i18n=i18n,
            locale="en",
            mode=CardMode.LIST_ROW,
        ),
    )

    assert category_row.button_label() == "Nano Brush · 25 GEL · In stock · Soft · Main branch"
    rec_label = recommendation_row.button_label()
    assert rec_label.startswith("Nano Brush · 25 GEL · In stock · Recommended")
    assert len(rec_label) <= 62
    assert category_row.supports_open_action()
    assert recommendation_row.supports_open_action()
    assert category_row.grammar_signature()[:2] == recommendation_row.grammar_signature()[:2]


def test_compact_product_row_renders_object_block_for_panel_body() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    seed = ProductCardSeed(
        product_id="prod-1",
        title="Nano Brush",
        price_label="25 GEL",
        availability_label="In stock",
        short_label="Soft",
        selected_branch_label="Main branch",
        recommendation_badge="Recommended",
        state_token="care:1",
    )
    row = _CompactProductRowCard(
        product_id="prod-1",
        shell=ProductCardAdapter.build(
            seed=seed,
            source=SourceRef(context=SourceContext.RECOMMENDATION_DETAIL, source_ref="care.recommendation"),
            i18n=i18n,
            locale="en",
            mode=CardMode.LIST_ROW,
        ),
    )
    block = row.object_block_lines(index=2)
    assert block[0] == "2. Nano Brush"
    assert "   - 25 GEL" in block
    assert "   - In stock" in block
    assert "   - Recommended" in block
    assert "   - Main branch" in block


def test_product_object_list_panel_composes_object_rows_not_single_text_lines() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    seed = ProductCardSeed(
        product_id="prod-1",
        title="Nano Brush",
        price_label="25 GEL",
        availability_label="In stock",
        short_label="Soft",
        selected_branch_label="Main branch",
        state_token="care:1",
    )
    rows = [
        _CompactProductRowCard(
            product_id="prod-1",
            shell=ProductCardAdapter.build(
                seed=seed,
                source=SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="care.catalog"),
                i18n=i18n,
                locale="en",
                mode=CardMode.LIST_ROW,
            ),
        )
    ]
    text = _compose_product_object_list_text(header_lines=["Care products", "Page 1"], row_cards=rows)
    assert "1. Nano Brush" in text
    assert "   - 25 GEL" in text
    assert "Care products" in text


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


def test_gallery_index_parser_is_bounded_and_stale_safe() -> None:
    assert _parse_gallery_index("gallery:0", total=3) == 0
    assert _parse_gallery_index("gallery:2", total=3) == 2
    assert _parse_gallery_index("gallery:999", total=3) == 2
    assert _parse_gallery_index("gallery:-5", total=3) == 0
    assert _parse_gallery_index("gallery:not-a-number", total=3) == 0
    assert _parse_gallery_index("gallery", total=3) == 0
    assert _parse_gallery_index("gallery:1", total=0) == 0


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
    assert "Open" in i18n.t("patient.care.orders.open.action", "en")
    assert "Reserve again" in i18n.t("patient.care.orders.repeat.action", "en")
    assert "Повторить" in i18n.t("patient.care.orders.repeat.action", "ru")


def test_repeat_order_object_detail_and_branch_reselect_strings_exist() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    assert "Order {care_order_id}" in i18n.t("patient.care.orders.object.detail", "en")
    assert "Pick another branch" in i18n.t("patient.care.orders.repeat.branch_select_required", "en")
    assert "режим совместимости" not in i18n.t("patient.care.orders.repeat.compat_hint", "en").lower()


def test_care_order_compact_object_uses_unified_card_grammar() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    seed = CareOrderRuntimeViewBuilder().build_seed(
        snapshot=CareOrderRuntimeSnapshot(
            care_order_id="co-1001",
            status="ready_for_pickup",
            total_amount=48,
            currency_code="GEL",
            item_summary="Nano Brush x1",
            branch_label="Main branch",
            pickup_ready=True,
            reservation_hint="Availability confirmed in branch Main branch.",
            state_token="care:77",
        ),
        i18n=i18n,
        locale="en",
    )

    row_shell = CareOrderCardAdapter.build(
        seed=seed,
        source=SourceRef(context=SourceContext.CARE_ORDER_LIST, source_ref="care.orders.list"),
        i18n=i18n,
        locale="en",
        mode=CardMode.LIST_ROW,
    )
    expanded_shell = CareOrderCardAdapter.build(
        seed=seed,
        source=SourceRef(context=SourceContext.CARE_ORDER_LIST, source_ref="care.orders.object"),
        i18n=i18n,
        locale="en",
        mode=CardMode.EXPANDED,
    )

    assert row_shell.mode == CardMode.LIST_ROW
    assert any(meta.key == "item" for meta in row_shell.meta_lines)
    assert any(meta.key == "pickup" for meta in row_shell.meta_lines)
    assert any(action.action == CardAction.OPEN for action in row_shell.actions)
    assert any(action.action == CardAction.RESERVE for action in row_shell.actions)
    assert expanded_shell.mode == CardMode.EXPANDED
    assert any("Timeline:" in line for line in expanded_shell.detail_lines)
    assert any(action.action == CardAction.BACK for action in expanded_shell.actions)
