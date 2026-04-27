from __future__ import annotations

import asyncio

import test_patient_home_surface_pat_a1_2 as home
from types import SimpleNamespace


def _button_map(markup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _flatten_callbacks(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]


def _open_first_product_runtime_callback(router, user_id: int = 1001) -> str:
    enter = home._Callback(data="phome:care", user_id=user_id)
    asyncio.run(home._handler(router, "patient_home_care", kind="callback")(enter))
    _, categories_markup = home._latest_callback_panel(enter)
    category_open = next(
        button.callback_data
        for row in categories_markup.inline_keyboard
        for button in row
        if button.callback_data and button.callback_data.startswith("c2|")
    )
    category_cb = home._Callback(data=category_open, user_id=user_id)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(category_cb))
    _, products_markup = home._latest_callback_panel(category_cb)
    return next(
        button.callback_data
        for row in products_markup.inline_keyboard
        for button in row
        if button.callback_data and button.callback_data.startswith("c2|")
    )


def _mock_product_content(care_service) -> None:  # noqa: ANN001
    async def _resolve_content(**kwargs):  # noqa: ANN003
        return SimpleNamespace(
            title=None,
            short_label=None,
            description="Daily aftercare support.",
            usage_hint="Use twice a day.",
            media_refs=(),
        )

    care_service.resolve_product_content = _resolve_content  # type: ignore[method-assign]


def _maybe_expand_product_card(router, callback):  # noqa: ANN001
    _, markup = home._latest_callback_panel(callback)
    expand_cb = next(
        (
            button.callback_data
            for row in markup.inline_keyboard
            for button in row
            if button.callback_data
            and button.callback_data.startswith("c2|")
            and any(token in button.text.lower() for token in ("expand", "details", "детал"))
        ),
        None,
    )
    if not expand_cb:
        return callback
    expanded = home._Callback(data=expand_cb, user_id=callback.from_user.id)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(expanded))
    return expanded


def test_p0_06b1_product_card_readable_ru_and_en_without_raw_debug_fields() -> None:
    for locale, expected_labels in (
        ("en", ("🏷 SKU:", "📂 Category:", "💶 Price:", "📦 Availability:", "📍 Branch:")),
        ("ru", ("🏷 Артикул:", "📂 Категория:", "💶 Цена:", "📦 Наличие:", "📍 Филиал:")),
    ):
        router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale=locale)
        assert care_service is not None
        _mock_product_content(care_service)

        async def _products(**kwargs):  # noqa: ANN003
            return [care_service.products["prod_1"]]

        care_service.list_catalog_products_by_category = _products  # type: ignore[method-assign]
        open_product = _open_first_product_runtime_callback(router)
        callback = home._Callback(data=open_product, user_id=1001)
        asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(callback))
        callback = _maybe_expand_product_card(router, callback)

        text, markup = home._latest_callback_panel(callback)
        assert "🪥" in text and "AF-BRUSH" in text
        for label in expected_labels:
            assert label in text
        for forbidden in (
            "Actions:",
            "Канал:",
            "Channel:",
            "telegram",
            "care_product_id",
            "branch_id",
            "source_channel",
            "booking_mode",
            "c2|",
        ):
            assert forbidden not in text

        callbacks = _flatten_callbacks(markup)
        button_texts = {button.text for row in markup.inline_keyboard for button in row}
        assert sum(1 for value in callbacks if value.startswith("c2|")) >= 2
        assert any("back" in text.lower() or "назад" in text.lower() for text in button_texts)
        assert "phome:home" in callbacks


