from __future__ import annotations

import asyncio
import re
from pathlib import Path

import test_p0_06b1_care_product_readable_card as b1
import test_p0_06b2_care_order_readable_surfaces as b2
import test_p0_06b3a_callback_cleanup as b3a
import test_p0_06b3b2_care_command_fallbacks as b3b2
import test_patient_home_surface_pat_a1_2 as home


_RUNTIME_CALLBACK_PREFIX = re.compile(r"^c\d+\|")


def _button_map(markup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _collect_callback_data(markup) -> set[str]:
    return {button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _assert_no_popup_only_or_double_answer(callback: home._Callback) -> None:
    assert len(callback.answer_payloads) <= 1


def _assert_allowed_callback_prefixes(callbacks: set[str]) -> None:
    allowed_prefixes = (
        "phome:home",
        "phome:care",
        "phome:my_booking",
        "phome:recommendations",
        "care:",
        "careo:",
        "prec:",
        "rec:",
        "book:",
        "rsch:",
    )
    for value in sorted(callbacks):
        if _RUNTIME_CALLBACK_PREFIX.match(value):
            continue
        assert value.startswith(allowed_prefixes), f"unexpected callback namespace: {value}"


def test_p0_06b4_consolidated_care_catalog_product_order_smoke() -> None:
    callbacks: set[str] = set()

    # care entry / recovery baseline (A4)
    router, _, _, _, _ = home._build_router(with_recommendations=False, with_care=False, locale="en")
    care_unavailable = home._Callback(data="phome:care", user_id=1001)
    asyncio.run(home._handler(router, "patient_home_care", kind="callback")(care_unavailable))
    text, markup = home._latest_callback_panel(care_unavailable)
    callbacks |= _collect_callback_data(markup)
    assert "Care & hygiene is unavailable" in text
    assert "patient.home.action.unavailable" not in text
    _assert_no_popup_only_or_double_answer(care_unavailable)

    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    b1._mock_product_content(care_service)
    b3a._mock_single_category_product(care_service)

    # product card readable contract + callbacks
    open_product = b1._open_first_product_runtime_callback(router)
    product_cb = home._Callback(data=open_product, user_id=1001)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(product_cb))
    product_cb = b1._maybe_expand_product_card(router, product_cb)
    text, markup = home._latest_callback_panel(product_cb)
    callbacks |= _collect_callback_data(markup)
    assert "🏷 SKU:" in text and "📂 Category:" in text and "📦 Availability:" in text
    assert "📍 Branch:" in text and "💶 Price:" in text
    for forbidden in ("Actions:", "source_channel", "booking_mode", "Channel:", "Канал:"):
        assert forbidden not in text
    _assert_no_popup_only_or_double_answer(product_cb)

    # runtime reserve unresolved must be inline recoverable
    unresolved_router, _, _, _, unresolved_care_service = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=b3b2._UnresolvedRepo(),
    )
    assert unresolved_care_service is not None
    b1._mock_product_content(unresolved_care_service)
    b3a._mock_single_category_product(unresolved_care_service)
    open_product = b1._open_first_product_runtime_callback(unresolved_router)
    unresolved_card_cb = home._Callback(data=open_product, user_id=1001)
    asyncio.run(home._handler(unresolved_router, "runtime_card_callback", kind="callback")(unresolved_card_cb))
    unresolved_card_cb = b1._maybe_expand_product_card(unresolved_router, unresolved_card_cb)
    _, unresolved_markup = home._latest_callback_panel(unresolved_card_cb)
    reserve_cb = next(
        button.callback_data
        for row in unresolved_markup.inline_keyboard
        for button in row
        if button.callback_data and button.callback_data.startswith("c2|") and "reserve" in button.text.lower()
    )
    reserve = home._Callback(data=reserve_cb, user_id=1001)
    asyncio.run(home._handler(unresolved_router, "runtime_card_callback", kind="callback")(reserve))
    text, markup = home._latest_callback_panel(reserve)
    callbacks |= _collect_callback_data(markup)
    buttons = _button_map(markup)
    assert "Reservation unavailable" in text
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🪥 Care catalog"] == "phome:care"
    _assert_no_popup_only_or_double_answer(reserve)

    # order creation -> list -> detail -> repeat
    b2._make_order(care_service, order_id="co_list_123456", status="confirmed")
    order_create = home._Callback(data="care:reserve:prod_1", user_id=1001)
    asyncio.run(home._handler(router, "care_reserve_pick", kind="callback")(order_create))
    text, markup = home._latest_callback_panel(order_create)
    callbacks |= _collect_callback_data(markup)
    buttons = _button_map(markup)
    assert "✅ Product reserved" in text and "Main Branch" in text
    assert "confirmed" not in text.lower()
    assert buttons["📦 My reserves / orders"] == "care:orders"
    _assert_no_popup_only_or_double_answer(order_create)

    orders = home._Callback(data="care:orders", user_id=1001)
    asyncio.run(home._handler(router, "care_orders_callback", kind="callback")(orders))
    text, markup = home._latest_callback_panel(orders)
    callbacks |= _collect_callback_data(markup)
    assert "📦 My reserves / orders" in text
    assert "Current order" in text or "You have no reserves yet" in text
    _assert_no_popup_only_or_double_answer(orders)

    order_callbacks = _collect_callback_data(markup)
    open_order_cb = next((value for value in order_callbacks if value.startswith("careo:open:")), "careo:open:co_list_123456")
    order_open = home._Callback(data=open_order_cb, user_id=1001)
    asyncio.run(home._handler(router, "care_order_open_callback", kind="callback")(order_open))
    text, markup = home._latest_callback_panel(order_open)
    callbacks |= _collect_callback_data(markup)
    assert "📦 Care reserve / order" in text and "🧾 Ref:" in text and "📍 Branch:" in text
    for forbidden in ("Actions:", "Channel:", "Канал:", "source_channel", "booking_mode"):
        assert forbidden not in text
    _assert_no_popup_only_or_double_answer(order_open)


    repeat_outcome = type("Outcome", (), {
        "ok": True,
        "reason": None,
        "source_order": care_service.orders["co_list_123456"],
        "source_item": type("Item", (), {"quantity": 1})(),
        "product": care_service.products["prod_1"],
        "selected_branch_id": "branch_1",
        "available_branch_ids": (),
        "created_order": type("Created", (), {"care_order_id": "co_repeat_123456", "status": "confirmed"})(),
        "created_reservation": type("Res", (), {"status": "created"})(),
    })()
    b2._mock_repeat(care_service, outcome=repeat_outcome)
    repeat_source = next(value.split(":")[-1] for value in callbacks if value.startswith("careo:open:"))
    repeat = home._Callback(data=f"care:repeat:{repeat_source}", user_id=1001)
    asyncio.run(home._handler(router, "care_repeat_from_order_surface", kind="callback")(repeat))
    text, markup = home._latest_callback_panel(repeat)
    callbacks |= _collect_callback_data(markup)
    buttons = _button_map(markup)
    assert "Reserve repeated" in text or "Choose a branch" in text
    assert "🏠 Main menu" in buttons
    _assert_no_popup_only_or_double_answer(repeat)

    # recommendation -> product handoff
    rec_products = home._Callback(data="prec:products:rec_latest", user_id=1001)
    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(rec_products))
    text, markup = home._latest_callback_panel(rec_products)
    callbacks |= _collect_callback_data(markup)
    assert "Recommended care products" in text
    open_product_from_rec = next(
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
        and button.callback_data.startswith("c2|")
        and any(token in button.text.lower() for token in ("toothbrush", "post-cleaning", "open", "product", "товар"))
    )
    rec_open = home._Callback(data=open_product_from_rec, user_id=1001)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(rec_open))
    text, markup = home._latest_callback_panel(rec_open)
    callbacks |= _collect_callback_data(markup)
    assert "Post-cleaning soft toothbrush" in text
    _assert_no_popup_only_or_double_answer(rec_open)

    # manual-invalid and empty recommendation products recovery
    router_invalid, _, _, _, care_service_invalid = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service_invalid is not None

    async def _manual_invalid(**kwargs):  # noqa: ANN003
        _ = kwargs
        return type("Resolution", (), {"status": "manual_target_invalid", "products": []})()

    care_service_invalid.resolve_recommendation_target_result = _manual_invalid  # type: ignore[method-assign]
    manual_invalid = home._Callback(data="prec:products:rec_latest", user_id=1001)
    asyncio.run(home._handler(router_invalid, "recommendation_products_callback", kind="callback")(manual_invalid))
    text, _ = home._latest_callback_panel(manual_invalid)
    assert "Recommended product unavailable" in text

    router_empty, _, _, _, care_service_empty = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service_empty is not None
    care_service_empty.resolution_by_recommendation_id["rec_latest"] = []
    products_empty = home._Callback(data="prec:products:rec_latest", user_id=1001)
    asyncio.run(home._handler(router_empty, "recommendation_products_callback", kind="callback")(products_empty))
    text, _ = home._latest_callback_panel(products_empty)
    assert "No products are linked to this recommendation yet" in text

    _assert_allowed_callback_prefixes(callbacks)



