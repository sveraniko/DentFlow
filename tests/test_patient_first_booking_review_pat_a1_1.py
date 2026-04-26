from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.application.booking.orchestration_outcomes import InvalidStateOutcome, OrchestrationSuccess
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

    async def edit_text(self, text: str, reply_markup=None):
        self.edits.append((text, reply_markup))


class _Callback:
    def __init__(self, data: str, *, user_id: int, message_id: int) -> None:
        self.data = data
        self.bot = _Bot()
        self.chat = SimpleNamespace(id=9001)
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _CallbackMessage(message_id=message_id)
        self.answers: list[str] = []

    async def answer(self, text: str = "", show_alert: bool = False, reply_markup=None) -> None:
        if text:
            self.answers.append(text)
        return SimpleNamespace(chat=self.chat, message_id=self.message.message_id)


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
        self.finalize_calls = 0
        self.start_or_resume_calls = 0
        self.start_or_resume_existing_calls = 0
        self.set_contact_phone_calls = 0

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
        return OrchestrationSuccess(kind="success", entity=self.session)

    async def set_contact_phone(self, *, booking_session_id: str, phone: str):
        self.set_contact_phone_calls += 1
        self.session = BookingSession(**{**asdict(self.session), "contact_phone_snapshot": phone})
        return self.session

    async def resolve_patient_from_contact(self, **kwargs):  # noqa: ANN003
        return PatientResolutionFlowResult(kind="exact_match", booking_session=self.session)

    async def mark_review_ready(self, **kwargs):  # noqa: ANN003
        self.session = BookingSession(**{**asdict(self.session), "status": "review_ready"})
        return OrchestrationSuccess(kind="success", entity=self.session)

    async def finalize(self, **kwargs):  # noqa: ANN003
        self.finalize_calls += 1
        if self.finalize_result == "invalid":
            return InvalidStateOutcome(kind="invalid_state", reason="session terminal")
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


def _build_router_and_flow() -> tuple[object, _BookingFlowStub, CardRuntimeCoordinator]:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
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
        default_locale="en",
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
    assert "Review your booking before confirming" in msg.answers[-1][0]
    assert "Teeth cleaning" in msg.answers[-1][0]
    assert "2026-04-22 12:00 CEST" in msg.answers[-1][0]
    assert msg.answers[-1][1].inline_keyboard[0][0].callback_data == "book:confirm:sess_1"


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
    assert "Doctor: Dr One" in success_text
    assert "Service: Teeth cleaning" in success_text
    assert "Time: 2026-04-22 12:00 CEST" in success_text
    assert "Branch: Main Branch" in success_text
    assert "Status: Pending confirmation" in success_text
    assert "doctor_1" not in success_text
    assert "service_consult" not in success_text
    assert "branch_1" not in success_text


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

    assert "Review your booking before confirming" in msg.answers[-1][0]
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
    assert callback.answers[-1] == "Booking could not be finalized from the current state."


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
