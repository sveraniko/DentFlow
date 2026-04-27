from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove

from app.application.booking.orchestration_outcomes import ConflictOutcome, InvalidStateOutcome, OrchestrationSuccess, SlotUnavailableOutcome
from app.application.booking.telegram_flow import BookingCardView, BookingResumePanel, PatientResolutionFlowResult
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.common.i18n import I18nService
from app.domain.booking import AvailabilitySlot, Booking, BookingSession
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, Service
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
from app.interfaces.cards.runtime_state import InMemoryRedis


class _Bot:
    def __init__(self) -> None:
        self.edits: list[dict] = []

    async def edit_message_text(self, **kwargs):  # noqa: ANN003
        self.edits.append(kwargs)
        return None


class _Message:
    def __init__(self, text: str, user_id: int = 1001) -> None:
        self.text = text
        self.bot = _Bot()
        self.chat = SimpleNamespace(id=9001)
        self.from_user = SimpleNamespace(id=user_id, full_name="Pat One")
        self.contact = None
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None):
        self.answers.append((text, reply_markup))
        return SimpleNamespace(chat=self.chat, message_id=500 + len(self.answers))


class _CallbackMessage:
    def __init__(self, message_id: int) -> None:
        self.chat = SimpleNamespace(id=9001)
        self.message_id = message_id
        self.edits: list[tuple[str, object | None]] = []
        self.answers: list[tuple[str, object | None]] = []

    async def edit_text(self, text: str, reply_markup=None):
        self.edits.append((text, reply_markup))

    async def answer(self, text: str, reply_markup=None):
        self.answers.append((text, reply_markup))
        return SimpleNamespace(chat=self.chat, message_id=900 + len(self.answers))


class _Callback:
    def __init__(self, data: str, *, user_id: int, message_id: int) -> None:
        self.data = data
        self.bot = _Bot()
        self.chat = SimpleNamespace(id=9001)
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _CallbackMessage(message_id=message_id)
        self.answers: list[str] = []
        self.answer_payloads: list[tuple[str, bool, object | None]] = []

    async def answer(self, text: str = "", show_alert: bool = False, reply_markup=None) -> None:
        self.answer_payloads.append((text, show_alert, reply_markup))
        if text:
            self.answers.append(text)
        return SimpleNamespace(chat=self.chat, message_id=self.message.message_id)


