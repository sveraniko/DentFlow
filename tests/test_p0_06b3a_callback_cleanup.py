from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import test_patient_home_surface_pat_a1_2 as home


def _button_map(markup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _make_order(care_service, *, order_id: str, status: str, branch_id: str = "branch_1", patient_id: str = "pat_1") -> None:
    now = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
    care_service.orders[order_id] = SimpleNamespace(
        care_order_id=order_id,
        clinic_id="clinic_main",
        patient_id=patient_id,
        status=status,
        total_amount=25,
        currency_code="GEL",
        pickup_branch_id=branch_id,
        updated_at=now,
    )
    care_service.order_items[order_id] = [SimpleNamespace(care_product_id="prod_1", quantity=1)]


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


def _find_button_callback(markup, *, contains_any: tuple[str, ...]) -> str:
    for row in markup.inline_keyboard:
        for button in row:
            if (
                button.callback_data
                and button.callback_data.startswith("c2|")
                and any(token in button.text.lower() for token in contains_any)
            ):
                return button.callback_data
    raise AssertionError(f"button not found for tokens={contains_any}")


def _track_callback_answers(callback: home._Callback) -> list[tuple[str, bool]]:
    captured: list[tuple[str, bool]] = []
    original_answer = callback.answer

    async def _tracked_answer(text: str = "", show_alert: bool = False, reply_markup=None):  # noqa: ANN001
        captured.append((text, show_alert))
        return await original_answer(text=text, show_alert=show_alert, reply_markup=reply_markup)

    callback.answer = _tracked_answer  # type: ignore[method-assign]
    return captured


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


def _mock_product_content_with_media(care_service) -> None:  # noqa: ANN001
    async def _resolve_content(**kwargs):  # noqa: ANN003
        return SimpleNamespace(
            title=None,
            short_label=None,
            description="Daily aftercare support.",
            usage_hint="Use twice a day.",
            media_refs=("photo:test-cover",),
        )

    care_service.resolve_product_content = _resolve_content  # type: ignore[method-assign]


def _mock_single_category_product(care_service) -> None:  # noqa: ANN001
    async def _products(**kwargs):  # noqa: ANN003
        _ = kwargs
        return [care_service.products["prod_1"]]

    care_service.list_catalog_products_by_category = _products  # type: ignore[method-assign]


def test_p0_06b3a_care_orders_callback_answers_once() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    _make_order(care_service, order_id="co_live_123456", status="confirmed")
    callback = home._Callback(data="care:orders", user_id=1001)

    asyncio.run(home._handler(router, "care_orders_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "My reserves / orders" in text
    assert buttons["🏠 Main menu"] == "phome:home"
    assert len(callback.answer_payloads) <= 1


def test_p0_06b3a_care_order_open_callback_answers_once() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    _make_order(care_service, order_id="coabcdef123456", status="confirmed")
    callback = home._Callback(data="careo:open:coabcdef123456", user_id=1001)

    asyncio.run(home._handler(router, "care_order_open_callback", kind="callback")(callback))

    text, _ = home._latest_callback_panel(callback)
    assert "📦 Care reserve / order" in text
    assert "Actions:" not in text and "care_order_id" not in text
    assert len(callback.answer_payloads) <= 1


def test_p0_06b3a_recommendation_products_unresolved_is_inline_panel() -> None:
    class _UnresolvedRepo:
        async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str | None:
            _ = clinic_id, telegram_user_id
            return None

    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    callback = home._Callback(data="prec:products:rec_latest", user_id=1001)
    alerts = _track_callback_answers(callback)

    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "could not safely resolve your patient profile" in text.lower()
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert not any(show_alert for _, show_alert in alerts)
    assert len(callback.answer_payloads) <= 1


def test_p0_06b3a_runtime_media_missing_uses_inline_product_recovery() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    _mock_product_content_with_media(care_service)
    _mock_single_category_product(care_service)

    open_product = _open_first_product_runtime_callback(router)
    open_cb = home._Callback(data=open_product, user_id=1001)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(open_cb))
    open_cb = _maybe_expand_product_card(router, open_cb)
    _, product_markup = home._latest_callback_panel(open_cb)
    media_cb_data = _find_button_callback(product_markup, contains_any=("cover", "gallery", "media", "photo"))

    care_service.products.pop("prod_1", None)
    media_cb = home._Callback(data=media_cb_data, user_id=1001)
    alerts = _track_callback_answers(media_cb)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(media_cb))

    text, markup = home._latest_callback_panel(media_cb)
    buttons = _button_map(markup)
    assert "Product unavailable" in text
    assert buttons["🪥 Open care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert not any(show_alert for _, show_alert in alerts)
    assert len(media_cb.answer_payloads) <= 1


def test_p0_06b3a_runtime_reserve_missing_uses_inline_product_recovery() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    _mock_product_content_with_media(care_service)
    _mock_single_category_product(care_service)

    open_product = _open_first_product_runtime_callback(router)
    open_cb = home._Callback(data=open_product, user_id=1001)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(open_cb))
    open_cb = _maybe_expand_product_card(router, open_cb)
    _, product_markup = home._latest_callback_panel(open_cb)
    reserve_cb_data = _find_button_callback(product_markup, contains_any=("reserve", "pickup", "заброн"))

    care_service.products["prod_1"].status = "inactive"
    reserve_cb = home._Callback(data=reserve_cb_data, user_id=1001)
    alerts = _track_callback_answers(reserve_cb)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(reserve_cb))

    text, markup = home._latest_callback_panel(reserve_cb)
    buttons = _button_map(markup)
    assert "Product unavailable" in text
    assert buttons["🪥 Open care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert not any(show_alert for _, show_alert in alerts)
    assert len(reserve_cb.answer_payloads) <= 1
