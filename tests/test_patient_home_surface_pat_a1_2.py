from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.booking.orchestration_outcomes import OrchestrationSuccess
from app.application.booking.telegram_flow import BookingResumePanel
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.common.i18n import I18nService
from app.domain.booking import BookingSession
from app.domain.clinic_reference.models import Branch, Clinic
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
from app.interfaces.cards.runtime_state import InMemoryRedis


class _Bot:
    def __init__(self) -> None:
        self.edits: list[dict[str, object]] = []

    async def edit_message_text(self, **kwargs):  # noqa: ANN003
        self.edits.append(kwargs)
        return None


class _Message:
    def __init__(self, text: str, user_id: int = 1001) -> None:
        self.text = text
        self.bot = _Bot()
        self.chat = SimpleNamespace(id=9001)
        self.from_user = SimpleNamespace(id=user_id, full_name="Pat One")
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None):
        self.answers.append((text, reply_markup))
        return SimpleNamespace(chat=self.chat, message_id=500 + len(self.answers))


class _CallbackMessage:
    def __init__(self, message_id: int) -> None:
        self.chat = SimpleNamespace(id=9001)
        self.message_id = message_id
        self.edits: list[tuple[str, object | None]] = []

    async def edit_text(self, text: str, reply_markup=None):
        self.edits.append((text, reply_markup))


class _Callback:
    def __init__(self, data: str, *, user_id: int, message_id: int = 500) -> None:
        self.data = data
        self.bot = _Bot()
        self.chat = SimpleNamespace(id=9001)
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _CallbackMessage(message_id=message_id)
        self.answers: list[str] = []
        self.answer_payloads: list[tuple[str, object | None]] = []

    async def answer(self, text: str = "", show_alert: bool = False, reply_markup=None) -> None:
        self.answer_payloads.append((text, reply_markup))
        if text:
            self.answers.append(text)
        return SimpleNamespace(chat=self.chat, message_id=self.message.message_id)


def _latest_callback_panel(callback: _Callback) -> tuple[str, object]:
    if callback.bot.edits:
        latest = callback.bot.edits[-1]
        return latest["text"], latest["reply_markup"]
    if callback.message.edits:
        return callback.message.edits[-1]
    for text, reply_markup in reversed(callback.answer_payloads):
        if text or reply_markup is not None:
            return text, reply_markup
    raise AssertionError("expected edited panel")


class _ReminderActions:
    async def handle_action(self, **kwargs):  # noqa: ANN003
        return SimpleNamespace(kind="invalid")


class _BookingFlowStub:
    def __init__(self) -> None:
        now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
        self.session = BookingSession(
            booking_session_id="sess_1",
            clinic_id="clinic_main",
            branch_id="branch_1",
            telegram_user_id=1001,
            resolved_patient_id="pat_1",
            status="awaiting_contact_confirmation",
            route_type="service_first",
            service_id="service_consult",
            urgency_type=None,
            requested_date_type=None,
            requested_date=None,
            time_window=None,
            doctor_preference_type="any",
            doctor_id=None,
            doctor_code_raw=None,
            selected_slot_id=None,
            selected_hold_id=None,
            contact_phone_snapshot=None,
            notes=None,
            expires_at=now,
            created_at=now,
            updated_at=now,
        )
        self.start_or_resume_calls = 0
        self.start_or_resume_existing_calls = 0
        self.resolve_known_patient_calls = 0
        self.known_patient_result_kind = "invalid_state"

    async def start_or_resume_session(self, **kwargs):  # noqa: ANN003
        self.start_or_resume_calls += 1
        return self.session

    async def start_or_resume_existing_booking_session(self, **kwargs):  # noqa: ANN003
        self.start_or_resume_existing_calls += 1
        return self.session

    async def resolve_existing_booking_for_known_patient(self, **kwargs):  # noqa: ANN003
        self.resolve_known_patient_calls += 1
        result_session = BookingSession(
            **{
                **asdict(self.session),
                "booking_session_id": "sess_known",
                "route_type": "existing_booking_control",
                "status": "in_progress",
            }
        )
        return SimpleNamespace(kind=self.known_patient_result_kind, bookings=(), booking_session=result_session)

    async def determine_resume_panel(self, **kwargs):  # noqa: ANN003
        return BookingResumePanel(panel_key="contact_collection", booking_session=self.session)

    def list_services(self, *, clinic_id: str):
        return []

    def list_doctors(self, *, clinic_id: str, branch_id: str | None = None):
        return []

    async def list_slots_for_session(self, **kwargs):  # noqa: ANN003
        return []

    async def select_slot(self, **kwargs):  # noqa: ANN003
        return OrchestrationSuccess(kind="success", entity=self.session)