def _latest_callback_payload(callback: _Callback) -> tuple[str, object | None]:
    for payload in reversed(callback.answer_payloads):
        if payload[0] or payload[2] is not None:
            return payload[0], payload[2]
    raise AssertionError("expected callback answer payload")


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
            doctor_preference_type="specific",
            doctor_id="doctor_1",
            doctor_code_raw=None,
            selected_slot_id="slot_1",
            selected_hold_id="hold_1",
            contact_phone_snapshot=None,
            notes=None,
            expires_at=now,
            created_at=now,
            updated_at=now,
        )
        self.slot = AvailabilitySlot(
            slot_id="slot_1",
            clinic_id="clinic_main",
            branch_id="branch_1",
            doctor_id="doctor_1",
            start_at=now,
            end_at=now,
            status="open",
            visibility_policy="public",
            service_scope=None,
            source_ref=None,
            updated_at=now,
        )
        self.resume_panel_key = "contact_collection"
        self.validate_callback_result = True
        self.finalize_result = "success"
        self.select_slot_outcome: object | None = None
        self.finalize_calls = 0
        self.start_or_resume_calls = 0
        self.start_or_resume_existing_calls = 0
        self.set_contact_phone_calls = 0
        self.release_selected_slot_calls = 0
        self.release_selected_slot_outcome: object | None = None
        self.clear_doctor_preference_calls = 0
        self.mark_review_ready_calls = 0

    async def start_or_resume_session(self, **kwargs):  # noqa: ANN003
        self.start_or_resume_calls += 1
        return self.session

    async def start_or_resume_returning_patient_booking(self, **kwargs):  # noqa: ANN003
        session = await self.start_or_resume_session(**kwargs)
        from types import SimpleNamespace

        return SimpleNamespace(booking_session=session, trusted_shortcut_applied=False)


    async def start_or_resume_existing_booking_session(self, **kwargs):  # noqa: ANN003
        self.start_or_resume_existing_calls += 1
        return self.session

    async def determine_resume_panel(self, **kwargs):  # noqa: ANN003
        return BookingResumePanel(panel_key=self.resume_panel_key, booking_session=self.session)

    async def validate_active_session_callback(self, **kwargs):  # noqa: ANN003
        return self.validate_callback_result

    def list_services(self, *, clinic_id: str):
        return []

    def list_doctors(self, *, clinic_id: str, branch_id: str | None = None):
        return []

    async def list_slots_for_session(self, **kwargs):  # noqa: ANN003
        return [self.slot]

    async def select_slot(self, **kwargs):  # noqa: ANN003
        slot_id = kwargs.get("slot_id")
        if slot_id:
            self.slot = AvailabilitySlot(**{**asdict(self.slot), "slot_id": slot_id})
            self.session = BookingSession(**{**asdict(self.session), "selected_slot_id": slot_id, "selected_hold_id": f"hold_{slot_id}"})
        if self.select_slot_outcome is not None:
            return self.select_slot_outcome
        return OrchestrationSuccess(kind="success", entity=self.session)

    async def release_selected_slot_for_reselect(self, **kwargs):  # noqa: ANN003
        self.release_selected_slot_calls += 1
        if self.release_selected_slot_outcome is not None:
            return self.release_selected_slot_outcome
        self.session = BookingSession(**{**asdict(self.session), "selected_slot_id": None, "selected_hold_id": None})
        return OrchestrationSuccess(kind="success", entity=self.session)

    async def clear_doctor_preference(self, **kwargs):  # noqa: ANN003
        self.clear_doctor_preference_calls += 1
        self.session = BookingSession(
            **{
                **asdict(self.session),
                "doctor_preference_type": None,
                "doctor_id": None,
                "doctor_code_raw": None,
            }
        )
        return self.session

    async def set_contact_phone(self, *, booking_session_id: str, phone: str):
        self.set_contact_phone_calls += 1
        self.session = BookingSession(**{**asdict(self.session), "contact_phone_snapshot": phone})
        return self.session

    async def resolve_patient_from_contact(self, **kwargs):  # noqa: ANN003
        return PatientResolutionFlowResult(kind="exact_match", booking_session=self.session)

    async def mark_review_ready(self, **kwargs):  # noqa: ANN003
        self.mark_review_ready_calls += 1
        self.session = BookingSession(**{**asdict(self.session), "status": "review_ready"})
        return OrchestrationSuccess(kind="success", entity=self.session)

    async def finalize(self, **kwargs):  # noqa: ANN003
        self.finalize_calls += 1
        if self.finalize_result == "invalid":
            return InvalidStateOutcome(kind="invalid_state", reason="session terminal")
        if self.finalize_result == "slot_unavailable":
            return SlotUnavailableOutcome(kind="slot_unavailable", reason="taken")
        if self.finalize_result == "conflict":
            return ConflictOutcome(kind="conflict", reason="already booked")
        booking = Booking(
            booking_id="bk_1",
            clinic_id="clinic_main",
            patient_id="pat_1",
            doctor_id="doctor_1",
            service_id="service_consult",
            booking_mode="service_first",
            source_channel="telegram",
            scheduled_start_at=self.slot.start_at,
            scheduled_end_at=self.slot.end_at,
            status="pending_confirmation",
            confirmation_required=True,
            created_at=self.slot.start_at,
            updated_at=self.slot.start_at,
            branch_id="branch_1",
            slot_id="slot_1",
        )
        return OrchestrationSuccess(kind="success", entity=booking)

    async def get_booking_session(self, *, booking_session_id: str):
        return self.session if booking_session_id == self.session.booking_session_id else None

    async def get_availability_slot(self, *, slot_id: str):
        return self.slot if slot_id == self.slot.slot_id else None

    def build_booking_card(self, *, booking: Booking) -> BookingCardView:
        return BookingCardView(
            booking_id=booking.booking_id,
            doctor_label="Dr One",
            service_label="CONSULT",
            datetime_label=booking.scheduled_start_at.astimezone(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M %Z"),
            branch_label="Main Branch",
            status_label=f"booking.status.{booking.status}",
            next_step_key="patient.booking.card.next.pending_confirmation",
        )



def _reference() -> ClinicReferenceService:
    repo = InMemoryClinicReferenceRepository()
    repo.upsert_clinic(Clinic(clinic_id="clinic_main", code="MAIN", display_name="Main", timezone="Europe/Berlin", default_locale="en"))
    repo.upsert_branch(Branch(branch_id="branch_1", clinic_id="clinic_main", display_name="Main Branch", address_text="-", timezone="Europe/Berlin"))
    repo.upsert_service(Service(service_id="service_consult", clinic_id="clinic_main", code="CONSULT", title_key="service.cleaning", duration_minutes=30))
    repo.upsert_doctor(Doctor(doctor_id="doctor_1", clinic_id="clinic_main", display_name="Dr One", specialty_code="dent", branch_id="branch_1"))
    return ClinicReferenceService(repo)


def _handler(router, name: str, *, kind: str = "message"):
    handlers = router.message.handlers if kind == "message" else router.callback_query.handlers
    for h in handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(name)


def _build_router_and_flow(*, locale: str = "en") -> tuple[object, _BookingFlowStub, CardRuntimeCoordinator]:
    i18n = I18nService(locales_path=Path("locales"), default_locale=locale)
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    booking_flow = _BookingFlowStub()
    router = make_router(
        i18n=i18n,
        booking_flow=booking_flow,
        reference=_reference(),
        reminder_actions=_ReminderActions(),
        recommendation_service=None,
        care_commerce_service=None,
        recommendation_repository=None,
        default_locale=locale,
        card_runtime=runtime,
        card_callback_codec=codec,
    )
    return router, booking_flow, runtime


def test_contact_submission_stops_at_review_ready_panel() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}},
        )
    )

    msg = _Message(text="+1 555 123 1234", user_id=1001)
    asyncio.run(_handler(router, "on_contact_text")(msg))

    assert booking_flow.finalize_calls == 0
    assert booking_flow.session.status == "review_ready"
    assert "📋 Review your booking" in msg.answers[-1][0]
    assert "Teeth cleaning" in msg.answers[-1][0]
    assert "Date: 22 Apr 2026" in msg.answers[-1][0]
    assert "Time: 12:00" in msg.answers[-1][0]
    assert "2026-" not in msg.answers[-1][0]
    assert "UTC" not in msg.answers[-1][0]
    assert "CEST" not in msg.answers[-1][0]
    assert "service_consult" not in msg.answers[-1][0]
    assert "doctor_1" not in msg.answers[-1][0]
    assert "branch_1" not in msg.answers[-1][0]
    assert " -\n" not in msg.answers[-1][0]
    keyboard = msg.answers[-1][1]
    assert keyboard.inline_keyboard[0][0].callback_data == "book:confirm:sess_1"
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row if button.callback_data]
    assert "book:review:edit:service:sess_1" in callbacks
    assert "book:review:edit:doctor:sess_1" in callbacks
    assert "book:review:edit:time:sess_1" in callbacks
    assert "book:review:edit:phone:sess_1" in callbacks
    assert "book:review:back:sess_1" in callbacks
    assert "phome:home" in callbacks
    assert any(isinstance(reply_markup, ReplyKeyboardRemove) for _, reply_markup in msg.answers[:-1])


