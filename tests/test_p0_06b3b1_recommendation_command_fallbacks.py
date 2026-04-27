from __future__ import annotations

import asyncio
from types import SimpleNamespace

import test_patient_home_surface_pat_a1_2 as home


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


def test_p0_06b3b1_recommendation_open_usage_panel() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    message = home._Message(text="/recommendation_open", user_id=1001)

    asyncio.run(home._handler(router, "recommendations_open")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Open recommendation" in text
    assert "/recommendation_open <recommendation_id>" in text
    assert buttons["💬 Recommendations"] == "phome:recommendations"
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b1_recommendation_open_unresolved_patient_panel() -> None:
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    message = home._Message(text="/recommendation_open rec_latest", user_id=1001)

    asyncio.run(home._handler(router, "recommendations_open")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "could not safely resolve your patient profile" in text.lower()
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b1_recommendation_open_not_found_panel() -> None:
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_OtherPatientRepo(),
    )
    message = home._Message(text="/recommendation_open rec_latest", user_id=1001)

    asyncio.run(home._handler(router, "recommendations_open")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Recommendation not found" in text
    assert buttons["💬 Recommendations"] == "phome:recommendations"
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b1_recommendation_open_success_still_renders_detail() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    message = home._Message(text="/recommendation_open rec_latest", user_id=1001)

    asyncio.run(home._handler(router, "recommendations_open")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Latest follow-up recommendation" in text
    assert buttons["⬅️ Back to recommendations"] == "phome:recommendations"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b1_recommendation_action_usage_panel() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    message = home._Message(text="/recommendation_action", user_id=1001)

    asyncio.run(home._handler(router, "recommendations_action")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Action for recommendation" in text
    assert "/recommendation_action <ack|accept|decline> <recommendation_id>" in text
    assert buttons["💬 Recommendations"] == "phome:recommendations"
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b1_recommendation_action_invalid_action_shows_usage_panel() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    message = home._Message(text="/recommendation_action noop rec_latest", user_id=1001)

    asyncio.run(home._handler(router, "recommendations_action")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Action for recommendation" in text
    assert buttons["💬 Recommendations"] == "phome:recommendations"
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b1_recommendation_action_invalid_state_panel() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None

    async def _raise_value_error(*, recommendation_id: str):
        _ = recommendation_id
        raise ValueError("invalid state")

    recommendation_service.acknowledge = _raise_value_error  # type: ignore[method-assign]
    message = home._Message(text="/recommendation_action ack rec_latest", user_id=1001)

    asyncio.run(home._handler(router, "recommendations_action")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Action unavailable" in text
    assert buttons["💬 Recommendations"] == "phome:recommendations"
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b1_recommendation_action_success_renders_updated_detail() -> None:
    router, _, _, recommendation_service, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert recommendation_service is not None
    message = home._Message(text="/recommendation_action accept rec_latest", user_id=1001)

    asyncio.run(home._handler(router, "recommendations_action")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Status: Accepted" in text
    assert buttons["⬅️ Back to recommendations"] == "phome:recommendations"


def test_p0_06b3b1_recommendation_products_usage_panel() -> None:
    router, _, _, _, _ = home._build_router(with_recommendations=True, with_care=True, locale="en")
    message = home._Message(text="/recommendation_products", user_id=1001)

    asyncio.run(home._handler(router, "recommendation_products")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Products for recommendation" in text
    assert buttons["💬 Recommendations"] == "phome:recommendations"
    assert buttons["🪥 Care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b1_recommendation_products_unresolved_patient_panel() -> None:
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_UnresolvedRepo(),
    )
    message = home._Message(text="/recommendation_products rec_latest", user_id=1001)

    asyncio.run(home._handler(router, "recommendation_products")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "could not safely resolve your patient profile" in text.lower()
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b1_recommendation_products_not_found_panel() -> None:
    router, _, _, _, _ = home._build_router(
        with_recommendations=True,
        with_care=True,
        locale="en",
        recommendation_repository=_OtherPatientRepo(),
    )
    message = home._Message(text="/recommendation_products rec_latest", user_id=1001)

    asyncio.run(home._handler(router, "recommendation_products")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Recommendation not found" in text
    assert buttons["💬 Recommendations"] == "phome:recommendations"
    assert buttons["📅 My booking"] == "phome:my_booking"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b1_recommendation_products_manual_invalid_uses_recovery_panel() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None

    async def _manual_invalid(**kwargs):  # noqa: ANN003
        _ = kwargs
        return SimpleNamespace(status="manual_target_invalid", products=[])

    care_service.resolve_recommendation_target_result = _manual_invalid  # type: ignore[method-assign]
    message = home._Message(text="/recommendation_products rec_latest", user_id=1001)

    asyncio.run(home._handler(router, "recommendation_products")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Recommended product unavailable" in text
    assert buttons["⬅️ Back to recommendation"] == "prec:open:rec_latest"
    assert buttons["🪥 Open care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b1_recommendation_products_empty_uses_recovery_panel() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None

    async def _empty(**kwargs):  # noqa: ANN003
        _ = kwargs
        return SimpleNamespace(status="resolved", products=[])

    care_service.resolve_recommendation_target_result = _empty  # type: ignore[method-assign]
    message = home._Message(text="/recommendation_products rec_latest", user_id=1001)

    asyncio.run(home._handler(router, "recommendation_products")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "No products are linked to this recommendation yet" in text
    assert buttons["⬅️ Back to recommendation"] == "prec:open:rec_latest"
    assert buttons["🪥 Open care catalog"] == "phome:care"
    assert buttons["🏠 Main menu"] == "phome:home"


def test_p0_06b3b1_recommendation_products_success_renders_picker() -> None:
    router, _, _, _, care_service = home._build_router(with_recommendations=True, with_care=True, locale="en")
    assert care_service is not None

    async def _resolve_content(**kwargs):  # noqa: ANN003
        _ = kwargs
        return SimpleNamespace(title="Post-cleaning soft toothbrush", short_label="AF-BRUSH", description="", usage_hint="", media_refs=())

    care_service.resolve_product_content = _resolve_content  # type: ignore[method-assign]
    message = home._Message(text="/recommendation_products rec_latest", user_id=1001)

    asyncio.run(home._handler(router, "recommendation_products")(message))

    text, markup = message.answers[-1]
    buttons = _button_map(markup)
    assert "Recommended care products:" in text
    assert any(callback_data and callback_data.startswith("c2|") for callback_data in buttons.values())
