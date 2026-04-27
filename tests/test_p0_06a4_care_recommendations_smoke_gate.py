from __future__ import annotations

import asyncio
import re

import test_patient_home_surface_pat_a1_2 as home


_RUNTIME_CALLBACK_PREFIX = re.compile(r"^c\d+\|")


def _button_map(markup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _collect_callback_data(markup) -> set[str]:
    return {button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _assert_allowed_callback_prefixes(callbacks: set[str]) -> None:
    allowed_prefixes = (
        "phome:home",
        "phome:my_booking",
        "phome:care",
        "phome:recommendations",
        "care:",
        "careo:",
        "prec:",
        "rec:",
    )
    for value in sorted(callbacks):
        if _RUNTIME_CALLBACK_PREFIX.match(value):
            continue
        assert value.startswith(allowed_prefixes), f"unexpected callback namespace: {value}"


def test_p0_06a4_consolidated_smoke_gate_and_callback_namespace() -> None:
    collected_callbacks: set[str] = set()

    # 1) Care entry: module unavailable panel.
    router, _, _, _, _ = home._build_router(with_recommendations=False, with_care=False, locale="en")
    care_unavailable = home._Callback(data="phome:care", user_id=1001)
    asyncio.run(home._handler(router, "patient_home_care", kind="callback")(care_unavailable))
    text, markup = home._latest_callback_panel(care_unavailable)
    buttons = _button_map(markup)
    collected_callbacks |= _collect_callback_data(markup)
    assert "Care & hygiene is unavailable" in text
    assert buttons == {"📅 My booking": "phome:my_booking", "🏠 Main menu": "phome:home"}
    assert len(care_unavailable.answer_payloads) <= 1

    # 1) Care entry: catalog empty panel.
    router, _, _, _, care_service = home._build_router(with_recommendations=False, with_care=True, locale="en")
    assert care_service is not None

    async def _empty_categories(**kwargs):  # noqa: ANN003
        return []

    care_service.list_catalog_categories = _empty_categories  # type: ignore[method-assign]
    care_empty_catalog = home._Callback(data="phome:care", user_id=1001)
    asyncio.run(home._handler(router, "patient_home_care", kind="callback")(care_empty_catalog))
    text, markup = home._latest_callback_panel(care_empty_catalog)
    buttons = _button_map(markup)
    collected_callbacks |= _collect_callback_data(markup)
    assert "Care catalog is empty for now" in text
    assert buttons == {"📅 My booking": "phome:my_booking", "🏠 Main menu": "phome:home"}
    assert len(care_empty_catalog.answer_payloads) <= 1

    # 1) Care entry: category empty panel + Home recovery.
    router, _, _, _, _ = home._build_router(with_recommendations=False, with_care=True, locale="en")
    enter_care = home._Callback(data="phome:care", user_id=1001)
    asyncio.run(home._handler(router, "patient_home_care", kind="callback")(enter_care))
    _, categories_markup = home._latest_callback_panel(enter_care)
    collected_callbacks |= _collect_callback_data(categories_markup)
    category_open = next(
        button.callback_data
        for row in categories_markup.inline_keyboard
        for button in row
        if button.callback_data and button.callback_data.startswith("c2|")
    )
    category_empty = home._Callback(data=category_open, user_id=1001)
    asyncio.run(home._handler(router, "runtime_card_callback", kind="callback")(category_empty))
    text, markup = home._latest_callback_panel(category_empty)
    buttons = _button_map(markup)
    collected_callbacks |= _collect_callback_data(markup)
    assert "There are no products in this category yet" in text
    assert buttons["🏠 Main menu"] == "phome:home"
    assert buttons["⬅️ Back to categories"].startswith("c2|")
    assert len(category_empty.answer_payloads) <= 1

    class _UnresolvedRepo:
        async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str | None:
            return None

    # 2) Care failure recovery: orders unresolved.
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    care_orders_unresolved = home._Callback(data="care:orders", user_id=1001)
    asyncio.run(home._handler(router, "care_orders_callback", kind="callback")(care_orders_unresolved))
    text, markup = home._latest_callback_panel(care_orders_unresolved)
    buttons = _button_map(markup)
    collected_callbacks |= _collect_callback_data(markup)
    assert "could not safely resolve your patient profile" in text.lower()
    assert buttons == {"📅 My booking": "phome:my_booking", "🏠 Main menu": "phome:home"}
    assert len(care_orders_unresolved.answer_payloads) <= 1

    # 2) Care failure recovery: reserve unresolved.
    care_reserve_unresolved = home._Callback(data="care:reserve:prod_1", user_id=1001)
    asyncio.run(home._handler(router, "care_reserve_pick", kind="callback")(care_reserve_unresolved))
    text, markup = home._latest_callback_panel(care_reserve_unresolved)
    buttons = _button_map(markup)
    collected_callbacks |= _collect_callback_data(markup)
    assert "Reservation unavailable" in text
    assert buttons == {
        "📅 My booking": "phome:my_booking",
        "🪥 Care catalog": "phome:care",
        "🏠 Main menu": "phome:home",
    }
    assert len(care_reserve_unresolved.answer_payloads) <= 1

    # 3) Recommendations entry: module unavailable.
    router, _, _, _, _ = home._build_router(with_recommendations=False, with_care=False, locale="en")
    recommendations_unavailable = home._Callback(data="phome:recommendations", user_id=1001)
    asyncio.run(home._handler(router, "patient_home_recommendations", kind="callback")(recommendations_unavailable))
    text, markup = home._latest_callback_panel(recommendations_unavailable)
    buttons = _button_map(markup)
    collected_callbacks |= _collect_callback_data(markup)
    assert "Recommendations unavailable" in text
    assert buttons == {"📅 My booking": "phome:my_booking", "🏠 Main menu": "phome:home"}
    assert len(recommendations_unavailable.answer_payloads) <= 1

    # 3) Recommendations entry: unresolved patient inline recovery.
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    recommendations_unresolved = home._Callback(data="phome:recommendations", user_id=1001)
    asyncio.run(home._handler(router, "patient_home_recommendations", kind="callback")(recommendations_unresolved))
    text, markup = home._latest_callback_panel(recommendations_unresolved)
    buttons = _button_map(markup)
    collected_callbacks |= _collect_callback_data(markup)
    assert "could not safely resolve your patient profile" in text
    assert buttons == {"📅 My booking": "phome:my_booking", "🏠 Main menu": "phome:home"}
    assert len(recommendations_unresolved.answer_payloads) <= 1

    # 3) Recommendations entry: empty state readable panel.
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=False, locale="en")
    assert recommendation_service is not None
    recommendation_service.rows = []
    recommendations_empty = home._Callback(data="phome:recommendations", user_id=1001)
    asyncio.run(home._handler(router, "patient_home_recommendations", kind="callback")(recommendations_empty))
    text, markup = home._latest_callback_panel(recommendations_empty)
    buttons = _button_map(markup)
    collected_callbacks |= _collect_callback_data(markup)
    assert "No recommendations yet" in text
    assert buttons == {"📅 My booking": "phome:my_booking", "🏠 Main menu": "phome:home"}
    assert len(recommendations_empty.answer_payloads) <= 1

    # 3) Recommendation detail: Back/Home.
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    seed_message = home._Message(text="/recommendations", user_id=1001)
    asyncio.run(home._handler(router, "recommendations_list")(seed_message))
    detail_open = home._Callback(data="prec:open:rec_latest", user_id=1001, message_id=501)
    asyncio.run(home._handler(router, "recommendation_open_callback", kind="callback")(detail_open))
    text, markup = home._latest_callback_panel(detail_open)
    buttons = _button_map(markup)
    collected_callbacks |= _collect_callback_data(markup)
    assert "Type:" in text and "Status:" in text
    assert buttons["⬅️ Back to recommendations"] == "phome:recommendations"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert len(detail_open.answer_payloads) <= 1

    # 4) Recommendation products failure recovery: manual target invalid.
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None

    async def _manual_invalid(**kwargs):  # noqa: ANN003
        return type("Resolution", (), {"status": "manual_target_invalid", "products": []})()

    care_service.resolve_recommendation_target_result = _manual_invalid  # type: ignore[method-assign]
    products_manual_invalid = home._Callback(data="prec:products:rec_latest", user_id=1001)
    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(products_manual_invalid))
    text, markup = home._latest_callback_panel(products_manual_invalid)
    buttons = _button_map(markup)
    collected_callbacks |= _collect_callback_data(markup)
    assert "Recommended product unavailable" in text
    assert buttons == {
        "⬅️ Back to recommendation": "prec:open:rec_latest",
        "🪥 Open care catalog": "phome:care",
        "🏠 Main menu": "phome:home",
    }
    assert len(products_manual_invalid.answer_payloads) <= 1

    # 4) Recommendation products failure recovery: resolved empty.
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    care_service.resolution_by_recommendation_id["rec_latest"] = []
    products_empty = home._Callback(data="prec:products:rec_latest", user_id=1001)
    asyncio.run(home._handler(router, "recommendation_products_callback", kind="callback")(products_empty))
    text, markup = home._latest_callback_panel(products_empty)
    buttons = _button_map(markup)
    collected_callbacks |= _collect_callback_data(markup)
    assert "No products are linked to this recommendation yet" in text
    assert buttons == {
        "⬅️ Back to recommendation": "prec:open:rec_latest",
        "🪥 Open care catalog": "phome:care",
        "🏠 Main menu": "phome:home",
    }
    assert len(products_empty.answer_payloads) <= 1

    _assert_allowed_callback_prefixes(collected_callbacks)