def test_start_renders_inline_patient_home_panel() -> None:
    router, _, _ = _build_router_and_flow()
    msg = _Message(text="/start", user_id=1001)

    asyncio.run(_handler(router, "start")(msg))

    text, keyboard = msg.answers[-1]
    assert "Choose an action" in text
    callbacks = [row[0].callback_data for row in keyboard.inline_keyboard]
    assert callbacks == ["phome:book", "phome:my_booking"]


def test_home_book_callback_reuses_booking_entry_helper() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    callback = _Callback(data="phome:book", user_id=1001, message_id=501)

    asyncio.run(_handler(router, "patient_home_book", kind="callback")(callback))

    assert booking_flow.start_or_resume_calls == 1
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_session_id"] == "sess_1"
    assert "Contact for booking" in callback.answers[-1]
    assert "+7 999 123-45-67" in callback.answers[-1]


def test_select_slot_callback_sends_contact_reply_keyboard() -> None:
    router, _, runtime = _build_router_and_flow()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}},
        )
    )
    callback = _Callback(data="book:slot:slot_1", user_id=1001, message_id=501)

    asyncio.run(_handler(router, "select_slot", kind="callback")(callback))

    text, keyboard = _latest_callback_payload(callback)
    assert "Contact for booking" in text
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    rows = [[button.text for button in row] for row in keyboard.keyboard]
    assert rows[0] == ["Share contact"]
    assert rows[1] == ["⬅️ Back", "🏠 Main menu"]
    assert callback.message.edits == []
    assert len(callback.answer_payloads) == 1
    assert callback.answer_payloads[0][1] is False


