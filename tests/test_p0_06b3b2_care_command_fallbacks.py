from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import test_patient_home_surface_pat_a1_2 as home
from app.common.i18n import I18nService
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
from app.interfaces.cards.runtime_state import InMemoryRedis


def _button_map(markup) -> dict[str, str]:
    return {button.text: button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data}


class _UnresolvedRepo:
    async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str | None:
        _ = clinic_id, telegram_user_id
        return None


class _OtherPatientRepo:
    async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str:
        _ = clinic_id, telegram_user_id
        return "pat_other"


def _mock_repeat(care_service, *, outcome):
    async def _repeat_order_as_new(**kwargs):  # noqa: ANN003
        _ = kwargs
        return outcome

    care_service.repeat_order_as_new = _repeat_order_as_new  # type: ignore[attr-defined]

def _mock_product_content(care_service) -> None:  # noqa: ANN001
    async def _resolve_content(**kwargs):  # noqa: ANN003
        _ = kwargs
        return SimpleNamespace(title=None, short_label=None, description="", usage_hint="", media_refs=())

    care_service.resolve_product_content = _resolve_content  # type: ignore[method-assign]


def _build_router_without_primary_clinic():
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    reference = home._reference()
    reference.repository.clinics = {}
    booking_flow = home._BookingFlowStub()
    recommendation_service = home._RecommendationServiceStub()
    care_service = home._CareServiceStub()
    router = make_router(
        i18n=i18n,
        booking_flow=booking_flow,
        reference=reference,
        reminder_actions=home._ReminderActions(),
        recommendation_service=recommendation_service,
        care_commerce_service=care_service,
        recommendation_repository=home._RecommendationRepoStub(),
        default_locale="en",
        card_runtime=runtime,
        card_callback_codec=codec,
    )
    return router