class _RecommendationRepoStub:
    def __init__(self, mapping: dict[int, str] | None = None) -> None:
        self.mapping = mapping or {1001: "pat_1"}

    async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str:
        return self.mapping.get(telegram_user_id, "pat_1")


class _RecommendationServiceStub:
    def __init__(self) -> None:
        self.list_calls = 0
        now = datetime(2026, 4, 22, 11, 0, tzinfo=timezone.utc)
        self.rows = [
            SimpleNamespace(
                recommendation_id="rec_terminal",
                patient_id="pat_1",
                recommendation_type="aftercare",
                status="accepted",
                title="Older accepted recommendation",
                body_text="Old body",
                rationale_text=None,
                clinic_id="clinic_main",
                booking_id=None,
                created_at=now,
            ),
            SimpleNamespace(
                recommendation_id="rec_latest",
                patient_id="pat_1",
                recommendation_type="follow_up",
                status="issued",
                title="Latest follow-up recommendation",
                body_text="Latest body",
                rationale_text=None,
                clinic_id="clinic_main",
                booking_id=None,
                created_at=now,
            ),
        ]
        self.mark_viewed_calls: list[str] = []
        self.actions: list[tuple[str, str]] = []

    async def list_for_patient(self, *, patient_id: str):
        self.list_calls += 1
        return self.rows

    async def get(self, recommendation_id: str):
        return next((row for row in self.rows if row.recommendation_id == recommendation_id), None)

    async def mark_viewed(self, *, recommendation_id: str):
        self.mark_viewed_calls.append(recommendation_id)
        row = await self.get(recommendation_id)
        if row is not None:
            row.status = "viewed"
        return row

    async def acknowledge(self, *, recommendation_id: str):
        self.actions.append(("ack", recommendation_id))
        row = await self.get(recommendation_id)
        if row is not None:
            row.status = "acknowledged"
        return row

    async def accept(self, *, recommendation_id: str):
        self.actions.append(("accept", recommendation_id))
        row = await self.get(recommendation_id)
        if row is not None:
            row.status = "accepted"
        return row

    async def decline(self, *, recommendation_id: str):
        self.actions.append(("decline", recommendation_id))
        row = await self.get(recommendation_id)
        if row is not None:
            row.status = "declined"
        return row


class _CareServiceStub:
    def __init__(self) -> None:
        self.list_categories_calls = 0
        self.resolution_by_recommendation_id: dict[str, list[str]] = {"rec_latest": ["prod_1"]}
        self.patient_orders: list[SimpleNamespace] = []
        self.repository = SimpleNamespace(
            list_order_items=self._list_order_items,
            get_product=self._get_product,
        )

    async def list_catalog_categories(self, *, clinic_id: str):
        self.list_categories_calls += 1
        return ["aftercare"]

    async def list_catalog_products_by_category(self, *, clinic_id: str, category: str):
        return []

    async def list_patient_orders(self, *, clinic_id: str, patient_id: str):
        return list(self.patient_orders)

    async def _list_order_items(self, care_order_id: str):
        return []

    async def _get_product(self, care_product_id: str):
        return None

    async def resolve_product_content(self, *, clinic_id: str, product, locale: str, fallback_locale: str):  # noqa: ANN001
        return SimpleNamespace(title=None)

    async def get_branch_product_availability(self, *, branch_id: str, care_product_id: str):
        return None

    async def resolve_recommendation_target_result(self, *, recommendation_id: str, **kwargs):  # noqa: ANN003
        product_ids = self.resolution_by_recommendation_id.get(recommendation_id, [])
        return SimpleNamespace(
            status="direct_links_resolved" if product_ids else "no_targets",
            products=[SimpleNamespace(care_product_id=item) for item in product_ids],
        )


