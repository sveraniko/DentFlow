from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import test_patient_home_surface_pat_a1_2 as home


def _button_map(markup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


def _flatten(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]


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


def _mock_repeat(care_service, *, outcome):
    async def _repeat_order_as_new(**kwargs):  # noqa: ANN003
        _ = kwargs
        return outcome

    care_service.repeat_order_as_new = _repeat_order_as_new  # type: ignore[attr-defined]


def test_p0_06b2_order_creation_result_after_reserve_readable_and_navigable() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    callback = home._Callback(data="care:reserve:prod_1", user_id=1001)
    asyncio.run(home._handler(router, "care_reserve_pick", kind="callback")(callback))
    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "✅ Product reserved" in text and "Main Branch" in text and "Status:" in text
    assert "Product:" in text and "Next" not in text
    assert buttons["📦 Open reserve"].startswith("careo:open:")
    assert buttons["📦 My reserves / orders"] == "care:orders"
    assert buttons["🪥 Care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"
    for forbidden in ("care_order_id", "care_product_id", "patient_id", "source_channel", "booking_mode", "Actions:", "Channel:", "telegram"):
        assert forbidden not in text


def test_p0_06b2_product_reserve_out_of_stock_panel_has_recovery() -> None:
    router, runtime, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {"selected_branch_by_product": {"prod_1": "branch_1"}}},
        )
    )
    care_service.availability[("branch_1", "prod_1")].free_qty = 0
    callback = home._Callback(data="care:reserve:prod_1", user_id=1001)
    asyncio.run(home._handler(router, "care_reserve_pick", kind="callback")(callback))
    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "❌ Not available right now" in text and "Main Branch" in text
    assert any("change" in key.lower() for key in buttons)
    assert "phome:care" in buttons.values()
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b2_care_orders_empty_state_has_catalog_and_home() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    callback = home._Callback(data="care:orders", user_id=1001)
    asyncio.run(home._handler(router, "care_orders_callback", kind="callback")(callback))
    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "You have no reserves yet" in text
    assert "phome:care" in buttons.values()
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b2_care_orders_list_sections_readable_and_navigable() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    _make_order(care_service, order_id="co_live_123456", status="confirmed")
    _make_order(care_service, order_id="co_hist_654321", status="fulfilled")
    callback = home._Callback(data="care:orders", user_id=1001)
    asyncio.run(home._handler(router, "care_orders_callback", kind="callback")(callback))
    text, markup = home._latest_callback_panel(callback)
    callbacks = _flatten(markup)
    assert "📦 My reserves / orders" in text
    assert "Current order" in text and "History" in text
    assert "Main Branch" in text and "Post-cleaning soft toothbrush" in text
    assert "care_order_id" not in text and "branch: -" not in text
    assert any(item == "phome:care" for item in callbacks)
    assert any(item == "phome:home" for item in callbacks)


def test_p0_06b2_care_order_detail_card_readable_and_safe_ref() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    _make_order(care_service, order_id="coabcdef123456", status="confirmed")
    callback = home._Callback(data="careo:open:coabcdef123456", user_id=1001)
    asyncio.run(home._handler(router, "care_order_open_callback", kind="callback")(callback))
    text, markup = home._latest_callback_panel(callback)
    callbacks = _flatten(markup)
    assert "📦 Care reserve / order" in text and "🧾 Ref:" in text and "…123456" in text
    assert "🪥 Items:" in text and "📍 Branch:" in text and "💶 Total:" in text and "📦 Status:" in text
    for forbidden in ("Actions:", "Канал:", "Channel:", "telegram", "coabcdef123456", "care_order_id"):
        assert forbidden not in text
    assert any(value.startswith("c2|") for value in callbacks)
    assert "phome:home" in callbacks