def test_select_slot_unavailable_renders_inline_notice_without_popup_and_suppresses_slot() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    booking_flow.select_slot_outcome = SlotUnavailableOutcome(kind="slot_unavailable", reason="taken")
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "slot_page": 0, "care": {}},
        )
    )
    callback = _Callback(data="book:slot:slot_1", user_id=1001, message_id=501)

    asyncio.run(_handler(router, "select_slot", kind="callback")(callback))

    text, keyboard = _latest_callback_payload(callback)
    assert "This slot is no longer available" in text
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert all(show_alert is False for _, show_alert, _ in callback.answer_payloads)
    assert len(callback.answer_payloads) == 1
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert "slot_1" in state["slot_suppressed_ids"]
    assert state["booking_mode"] == "new_booking_flow"


def test_select_slot_conflict_renders_inline_notice_without_popup_and_does_not_open_contact_stage() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    booking_flow.select_slot_outcome = ConflictOutcome(kind="conflict", reason="already booked")
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "slot_page": 0, "care": {}},
        )
    )
    callback = _Callback(data="book:slot:slot_1", user_id=1001, message_id=501)

    asyncio.run(_handler(router, "select_slot", kind="callback")(callback))

    text, _ = _latest_callback_payload(callback)
    assert "This slot is no longer available" in text
    assert "Contact for booking" not in text
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "new_booking_flow"
    assert len(callback.answer_payloads) == 1
    assert all(show_alert is False for _, show_alert, _ in callback.answer_payloads)


def test_select_slot_invalid_state_renders_inline_notice_and_keeps_slot_stage() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    booking_flow.select_slot_outcome = InvalidStateOutcome(kind="invalid_state", reason="session moved")
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}},
        )
    )
    callback = _Callback(data="book:slot:slot_1", user_id=1001, message_id=501)

    asyncio.run(_handler(router, "select_slot", kind="callback")(callback))

    text, _ = _latest_callback_payload(callback)
    assert "This slot is no longer available" in text
    assert "Contact for booking" not in text
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "new_booking_flow"
    assert len(callback.answer_payloads) == 1