def _reference() -> ClinicReferenceService:
    repo = InMemoryClinicReferenceRepository()
    repo.upsert_clinic(Clinic(clinic_id="clinic_main", code="MAIN", display_name="Main", timezone="UTC", default_locale="en"))
    repo.upsert_branch(Branch(branch_id="branch_1", clinic_id="clinic_main", display_name="Main Branch", address_text="-", timezone="UTC"))
    return ClinicReferenceService(repo)


def _handler(router, name: str, *, kind: str = "message"):
    handlers = router.message.handlers if kind == "message" else router.callback_query.handlers
    for h in handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(name)


def _build_router(*, with_recommendations: bool, with_care: bool, recommendation_repository=None):
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    booking_flow = _BookingFlowStub()
    recommendation_service = _RecommendationServiceStub() if with_recommendations else None
    care_service = _CareServiceStub() if with_care else None
    router = make_router(
        i18n=i18n,
        booking_flow=booking_flow,
        reference=_reference(),
        reminder_actions=_ReminderActions(),
        recommendation_service=recommendation_service,
        care_commerce_service=care_service,
        recommendation_repository=recommendation_repository if recommendation_repository is not None else _RecommendationRepoStub(),
        default_locale="en",
        card_runtime=runtime,
        card_callback_codec=codec,
    )
    return router, runtime, booking_flow, recommendation_service, care_service


def test_start_renders_inline_home_panel_with_localized_actions() -> None:
    router, _, _, _, _ = _build_router(with_recommendations=True, with_care=True)
    msg = _Message(text="/start")

    asyncio.run(_handler(router, "start")(msg))

    text, keyboard = msg.answers[-1]
    assert "Choose an action" in text
    callbacks = [row[0].callback_data for row in keyboard.inline_keyboard]
    assert callbacks == ["phome:book", "phome:my_booking", "phome:recommendations", "phome:care"]


def test_book_and_home_book_callback_have_equivalent_entry_state() -> None:
    router, runtime, booking_flow, _, _ = _build_router(with_recommendations=False, with_care=False)

    asyncio.run(_handler(router, "book_entry")(_Message(text="/book", user_id=1001)))
    state_after_command = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))

    callback = _Callback(data="phome:book", user_id=1001)
    asyncio.run(_handler(router, "patient_home_book", kind="callback")(callback))
    state_after_callback = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))

    assert booking_flow.start_or_resume_calls == 2
    assert state_after_command["booking_session_id"] == "sess_1"
    assert state_after_callback["booking_session_id"] == "sess_1"


def test_my_booking_and_home_callback_have_equivalent_entry_state() -> None:
    router, runtime, booking_flow, _, _ = _build_router(with_recommendations=False, with_care=False)

    asyncio.run(_handler(router, "my_booking_entry")(_Message(text="/my_booking", user_id=1001)))
    state_after_command = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))

    callback = _Callback(data="phome:my_booking", user_id=1001)
    asyncio.run(_handler(router, "patient_home_my_booking", kind="callback")(callback))
    state_after_callback = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))

    assert booking_flow.start_or_resume_existing_calls == 2
    assert state_after_command["booking_mode"] == "existing_lookup_contact"
    assert state_after_callback["booking_mode"] == "existing_lookup_contact"