def test_p0_06b2_order_not_found_panel_has_orders_and_home() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    callback = home._Callback(data="careo:open:missing_order", user_id=1001)
    asyncio.run(home._handler(router, "care_order_open_callback", kind="callback")(callback))
    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "📦 Order not found" in text
    assert buttons["📦 My reserves / orders"] == "care:orders"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b2_runtime_care_order_unresolved_patient_uses_inline_recovery() -> None:
    class _UnresolvedRepo:
        async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str | None:
            _ = clinic_id, telegram_user_id
            return None

    router, _, _, _, care_service = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    assert care_service is not None
    _make_order(care_service, order_id="co_unresolved_1", status="confirmed")
    care_orders = home._Callback(data="care:orders", user_id=1001)
    asyncio.run(home._handler(router, "care_orders_callback", kind="callback")(care_orders))
    text, markup = home._latest_callback_panel(care_orders)
    buttons = _button_map(markup)
    assert "Could not safely resolve your patient profile" in text
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert len(care_orders.answer_payloads) <= 1


def test_p0_06b2_repeat_success_panel_readable_and_no_double_answer() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    _make_order(care_service, order_id="co_src_1", status="confirmed")
    created = SimpleNamespace(care_order_id="co_new_repeat", status="confirmed")
    outcome = SimpleNamespace(
        ok=True,
        reason=None,
        source_order=care_service.orders["co_src_1"],
        source_item=SimpleNamespace(quantity=1),
        product=care_service.products["prod_1"],
        selected_branch_id="branch_1",
        available_branch_ids=(),
        created_order=created,
        created_reservation=SimpleNamespace(status="created"),
    )
    _mock_repeat(care_service, outcome=outcome)
    callback = home._Callback(data="care:repeat:co_src_1", user_id=1001)
    asyncio.run(home._handler(router, "care_repeat_from_order_surface", kind="callback")(callback))
    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "✅ Reserve repeated" in text
    assert buttons["Open new order"].startswith("c2|")
    assert buttons["Back to orders"].startswith("c2|")
    assert buttons["🪥 Care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert len(callback.answer_payloads) <= 1


def test_p0_06b2_repeat_branch_selection_uses_branch_display_labels() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    _make_order(care_service, order_id="co_src_2", status="confirmed")
    outcome = SimpleNamespace(
        ok=False,
        reason="branch_selection_required",
        source_order=care_service.orders["co_src_2"],
        source_item=SimpleNamespace(quantity=1),
        product=care_service.products["prod_1"],
        selected_branch_id=None,
        available_branch_ids=("branch_1",),
        created_order=None,
        created_reservation=None,
    )
    _mock_repeat(care_service, outcome=outcome)
    callback = home._Callback(data="care:repeat:co_src_2", user_id=1001)
    asyncio.run(home._handler(router, "care_repeat_from_order_surface", kind="callback")(callback))
    text, markup = home._latest_callback_panel(callback)
    buttons = list(_button_map(markup).keys())
    assert "📍 Choose a branch" in text
    assert any("Main Branch" in key for key in buttons)


def test_p0_06b2_repeat_unavailable_has_recovery_navigation() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    _make_order(care_service, order_id="co_src_3", status="confirmed")
    outcome = SimpleNamespace(
        ok=False,
        reason="product_unavailable",
        source_order=care_service.orders["co_src_3"],
        source_item=SimpleNamespace(quantity=1),
        product=care_service.products["prod_1"],
        selected_branch_id=None,
        available_branch_ids=(),
        created_order=None,
        created_reservation=None,
    )
    _mock_repeat(care_service, outcome=outcome)
    callback = home._Callback(data="care:repeat:co_src_3", user_id=1001)
    asyncio.run(home._handler(router, "care_repeat_from_order_surface", kind="callback")(callback))
    text, markup = home._latest_callback_panel(callback)
    buttons = _button_map(markup)
    assert "Unable to repeat reserve now" in text
    assert buttons["Back to orders"].startswith("c2|")
    assert buttons["🪥 Care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"