def test_resume_contact_collection_callback_sends_contact_reply_keyboard() -> None:
    router, _, runtime = _build_router_and_flow()
    callback = _Callback(data="phome:book", user_id=1001, message_id=501)

    asyncio.run(_handler(router, "patient_home_book", kind="callback")(callback))

    text, keyboard = _latest_callback_payload(callback)
    assert "Contact for booking" in text
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    rows = [[button.text for button in row] for row in keyboard.keyboard]
    assert rows[0] == ["Share contact"]
    assert rows[1] == ["⬅️ Back", "🏠 Main menu"]
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "new_booking_contact"


def test_explicit_confirm_callback_finalizes_booking() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}},
        )
    )
    msg = _Message(text="+1 555 123 1234", user_id=1001)
    asyncio.run(_handler(router, "on_contact_text")(msg))

    callback = _Callback(data="book:confirm:sess_1", user_id=1001, message_id=501)
    asyncio.run(_handler(router, "confirm_new_booking", kind="callback")(callback))

    assert booking_flow.finalize_calls == 1
    assert callback.answers == []
    assert callback.bot.edits
    success_text = callback.bot.edits[-1]["text"]
    success_markup = callback.bot.edits[-1]["reply_markup"]
    assert isinstance(success_markup, InlineKeyboardMarkup)
    assert "✅ Booking created" in success_text
    assert "Doctor: Dr One" in success_text
    assert "Service: Teeth cleaning" in success_text
    assert "Date: 22 Apr 2026" in success_text
    assert "Time: 12:00" in success_text
    assert "Branch: Main Branch" in success_text
    assert "Status: pending clinic confirmation" in success_text
    assert "UTC" not in success_text
    assert "CEST" not in success_text
    assert "pending_confirmation" not in success_text
    assert "telegram" not in success_text
    assert "Actions:" not in success_text
    assert "branch: -" not in success_text
    assert "doctor_1" not in success_text
    assert "service_consult" not in success_text
    assert "branch_1" not in success_text
    assert success_markup.inline_keyboard[0][0].callback_data == "phome:my_booking"
    assert success_markup.inline_keyboard[1][0].callback_data == "phome:home"


def test_resume_review_ready_session_renders_review_panel() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    booking_flow.session = BookingSession(**{**asdict(booking_flow.session), "status": "review_ready", "contact_phone_snapshot": "+15551231234"})
    booking_flow.resume_panel_key = "review_finalize"
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}},
        )
    )

    msg = _Message(text="/book", user_id=1001)
    asyncio.run(_handler(router, "book_entry")(msg))

    assert "📋 Review your booking" in msg.answers[-1][0]
    assert msg.answers[-1][1].inline_keyboard[0][0].callback_data == "book:confirm:sess_1"


def test_stale_confirm_callback_is_rejected_without_finalize() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    booking_flow.validate_callback_result = False
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}},
        )
    )

    callback = _Callback(data="book:confirm:sess_1", user_id=1001, message_id=501)
    asyncio.run(_handler(router, "confirm_new_booking", kind="callback")(callback))

    assert booking_flow.finalize_calls == 0
    assert callback.answers == ["This button is no longer active. Please use /book to continue."]


def test_terminal_confirm_callback_is_rejected_with_safe_invalid_message() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    booking_flow.session = BookingSession(**{**asdict(booking_flow.session), "status": "completed", "contact_phone_snapshot": "+15551231234"})
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}},
        )
    )

    callback = _Callback(data="book:confirm:sess_1", user_id=1001, message_id=501)
    asyncio.run(_handler(router, "confirm_new_booking", kind="callback")(callback))

    assert booking_flow.finalize_calls == 0
    assert callback.answers == ["Booking could not be finalized from the current state."]


def test_finalize_invalid_path_is_safe_and_localized() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    booking_flow.session = BookingSession(**{**asdict(booking_flow.session), "status": "review_ready", "contact_phone_snapshot": "+15551231234"})
    booking_flow.finalize_result = "invalid"
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}},
        )
    )

    callback = _Callback(data="book:confirm:sess_1", user_id=1001, message_id=501)
    asyncio.run(_handler(router, "confirm_new_booking", kind="callback")(callback))

    assert booking_flow.finalize_calls == 1
    text, markup = _latest_callback_payload(callback)
    assert "could not confirm your booking" in text.lower()
    assert markup.inline_keyboard[0][0].callback_data == "phome:home"