def test_my_booking_direct_shortcut_uses_trusted_patient_and_skips_contact_prompt() -> None:
    router, runtime, booking_flow, _, _ = _build_router(
        with_recommendations=False,
        with_care=False,
    )
    booking_flow.known_patient_result_kind = "no_match"
    message = _Message(text="/my_booking", user_id=1001)

    asyncio.run(_handler(router, "my_booking_entry")(message))

    assert booking_flow.resolve_known_patient_calls == 1
    assert booking_flow.start_or_resume_existing_calls == 0
    text, _ = message.answers[-1]
    assert "upcoming booking for this contact" in text
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "existing_booking_control"


def test_my_booking_without_trusted_identity_falls_back_to_contact_prompt() -> None:
    class _NoTrustRecommendationRepo:
        async def find_patient_ids_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> list[str]:
            return []

    router, _, booking_flow, _, _ = _build_router(
        with_recommendations=False,
        with_care=False,
        recommendation_repository=_NoTrustRecommendationRepo(),
    )
    message = _Message(text="/my_booking", user_id=1001)

    asyncio.run(_handler(router, "my_booking_entry")(message))

    assert booking_flow.resolve_known_patient_calls == 0
    assert booking_flow.start_or_resume_existing_calls == 1
    text, _ = message.answers[-1]
    assert "share the same phone" in text


def test_recommendations_command_and_home_callback_share_entry_when_available() -> None:
    router, _, _, recommendation_service, _ = _build_router(with_recommendations=True, with_care=False)

    asyncio.run(_handler(router, "recommendations_list")(_Message(text="/recommendations", user_id=1001)))
    callback = _Callback(data="phome:recommendations", user_id=1001)
    asyncio.run(_handler(router, "patient_home_recommendations", kind="callback")(callback))

    assert recommendation_service is not None
    assert recommendation_service.list_calls == 2


def test_recommendations_panel_surfaces_latest_first_without_raw_ids() -> None:
    router, _, _, recommendation_service, _ = _build_router(with_recommendations=True, with_care=False)
    message = _Message(text="/recommendations", user_id=1001)

    asyncio.run(_handler(router, "recommendations_list")(message))

    assert recommendation_service is not None
    text, keyboard = message.answers[-1]
    assert "Latest recommendation" in text
    assert "Latest follow-up recommendation" in text
    assert "History" in text
    assert "/recommendation_open" not in text
    buttons = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert buttons[0] == "prec:open:rec_latest"


def test_recommendation_open_callback_marks_issued_as_viewed_and_renders_detail() -> None:
    router, _, _, recommendation_service, _ = _build_router(with_recommendations=True, with_care=False)
    message = _Message(text="/recommendations", user_id=1001)
    asyncio.run(_handler(router, "recommendations_list")(message))
    callback = _Callback(data="prec:open:rec_latest", user_id=1001, message_id=501)

    asyncio.run(_handler(router, "recommendation_open_callback", kind="callback")(callback))

    assert recommendation_service is not None
    assert recommendation_service.mark_viewed_calls == ["rec_latest"]


def test_proactive_open_callback_and_manual_open_share_canonical_detail_surface() -> None:
    router, _, _, _, _ = _build_router(with_recommendations=True, with_care=True)
    seed_message = _Message(text="/recommendations", user_id=1001)
    asyncio.run(_handler(router, "recommendations_list")(seed_message))
    proactive_callback = _Callback(data="prec:open:rec_latest", user_id=1001, message_id=501)
    manual_message = _Message(text="/recommendation_open rec_latest", user_id=1001)

    asyncio.run(_handler(router, "recommendation_open_callback", kind="callback")(proactive_callback))
    asyncio.run(_handler(router, "recommendations_open")(manual_message))

    proactive_edit = proactive_callback.bot.edits[-1]
    proactive_text = proactive_edit["text"]
    proactive_keyboard = proactive_edit["reply_markup"]
    manual_edit = manual_message.bot.edits[-1]
    manual_text = manual_edit["text"]
    manual_keyboard = manual_edit["reply_markup"]
    assert proactive_text == manual_text
    proactive_buttons = [button.text for row in proactive_keyboard.inline_keyboard for button in row]
    manual_buttons = [button.text for row in manual_keyboard.inline_keyboard for button in row]
    assert "Open recommended products" in proactive_buttons
    assert proactive_buttons == manual_buttons


