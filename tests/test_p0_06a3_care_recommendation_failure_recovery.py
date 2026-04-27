from __future__ import annotations

import asyncio

import test_patient_home_surface_pat_a1_2 as home


def _button_map(markup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def test_p0_06a3_care_orders_unresolved_renders_inline_recovery_panel() -> None:
    class _UnresolvedRepo:
        async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str | None:
            return None

    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    callback = home._Callback(data="care:orders", user_id=1001)

    asyncio.run(home._handler(router, "care_orders_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "My reserves" in text
    assert "could not safely resolve your patient profile" in text.lower()
    assert buttons == {
        "📅 My booking": "phome:my_booking",
        "🏠 Main menu": "phome:home",
    }
    assert len(callback.answer_payloads) <= 1


def test_p0_06a3_care_reserve_unresolved_renders_inline_recovery_panel() -> None:
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
    buttons = _button_map(markup)
    assert "Reservation unavailable" in text
    assert "Open your booking first" in text
    assert buttons == {
        "📅 My booking": "phome:my_booking",
        "🪥 Care catalog": "phome:care",
        "🏠 Main menu": "phome:home",
    }
    assert len(callback.answer_payloads) <= 1


def test_p0_06a3_recommendation_products_manual_invalid_renders_recovery_panel() -> None:
    router, _, _, recommendation_service, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    assert care_service is not None

    async def _manual_invalid(**kwargs):  # noqa: ANN003
        return type("Resolution", (), {"status": "manual_target_invalid", "products": []})()

    care_service.resolve_recommendation_target_result = _manual_invalid  # type: ignore[method-assign]
    callback = home._Callback(data="prec:products:rec_latest", user_id=1001)

    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "Recommended product unavailable" in text
    assert "no longer linked to the catalog" in text
    assert buttons == {
        "⬅️ Back to recommendation": "prec:open:rec_latest",
        "🪥 Open care catalog": "phome:care",
        "🏠 Main menu": "phome:home",
    }
    assert len(callback.answer_payloads) <= 1


def test_p0_06a3_recommendation_products_empty_renders_recovery_panel() -> None:
    router, _, _, recommendation_service, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    assert care_service is not None
    care_service.resolution_by_recommendation_id["rec_latest"] = []

    callback = home._Callback(data="prec:products:rec_latest", user_id=1001)

    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(callback))

    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "No products are linked to this recommendation yet" in text
    assert "recommendation exists" in text
    assert buttons == {
        "⬅️ Back to recommendation": "prec:open:rec_latest",
        "🪥 Open care catalog": "phome:care",
        "🏠 Main menu": "phome:home",
    }
    assert len(callback.answer_payloads) <= 1