def test_review_back_callback_returns_contact_prompt_reply_keyboard() -> None:
    router, _, runtime = _build_router_and_flow()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}},
        )
    )
    callback = _Callback(data="book:review:back:sess_1", user_id=1001, message_id=501)
    asyncio.run(_handler(router, "booking_review_back", kind="callback")(callback))

    text, keyboard = _latest_callback_payload(callback)
    assert "Contact for booking" in text
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    assert len(callback.answer_payloads) == 1
    assert callback.answer_payloads[0][1] is False
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "new_booking_contact"


def test_review_panel_contains_edit_actions_with_exact_callbacks() -> None:
    router, _, runtime = _build_router_and_flow()
    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}}))
    msg = _Message(text="+1 555 123 1234", user_id=1001)
    asyncio.run(_handler(router, "on_contact_text")(msg))

    keyboard = msg.answers[-1][1]
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row if button.callback_data]
    assert callbacks == [
        "book:confirm:sess_1",
        "book:review:edit:service:sess_1",
        "book:review:edit:doctor:sess_1",
        "book:review:edit:time:sess_1",
        "book:review:edit:phone:sess_1",
        "book:review:back:sess_1",
        "phome:home",
    ]


def test_review_edit_service_releases_hold_and_routes_to_service_picker() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "slot_page": 3, "slot_date_from": "2026-04-30", "slot_time_window": "morning", "slot_suppressed_ids": ["slot_x"], "care": {}}))
    callback = _Callback(data="book:review:edit:service:sess_1", user_id=1001, message_id=501)
    asyncio.run(_handler(router, "booking_review_edit", kind="callback")(callback))

    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert booking_flow.release_selected_slot_calls == 1
    assert booking_flow.session.selected_slot_id is None
    assert booking_flow.session.selected_hold_id is None
    assert state["booking_mode"] == "review_edit_service"
    assert state["slot_page"] == 0
    assert state["slot_date_from"] == ""
    assert state["slot_time_window"] == "all"
    assert state["slot_suppressed_ids"] == []
    panel_text, _ = _latest_callback_payload(callback)
    assert "service" in panel_text.lower()


def test_review_edit_doctor_and_time_release_hold_and_route() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}}))
    doctor = _Callback(data="book:review:edit:doctor:sess_1", user_id=1001, message_id=501)
    asyncio.run(_handler(router, "booking_review_edit", kind="callback")(doctor))
    assert booking_flow.release_selected_slot_calls == 1
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "review_edit_doctor"
    doctor_text, _ = _latest_callback_payload(doctor)
    assert "doctor" in doctor_text.lower()

    booking_flow.session = BookingSession(**{**asdict(booking_flow.session), "selected_slot_id": "slot_1", "selected_hold_id": "hold_1"})
    time = _Callback(data="book:review:edit:time:sess_1", user_id=1001, message_id=501)
    asyncio.run(_handler(router, "booking_review_edit", kind="callback")(time))
    assert booking_flow.release_selected_slot_calls == 2
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "review_edit_time"
    assert time.bot.edits
    assert "slot" in time.bot.edits[-1]["text"].lower()


def test_review_edit_phone_flow_keeps_slot_and_returns_to_review() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    booking_flow.session = BookingSession(**{**asdict(booking_flow.session), "contact_phone_snapshot": "+15550001111", "status": "review_ready"})
    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}}))
    callback = _Callback(data="book:review:edit:phone:sess_1", user_id=1001, message_id=501)
    asyncio.run(_handler(router, "booking_review_edit", kind="callback")(callback))
    assert booking_flow.release_selected_slot_calls == 0
    assert booking_flow.session.selected_slot_id == "slot_1"
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "review_edit_phone"
    _, keyboard = _latest_callback_payload(callback)
    assert isinstance(keyboard, ReplyKeyboardMarkup)

    msg = _Message(text="⬅️ Back", user_id=1001)
    asyncio.run(_handler(router, "on_contact_navigation")(msg))
    assert any(isinstance(reply_markup, ReplyKeyboardRemove) for _, reply_markup in msg.answers)
    assert msg.bot.edits
    assert "📋 Review your booking" in msg.bot.edits[-1]["text"]


