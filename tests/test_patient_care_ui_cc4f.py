from pathlib import Path

from app.common.i18n import I18nService
from app.interfaces.bots.patient.router import (
    _CompactCareOrderRowCard,
    _compose_care_order_object_list_text,
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


def test_product_object_rows_share_unified_grammar_across_recommendation_and_category() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    seed = ProductCardSeed(
        product_id="prod-cc4f-1",
        title="Hydro Rinse",
        short_label="Daily care",
        price_label="19 GEL",
        availability_label="In stock",
        selected_branch_label="Central branch",
        recommendation_badge="Recommended",
        state_token="care:1",
    )

    row_category = ProductCardAdapter.build(
        seed=seed,
        source=SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="care.catalog"),
        i18n=i18n,
        locale="en",
        mode=CardMode.LIST_ROW,
    )
    row_recommendation = ProductCardAdapter.build(
        seed=seed,
        source=SourceRef(context=SourceContext.RECOMMENDATION_DETAIL, source_ref="care.recommendation"),
        i18n=i18n,
        locale="en",
        mode=CardMode.LIST_ROW,
    )

    assert row_category.mode == CardMode.LIST_ROW
    assert row_recommendation.mode == CardMode.LIST_ROW
    assert [meta.key for meta in row_category.meta_lines] == [meta.key for meta in row_recommendation.meta_lines]
    assert any(action.action == CardAction.OPEN for action in row_category.actions)
    assert any(action.action == CardAction.OPEN for action in row_recommendation.actions)


def test_product_object_open_path_keeps_detail_card_actions_intact() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    seed = ProductCardSeed(
        product_id="prod-cc4f-2",
        title="Night Gel",
        short_label="Sensitive",
        price_label="22 GEL",
        availability_label="Low stock",
        selected_branch_label="North branch",
        recommendation_badge="Recommended",
        recommendation_rationale="Post-procedure support",
        state_token="care:2",
    )

    list_row = ProductCardAdapter.build(
        seed=seed,
        source=SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="care.catalog.products"),
        i18n=i18n,
        locale="en",
        mode=CardMode.LIST_ROW,
    )
    compact_detail = ProductCardAdapter.build(
        seed=seed,
        source=SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="care.product"),
        i18n=i18n,
        locale="en",
        mode=CardMode.COMPACT,
    )
    expanded_detail = ProductCardAdapter.build(
        seed=seed,
        source=SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="care.product"),
        i18n=i18n,
        locale="en",
        mode=CardMode.EXPANDED,
    )

    assert any(action.action == CardAction.OPEN for action in list_row.actions)
    assert any(action.action == CardAction.EXPAND for action in compact_detail.actions)
    assert any(action.action == CardAction.RESERVE for action in expanded_detail.actions)
    assert any(action.action == CardAction.BACK for action in expanded_detail.actions)


def test_care_order_object_rows_and_expanded_view_expose_object_actions() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    seed = CareOrderRuntimeViewBuilder().build_seed(
        snapshot=CareOrderRuntimeSnapshot(
            care_order_id="co-cc4f-1",
            status="ready_for_pickup",
            total_amount=48,
            currency_code="GEL",
            item_summary="Hydro Rinse x1",
            branch_label="Central branch",
            pickup_ready=True,
            reservation_hint="Availability confirmed in branch Central branch.",
            issued=False,
            fulfilled=False,
            state_token="care:9",
        ),
        i18n=i18n,
        locale="en",
    )

    row = CareOrderCardAdapter.build(
        seed=seed,
        source=SourceRef(context=SourceContext.CARE_ORDER_LIST, source_ref="care.orders.row"),
        i18n=i18n,
        locale="en",
        mode=CardMode.LIST_ROW,
    )
    expanded = CareOrderCardAdapter.build(
        seed=seed,
        source=SourceRef(context=SourceContext.CARE_ORDER_LIST, source_ref="care.orders.object"),
        i18n=i18n,
        locale="en",
        mode=CardMode.EXPANDED,
    )

    assert any(meta.key == "item" for meta in row.meta_lines)
    assert any(meta.key == "branch" for meta in row.meta_lines)
    assert any(meta.key == "pickup" for meta in row.meta_lines)
    assert any(action.action == CardAction.OPEN for action in row.actions)
    assert any(action.action == CardAction.RESERVE for action in row.actions)
    assert any(action.action == CardAction.RESERVE for action in expanded.actions)
    assert any(action.action == CardAction.BACK for action in expanded.actions)


def test_care_order_row_object_block_renders_identity_item_branch_status_and_pickup() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    seed = CareOrderRuntimeViewBuilder().build_seed(
        snapshot=CareOrderRuntimeSnapshot(
            care_order_id="co-cc4f-2",
            status="ready_for_pickup",
            total_amount=41,
            currency_code="GEL",
            item_summary="Night Gel x1",
            branch_label="North branch",
            pickup_ready=True,
            state_token="care:11",
        ),
        i18n=i18n,
        locale="en",
    )
    shell = CareOrderCardAdapter.build(
        seed=seed,
        source=SourceRef(context=SourceContext.CARE_ORDER_LIST, source_ref="care.orders.row"),
        i18n=i18n,
        locale="en",
        mode=CardMode.LIST_ROW,
    )
    row = _CompactCareOrderRowCard(care_order_id=seed.care_order_id, shell=shell)
    block = row.object_block_lines(index=1)

    assert block[0] == "1. Order co-cc4f-2"
    assert "   - Night Gel x1" in block
    assert "   - North branch" in block
    assert "   - Ready for pickup" in block
    assert any("Pickup" in line for line in block)


def test_care_order_list_panel_text_is_object_rows_not_header_only() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    seed = CareOrderRuntimeViewBuilder().build_seed(
        snapshot=CareOrderRuntimeSnapshot(
            care_order_id="co-cc4f-3",
            status="confirmed",
            total_amount=19,
            currency_code="GEL",
            item_summary="Hydro Rinse x1",
            branch_label="Central branch",
            pickup_ready=False,
            state_token="care:12",
        ),
        i18n=i18n,
        locale="en",
    )
    shell = CareOrderCardAdapter.build(
        seed=seed,
        source=SourceRef(context=SourceContext.CARE_ORDER_LIST, source_ref="care.orders.row"),
        i18n=i18n,
        locale="en",
        mode=CardMode.LIST_ROW,
    )
    text = _compose_care_order_object_list_text(
        header_lines=["Care orders", "Page 1"],
        row_cards=[_CompactCareOrderRowCard(care_order_id=seed.care_order_id, shell=shell)],
    )

    assert "1. Order co-cc4f-3" in text
    assert "   - Hydro Rinse x1" in text
    assert "   - Central branch" in text


def test_reserve_again_localization_stays_object_action_oriented() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")

    assert "Reserve again" in i18n.t("patient.care.orders.repeat.action", "en")
    assert "Повторить резерв" in i18n.t("patient.care.orders.repeat.action", "ru")
    assert "/" not in i18n.t("patient.care.orders.repeat.action", "en")
    assert "Open new order" in i18n.t("patient.care.orders.repeat.open_new", "en")
    assert "Back to orders" in i18n.t("patient.care.orders.repeat.back_to_orders", "en")
    assert "Status: {status}" in i18n.t("patient.care.orders.repeat.result", "en")
    assert "Order {care_order_id}" in i18n.t("patient.care.orders.object.detail", "en")