def test_p0_07d_ru_care_labels_and_price_formatting_smoke() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="ru")
    assert care_service is not None
    b1._mock_product_content(care_service)
    b3a._mock_single_category_product(care_service)
    care_service.products["prod_1"].price_amount = 420
    care_service.products["prod_1"].currency_code = "EUR"
    care_service.products["prod_1"].category = "irrigator"

    open_product = b1._open_first_product_runtime_callback(router)
    product_cb = home._Callback(data=open_product, user_id=1001)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(product_cb))
    text, _ = home._latest_callback_panel(product_cb)
    assert "4.20 EUR" in text
    assert "420 EUR" not in text
    assert "Ирригаторы" in text


def test_p0_06b4_command_fallback_and_router_grep_guards() -> None:
    router_text = Path("app/interfaces/bots/patient/router.py").read_text(encoding="utf-8")

    assert "CardShellRenderer.to_panel(shell).text" not in router_text
    assert "await message.answer(view.text)" not in router_text
    assert 'await message.answer(i18n.t("patient.care.product.open.usage' not in router_text
    assert 'await message.answer(i18n.t("patient.care.order.create.usage' not in router_text
    assert 'await message.answer(i18n.t("patient.care.orders.repeat.usage' not in router_text

    message = home._Message(text="/care_order_create rec_latest prod_1 branch_1", user_id=1001)
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    b1._mock_product_content(care_service)
    asyncio.run(home._handler(router, "care_order_create")(message))
    text, _ = message.answers[-1]
    assert "✅ Product reserved" in text
    assert "confirmed" not in text.lower()

    orders_router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    orders_message = home._Message(text="/care_orders", user_id=1001)
    asyncio.run(home._handler(orders_router, "care_orders")(orders_message))
    orders_text, _ = orders_message.answers[-1]
    assert "reserves" in orders_text.lower()


def test_p0_06b4_show_alert_carry_forward_classification_snapshot() -> None:
    router_text = Path("app/interfaces/bots/patient/router.py").read_text(encoding="utf-8")
    matches = re.findall(r"show_alert=True", router_text)
    assert len(matches) >= 1

    # Ensure key valid care/recommendation paths are inline-panel based and not popup-only.
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    b1._mock_product_content(care_service)
    care_orders = home._Callback(data="care:orders", user_id=1001)
    asyncio.run(home._handler(router, "care_orders_callback", kind="callback")(care_orders))
    text, _ = home._latest_callback_panel(care_orders)
    assert "My reserves / orders" in text or "You have no reserves yet" in text
    assert len(care_orders.answer_payloads) <= 1

    rec_products = home._Callback(data="prec:products:rec_latest", user_id=1001)
    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(rec_products))
    text, _ = home._latest_callback_panel(rec_products)
    assert "Recommended care products" in text
    assert len(rec_products.answer_payloads) <= 1