def test_select_slot_after_review_edit_returns_to_review_when_contact_present() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    booking_flow.session = BookingSession(**{**asdict(booking_flow.session), "contact_phone_snapshot": "+15551231234", "resolved_patient_id": "pat_1"})
    asyncio.run(runtime.bind_actor_session_state(scope="patient_flow", actor_id=1001, payload={"booking_session_id": "sess_1", "booking_mode": "review_edit_time", "care": {}}))
    callback = _Callback(data="book:slot:slot_2", user_id=1001, message_id=501)
    asyncio.run(_handler(router, "select_slot", kind="callback")(callback))
    text, keyboard = _latest_callback_payload(callback)
    assert "📋 Review your booking" in text
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert booking_flow.mark_review_ready_calls >= 1
    assert len(callback.answer_payloads) == 1

def test_finalize_slot_unavailable_renders_recovery_panel_without_popup() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    booking_flow.finalize_result = "slot_unavailable"
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}},
        )
    )
    callback = _Callback(data="book:confirm:sess_1", user_id=1001, message_id=501)
    asyncio.run(_handler(router, "confirm_new_booking", kind="callback")(callback))

    text, markup = _latest_callback_payload(callback)
    assert "no longer available" in text.lower()
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]
    assert "book:slots:back:sess_1" in callbacks
    assert "phome:home" in callbacks
    assert len(callback.answer_payloads) == 1


def test_review_and_success_panels_ru_formatting() -> None:
    router, booking_flow, runtime = _build_router_and_flow(locale="ru")
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}},
        )
    )
    msg = _Message(text="+7 999 123 1234", user_id=1001)
    asyncio.run(_handler(router, "on_contact_text")(msg))
    review_text = msg.answers[-1][0]
    assert "📋 Проверьте запись" in review_text
    assert "🦷 Услуга:" in review_text
    assert "👩‍⚕️ Врач:" in review_text
    assert "📅 Дата: 22 апреля 2026" in review_text
    assert "🕒 Время: 12:00" in review_text
    assert "📍 Филиал:" in review_text
    assert "📞 Телефон:" in review_text
    assert all(token not in review_text for token in ("UTC", "MSK", "service:", "doctor:", "branch:", "2026-"))

    callback = _Callback(data="book:confirm:sess_1", user_id=1001, message_id=501)
    asyncio.run(_handler(router, "confirm_new_booking", kind="callback")(callback))
    success_text = callback.bot.edits[-1]["text"]
    assert "✅ Запись создана" in success_text
    assert "📅 Дата: 22 апреля 2026" in success_text
    assert "🕒 Время: 12:00" in success_text
    assert "Статус: ожидает подтверждения клиники" in success_text
    assert "Мы напомним вам о приёме заранее." in success_text
    assert all(token not in success_text for token in ("UTC", "MSK", "pending_confirmation", "telegram", "Actions:"))


def test_contact_submission_with_stale_session_id_is_ignored_and_state_is_normalized() -> None:
    router, booking_flow, runtime = _build_router_and_flow()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_missing", "booking_mode": "new_booking_contact", "care": {}},
        )
    )

    msg = _Message(text="+1 555 123 1234", user_id=1001)
    asyncio.run(_handler(router, "on_contact_text")(msg))

    assert booking_flow.set_contact_phone_calls == 0
    assert booking_flow.finalize_calls == 0
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_session_id"] == ""
    assert state["booking_mode"] == "new_booking_flow"