def test_recommendation_action_callback_updates_lifecycle_and_re_renders_detail() -> None:
    router, _, _, recommendation_service, _ = _build_router(with_recommendations=True, with_care=False)
    message = _Message(text="/recommendations", user_id=1001)
    asyncio.run(_handler(router, "recommendations_list")(message))
    callback = _Callback(data="prec:act:accept:rec_latest", user_id=1001, message_id=501)

    asyncio.run(_handler(router, "recommendation_action_callback", kind="callback")(callback))

    assert recommendation_service is not None
    assert ("accept", "rec_latest") in recommendation_service.actions
    assert recommendation_service.rows[1].status == "accepted"


def test_recommendation_actions_keep_continuity_for_ack_accept_decline() -> None:
    router, _, _, recommendation_service, _ = _build_router(with_recommendations=True, with_care=False)
    assert recommendation_service is not None

    for action, expected_status in (("ack", "Acknowledged"), ("accept", "Accepted"), ("decline", "Declined")):
        recommendation_service.rows[1].status = "viewed"
        callback = _Callback(data=f"prec:act:{action}:rec_latest", user_id=1001, message_id=501)
        asyncio.run(_handler(router, "recommendation_action_callback", kind="callback")(callback))
        assert callback.answers
        assert f"Current status: {expected_status}" in callback.answers[-1]


def test_recommendation_callback_rejects_malformed_payload_safely() -> None:
    router, _, _, _, _ = _build_router(with_recommendations=True, with_care=False)
    callback = _Callback(data="prec:act:accept:", user_id=1001, message_id=501)

    asyncio.run(_handler(router, "recommendation_action_callback", kind="callback")(callback))

    assert callback.answers
    assert "no longer available" in callback.answers[-1]


def test_recommendation_open_callback_rejects_stale_or_manually_replayed_payloads_safely() -> None:
    router, _, _, _, _ = _build_router(with_recommendations=True, with_care=False)
    malformed = _Callback(data="prec:open:", user_id=1001, message_id=501)
    missing = _Callback(data="prec:open:rec_missing", user_id=1001, message_id=502)

    asyncio.run(_handler(router, "recommendation_open_callback", kind="callback")(malformed))
    asyncio.run(_handler(router, "recommendation_open_callback", kind="callback")(missing))

    assert malformed.answers
    assert "no longer available" in malformed.answers[-1]
    assert missing.answers
    assert "Recommendation not found." in missing.answers[-1]


def test_recommendation_open_and_actions_reject_other_patient_recommendation() -> None:
    repo = _RecommendationRepoStub(mapping={1001: "pat_other"})
    router, _, _, _, _ = _build_router(with_recommendations=True, with_care=False, recommendation_repository=repo)
    open_callback = _Callback(data="prec:open:rec_latest", user_id=1001, message_id=501)
    action_callback = _Callback(data="prec:act:ack:rec_latest", user_id=1001, message_id=502)

    asyncio.run(_handler(router, "recommendation_open_callback", kind="callback")(open_callback))
    asyncio.run(_handler(router, "recommendation_action_callback", kind="callback")(action_callback))

    assert "Recommendation not found." in open_callback.answers[-1]
    assert "Recommendation not found." in action_callback.answers[-1]


def test_recommendation_detail_shows_products_cta_only_when_targets_resolvable() -> None:
    router, _, _, recommendation_service, care_service = _build_router(with_recommendations=True, with_care=True)
    assert recommendation_service is not None
    assert care_service is not None
    message = _Message(text="/recommendation_open rec_latest", user_id=1001)

    asyncio.run(_handler(router, "recommendations_open")(message))
    with_target_buttons = [button.text for row in message.answers[-1][1].inline_keyboard for button in row]
    assert "Open recommended products" in with_target_buttons

    care_service.resolution_by_recommendation_id["rec_latest"] = []
    message_no_target = _Message(text="/recommendation_open rec_latest", user_id=1001)
    asyncio.run(_handler(router, "recommendations_open")(message_no_target))
    assert message_no_target.bot.edits
    reply_markup = message_no_target.bot.edits[-1]["reply_markup"]
    no_target_buttons = [button.text for row in reply_markup.inline_keyboard for button in row]
    assert "Open recommended products" not in no_target_buttons