def test_p0_06b3b2_care_product_open_usage_panel() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    message = home._Message(text="/care_product_open", user_id=1001)

    asyncio.run(home._handler(router, "care_product_open")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Open care product" in text
    assert "/care_product_open <product_id>" in text
    assert buttons["🪥 Care catalog"] == "phome:care"
    assert buttons["📦 My reserves / orders"] == "care:orders"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b2_care_product_open_clinic_unavailable_panel() -> None:
    router = _build_router_without_primary_clinic()
    message = home._Message(text="/care_product_open prod_1", user_id=1001)

    asyncio.run(home._handler(router, "care_product_open")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Care catalog unavailable" in text
    assert buttons == {"🏠 Main menu": "phome:home"}


def test_p0_06b3b2_care_product_open_missing_uses_panel() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    message = home._Message(text="/care_product_open prod_missing", user_id=1001)

    asyncio.run(home._handler(router, "care_product_open")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Product unavailable" in text
    assert buttons["🪥 Open care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b2_care_product_open_success_still_renders_b1_card() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    _mock_product_content(care_service)
    message = home._Message(text="/care_product_open prod_1", user_id=1001)

    asyncio.run(home._handler(router, "care_product_open")(message))

    text, _ = message.answers[-1]
    assert "Post-cleaning soft toothbrush" in text
    for forbidden in ("care_product_id", "patient_id", "source_channel", "booking_mode"):
        assert forbidden not in text


def test_p0_06b3b2_care_order_create_usage_panel() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    message = home._Message(text="/care_order_create", user_id=1001)

    asyncio.run(home._handler(router, "care_order_create")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Create care reserve" in text
    assert buttons["💬 Recommendations"] == "phome:recommendations"
    assert buttons["🪥 Care catalog"] == "phome:care"
    assert buttons["📦 My reserves / orders"] == "care:orders"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b2_care_order_create_unresolved_panel() -> None:
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    message = home._Message(text="/care_order_create rec_latest prod_1 branch_1", user_id=1001)

    asyncio.run(home._handler(router, "care_order_create")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Could not safely resolve your patient profile" in text
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert "phome:care" in buttons.values()
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b2_care_order_create_recommendation_not_found_panel() -> None:
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_OtherPatientRepo(),
    )
    message = home._Message(text="/care_order_create rec_latest prod_1 branch_1", user_id=1001)

    asyncio.run(home._handler(router, "care_order_create")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Recommendation not found" in text
    assert buttons["💬 Recommendations"] == "phome:recommendations"
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b2_care_order_create_branch_invalid_panel() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    message = home._Message(text="/care_order_create rec_latest prod_1 branch_404", user_id=1001)

    asyncio.run(home._handler(router, "care_order_create")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Branch unavailable" in text
    assert buttons["🪥 Care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b2_care_order_create_product_not_linked_panel() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    message = home._Message(text="/care_order_create rec_latest prod_404 branch_1", user_id=1001)

    asyncio.run(home._handler(router, "care_order_create")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Product is not linked to recommendation" in text
    assert buttons["🪥 Products by recommendation"] == "prec:products:rec_latest"
    assert buttons["🪥 Care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b2_care_order_create_out_of_stock_panel_uses_branch_label() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    care_service.availability[("branch_1", "prod_1")].free_qty = 0
    message = home._Message(text="/care_order_create rec_latest prod_1 branch_1", user_id=1001)

    asyncio.run(home._handler(router, "care_order_create")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Not available right now" in text and "Main Branch" in text
    assert "branch_1" not in text
    assert buttons["🪥 Care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b2_care_order_create_success_uses_structured_result_panel() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    message = home._Message(text="/care_order_create rec_latest prod_1 branch_1", user_id=1001)

    asyncio.run(home._handler(router, "care_order_create")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "✅ Product reserved" in text and "Main Branch" in text
    assert buttons["📦 Open reserve"].startswith("careo:open:")
    assert buttons["📦 My reserves / orders"] == "care:orders"
    assert buttons["🪥 Care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"
    assert "confirmed" not in text.lower()
    assert "branch_1" not in text


def test_p0_06b3b2_care_orders_unresolved_panel() -> None:
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    message = home._Message(text="/care_orders", user_id=1001)

    asyncio.run(home._handler(router, "care_orders")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Could not safely resolve your patient profile" in text
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b2_care_orders_success_panel() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    message = home._Message(text="/care_orders", user_id=1001)

    asyncio.run(home._handler(router, "care_orders")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "You have no reserves yet" in text
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b2_care_order_repeat_usage_panel() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    message = home._Message(text="/care_order_repeat", user_id=1001)

    asyncio.run(home._handler(router, "care_order_repeat")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Repeat reserve" in text
    assert buttons["📦 My reserves / orders"] == "care:orders"
    assert buttons["🪥 Care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b2_care_order_repeat_unresolved_panel() -> None:
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    message = home._Message(text="/care_order_repeat co_src_1", user_id=1001)

    asyncio.run(home._handler(router, "care_order_repeat")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Could not safely resolve your patient profile" in text
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b2_care_order_repeat_success_renders_panel_with_keyboard() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    created = SimpleNamespace(care_order_id="co_new_repeat", status="confirmed")
    outcome = SimpleNamespace(
        ok=True,
        reason=None,
        source_order=SimpleNamespace(),
        source_item=SimpleNamespace(quantity=1),
        product=care_service.products["prod_1"],
        selected_branch_id="branch_1",
        available_branch_ids=(),
        created_order=created,
        created_reservation=SimpleNamespace(status="created"),
    )
    _mock_repeat(care_service, outcome=outcome)
    message = home._Message(text="/care_order_repeat co_src_1", user_id=1001)

    asyncio.run(home._handler(router, "care_order_repeat")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Reserve repeated" in text
    assert buttons["Open new order"].startswith("c2|")
    assert buttons["Back to orders"].startswith("c2|")
    assert buttons["🪥 Care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b2_care_order_repeat_branch_selection_has_display_labels() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    outcome = SimpleNamespace(
        ok=False,
        reason="branch_selection_required",
        source_order=SimpleNamespace(),
        source_item=SimpleNamespace(quantity=1),
        product=care_service.products["prod_1"],
        selected_branch_id=None,
        available_branch_ids=("branch_1",),
        created_order=None,
        created_reservation=None,
    )
    _mock_repeat(care_service, outcome=outcome)
    message = home._Message(text="/care_order_repeat co_src_2", user_id=1001)

    asyncio.run(home._handler(router, "care_order_repeat")(message))

    text, markup = message.answers[-1]
    buttons = list(_button_map(markup).keys())
    assert "Choose a branch" in text
    assert any("Main Branch" in label for label in buttons)
    assert any("Back to orders" in label for label in buttons)


def test_p0_06b3b2_care_order_repeat_unavailable_recovery_panel() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None
    outcome = SimpleNamespace(
        ok=False,
        reason="product_unavailable",
        source_order=SimpleNamespace(),
        source_item=SimpleNamespace(quantity=1),
        product=care_service.products["prod_1"],
        selected_branch_id=None,
        available_branch_ids=(),
        created_order=None,
        created_reservation=None,
    )
    _mock_repeat(care_service, outcome=outcome)
    message = home._Message(text="/care_order_repeat co_src_3", user_id=1001)

    asyncio.run(home._handler(router, "care_order_repeat")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Unable to repeat reserve now" in text
    assert buttons["Back to orders"].startswith("c2|")
    assert buttons["🪥 Care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"
