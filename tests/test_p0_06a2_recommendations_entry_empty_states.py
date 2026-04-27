from __future__ import annotations

import asyncio

import test_patient_home_surface_pat_a1_2 as home


def _button_map(markup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def test_p0_06a2_recommendation_module_unavailable_panel_and_no_double_answer() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=False, with_care=False, locale="en")
    callback = home._Callback(data="phome:recommendations", user_id=1001)

    asyncio.run(home._handler(router, "patient_home_recommendations", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "Recommendations unavailable" in text
    assert "This section is currently unavailable." not in text
    assert buttons == {
        "📅 My booking": "phome:my_booking",
        "🏠 Main menu": "phome:home",
    }
    assert len(callback.answer_payloads) <= 1


def test_p0_06a2_patient_resolution_failure_renders_inline_panel_no_popup_only() -> None:
    class _UnresolvedRepo:
        async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str | None:
            return None

    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=False,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    callback = home._Callback(data="phome:recommendations", user_id=1001)

    asyncio.run(home._handler(router, "patient_home_recommendations", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "could not safely resolve your patient profile" in text
    assert buttons == {
        "📅 My booking": "phome:my_booking",
        "🏠 Main menu": "phome:home",
    }
    assert home._latest_callback_panel(callback)[0] == text
    assert len(callback.answer_payloads) <= 1


def test_p0_06a2_empty_recommendations_list_panel_and_nav() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=False, locale="en")
    assert recommendation_service is not None
    recommendation_service.rows = []

    callback = home._Callback(data="phome:recommendations", user_id=1001)
    asyncio.run(home._handler(router, "patient_home_recommendations", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "No recommendations yet" in text
    assert "after your visit" in text
    assert buttons == {
        "📅 My booking": "phome:my_booking",
        "🏠 Main menu": "phome:home",
    }


def test_p0_06a2_recommendation_detail_has_back_home_and_no_double_answer() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    seed_message = home._Message(text="/recommendations", user_id=1001)
    asyncio.run(home._handler(router, "recommendations_list")(seed_message))

    callback = home._Callback(data="prec:open:rec_latest", user_id=1001, message_id=501)
    asyncio.run(home._handler(router, "recommendation_open_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "Type:" in text and "Status:" in text
    assert buttons["⬅️ Back to recommendations"] == "phome:recommendations"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert len(callback.answer_payloads) <= 1