def test_recommendation_products_callback_reuses_resolution_and_falls_back_safely() -> None:
    router, _, _, _, care_service = _build_router(with_recommendations=True, with_care=True)
    assert care_service is not None
    care_service.resolution_by_recommendation_id["rec_latest"] = []
    callback = _Callback(data="prec:products:rec_latest", user_id=1001, message_id=501)

    asyncio.run(_handler(router, "recommendation_products_callback", kind="callback")(callback))

    assert callback.answers
    assert "No care products are linked to this recommendation yet." in callback.answers[-1]


def test_pat_a7_1b_contains_no_new_migration_artifacts() -> None:
    migrations_root = Path("migrations")
    if not migrations_root.exists():
        assert True
        return
    assert not any("pat_a7_1b" in path.name.lower() for path in migrations_root.rglob("*.py"))


def test_care_command_and_home_callback_share_entry_when_available() -> None:
    router, _, _, _, care_service = _build_router(with_recommendations=False, with_care=True)

    asyncio.run(_handler(router, "care_catalog")(_Message(text="/care", user_id=1001)))
    callback = _Callback(data="phome:care", user_id=1001)
    asyncio.run(_handler(router, "patient_home_care", kind="callback")(callback))

    assert care_service is not None
    assert care_service.list_categories_calls == 2


def test_care_entry_surface_contains_callback_to_orders_panel() -> None:
    router, _, _, _, _ = _build_router(with_recommendations=False, with_care=True)
    callback = _Callback(data="phome:care", user_id=1001)

    asyncio.run(_handler(router, "patient_home_care", kind="callback")(callback))

    _, markup = _latest_callback_panel(callback)
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert "care:orders" in callbacks


def test_care_orders_command_and_callback_share_canonical_orders_surface() -> None:
    router, _, _, _, care_service = _build_router(with_recommendations=False, with_care=True)
    assert care_service is not None
    message = _Message(text="/care_orders", user_id=1001)
    callback = _Callback(data="care:orders", user_id=1001)

    asyncio.run(_handler(router, "care_orders")(message))
    asyncio.run(_handler(router, "care_orders_callback", kind="callback")(callback))

    message_text, _ = message.answers[-1]
    callback_text, _ = _latest_callback_panel(callback)
    assert message_text == callback_text
    assert "no care reserves or orders" in message_text


def test_care_orders_empty_state_includes_browse_catalog_cta() -> None:
    router, _, _, _, _ = _build_router(with_recommendations=False, with_care=True)
    callback = _Callback(data="care:orders", user_id=1001)

    asyncio.run(_handler(router, "care_orders_callback", kind="callback")(callback))

    text, markup = _latest_callback_panel(callback)
    assert "no care reserves or orders" in text
    actions = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert "care:catalog" in actions


def test_home_hides_optional_actions_when_services_unavailable() -> None:
    router, _, _, _, _ = _build_router(with_recommendations=False, with_care=False)
    msg = _Message(text="/start")

    asyncio.run(_handler(router, "start")(msg))

    _, keyboard = msg.answers[-1]
    callbacks = [row[0].callback_data for row in keyboard.inline_keyboard]
    assert callbacks == ["phome:book", "phome:my_booking"]


def test_stale_optional_callback_is_safe_when_service_unavailable() -> None:
    router, _, _, _, _ = _build_router(with_recommendations=False, with_care=False)
    callback = _Callback(data="phome:recommendations", user_id=1001)

    asyncio.run(_handler(router, "patient_home_recommendations", kind="callback")(callback))

    texts = [item[0] for item in callback.message.edits] + callback.answers
    assert "This section is currently unavailable." in texts