def test_p0_06b1_product_card_from_recommendation_keeps_reason_back_and_home() -> None:
    router, _, _, recommendation_service, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    assert care_service is not None
    _mock_product_content(care_service)
    recommendation_service.rows[1].rationale_text = "Use after ultrasonic cleaning"

    products = home._Callback(data="prec:products:rec_latest", user_id=1001)
    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(products))
    _, picker_markup = home._latest_callback_panel(products)
    open_product = next(
        button.callback_data
        for row in picker_markup.inline_keyboard
        for button in row
        if button.callback_data and button.callback_data.startswith("c2|")
    )

    open_cb = home._Callback(data=open_product, user_id=1001)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(open_cb))
    text, markup = home._latest_callback_panel(open_cb)
    assert "Why recommended:" in text
    assert "Use after ultrasonic cleaning" in text
    assert "Actions:" not in text and "telegram" not in text
    callbacks = _flatten_callbacks(markup)
    back_cb = next(
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data and button.callback_data.startswith("c2|") and ("back" in button.text.lower() or "назад" in button.text.lower())
    )
    assert "phome:home" in callbacks

    back = home._Callback(data=back_cb, user_id=1001)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(back))
    back_text, _ = home._latest_callback_panel(back)
    assert "Recommended care products" in back_text


def test_p0_06b1_runtime_reserve_unresolved_uses_inline_recovery_no_popup_only_path() -> None:
    class _UnresolvedRepo:
        async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str | None:
            return None

    router, _, _, _, care_service = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    assert care_service is not None
    _mock_product_content(care_service)

    async def _products(**kwargs):  # noqa: ANN003
        return [care_service.products["prod_1"]]

    care_service.list_catalog_products_by_category = _products  # type: ignore[method-assign]
    open_product = _open_first_product_runtime_callback(router)
    card_cb = home._Callback(data=open_product, user_id=1001)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(card_cb))
    card_cb = _maybe_expand_product_card(router, card_cb)
    _, card_markup = home._latest_callback_panel(card_cb)
    reserve_cb = next(
        button.callback_data
        for row in card_markup.inline_keyboard
        for button in row
        if button.callback_data and button.callback_data.startswith("c2|") and "reserve" in button.text.lower()
    )

    reserve = home._Callback(data=reserve_cb, user_id=1001)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(reserve))
    text, markup = home._latest_callback_panel(reserve)
    buttons = _button_map(markup)
    assert "Reservation unavailable" in text
    assert buttons == {
        "📅 My booking": "phome:my_booking",
        "🪥 Care catalog": "phome:care",
        "🏠 Main menu": "phome:home",
    }
    assert len(reserve.answer_payloads) <= 1


def test_p0_06b1_direct_care_reserve_unresolved_still_inline_recovery() -> None:
    class _UnresolvedRepo:
        async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str | None:
            return None

    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    callback = home._Callback(data="care:reserve:prod_1", user_id=1001)
    asyncio.run(home._handler(router, "care_reserve_pick", kind="callback")(callback))
    text, markup = home._latest_callback_panel(callback)
    assert "Reservation unavailable" in text
    assert _button_map(markup)["🏠 Main menu"] == "phome:home"


def test_p0_06b1_missing_or_inactive_product_panel_is_recoverable() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    _mock_product_content(care_service)
    care_service.products["prod_1"].status = "inactive"

    callback = home._Callback(data="care:product:prod_1", user_id=1001)
    asyncio.run(home._handler(router, "care_product_pick", kind="callback")(callback))
    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "Product unavailable" in text
    assert buttons == {"🪥 Open care catalog": "phome:care", "🏠 Main menu": "phome:home"}


def test_p0_06b1_recommendation_products_success_answers_once_and_renders_picker() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    _mock_product_content(care_service)

    callback = home._Callback(data="prec:products:rec_latest", user_id=1001)
    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(callback))

    text, _ = home._latest_callback_panel(callback)
    assert "Recommended care products" in text
    assert len(callback.answer_payloads) <= 1


def test_p0_06b1_branch_picker_has_back_and_home() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")

    callback = home._Callback(data="care:branch:prod_1", user_id=1001)
    asyncio.run(home._handler(router, "care_branch_pick", kind="callback")(callback))
    _, markup = home._latest_callback_panel(callback)
    callbacks = _flatten_callbacks(markup)
    assert any(value.startswith("c2|") for value in callbacks)
    assert "phome:home" in callbacks
