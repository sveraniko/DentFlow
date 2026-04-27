from __future__ import annotations

import asyncio

import test_patient_home_surface_pat_a1_2 as home


def _button_map(markup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def test_p0_06a1_care_module_unavailable_panel_and_no_double_answer() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=False, with_care=False, locale="en")
    callback = home._Callback(data="phome:care", user_id=1001)

    asyncio.run(home._handler(router, "patient_home_care", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "Care & hygiene is unavailable" in text
    assert "This section is currently unavailable." not in text
    assert buttons == {
        "📅 My booking": "phome:my_booking",
        "🏠 Main menu": "phome:home",
    }
    assert len(callback.answer_payloads) <= 1


def test_p0_06a1_care_catalog_empty_panel_and_nav() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=False, with_care=True, locale="en")
    assert care_service is not None

    async def _empty_categories(**kwargs):  # noqa: ANN003
        return []

    care_service.list_catalog_categories = _empty_categories  # type: ignore[method-assign]
    callback = home._Callback(data="phome:care", user_id=1001)

    asyncio.run(home._handler(router, "patient_home_care", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "Care catalog is empty for now" in text
    assert buttons == {
        "📅 My booking": "phome:my_booking",
        "🏠 Main menu": "phome:home",
    }
    assert len(buttons) == 2
    assert len(callback.answer_payloads) <= 1


def test_p0_06a1_care_category_empty_panel_and_no_double_answer() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=False, with_care=True, locale="en")
    enter_callback = home._Callback(data="phome:care", user_id=1001)

    asyncio.run(home._handler(router, "patient_home_care", kind="callback")(enter_callback))

    _, categories_markup = home._latest_callback_panel(enter_callback)
    category_open = next(
        button.callback_data
        for row in categories_markup.inline_keyboard
        for button in row
        if button.callback_data and button.callback_data.startswith("c2|")
    )

    category_callback = home._Callback(data=category_open, user_id=1001)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(category_callback))

    text, markup = home._latest_callback_panel(category_callback)
    buttons = _button_map(markup)
    assert "There are no products in this category yet" in text
    assert "⬅️ Back to categories" in buttons
    assert buttons["🏠 Main menu"] == "phome:home"
    assert buttons["⬅️ Back to categories"].startswith("c2|")
    assert len(category_callback.answer_payloads) <= 1
