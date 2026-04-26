"""
P0-03A — Navigation callback contract (no live run).

Checklist verified:
  Service picker:
    [1] Back callback  = phome:home
    [2] Home callback  = phome:home
  Doctor picker:
    [3] Back callback  = book:back:doctors:{session_id}
    [4] Home callback  = phome:home
  Contact reply keyboard:
    [5] Home text  → ReplyKeyboardRemove sent before rendering home panel
    [6] Back text  → ReplyKeyboardRemove sent before navigating away
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from aiogram.types import ReplyKeyboardRemove

from app.application.booking.orchestration_outcomes import OrchestrationSuccess
from app.application.booking.telegram_flow import BookingResumePanel
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.common.i18n import I18nService
from app.domain.booking import BookingSession
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, DoctorAccessCode, RecordStatus, Service
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
from app.interfaces.cards.runtime_state import InMemoryRedis


# ---------------------------------------------------------------------------
# Minimal fakes
# ---------------------------------------------------------------------------

class _Bot:
    def __init__(self) -> None:
        self.edits: list[dict] = []

    async def edit_message_text(self, **kwargs):
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
        self.edits: list[tuple] = []
        self.answers: list[tuple] = []

    async def edit_text(self, text: str, reply_markup=None):
        self.edits.append((text, reply_markup))

    async def answer(self, text: str, reply_markup=None):
        self.answers.append((text, reply_markup))
        return SimpleNamespace(chat=self.chat, message_id=900 + len(self.answers))


class _Callback:
    def __init__(self, data: str, *, user_id: int, message_id: int = 500) -> None:
        self.data = data
        self.bot = _Bot()
        self.chat = SimpleNamespace(id=9001)
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _CallbackMessage(message_id=message_id)
        self.answers: list[str] = []
        self.answer_payloads: list[tuple] = []

    async def answer(self, text: str = "", show_alert: bool = False, reply_markup=None) -> None:
        self.answer_payloads.append((text, reply_markup))
        if text:
            self.answers.append(text)
        return SimpleNamespace(chat=self.chat, message_id=self.message.message_id)


def _latest_panel(callback: _Callback) -> tuple[str, object]:
    if callback.bot.edits:
        latest = callback.bot.edits[-1]
        return latest["text"], latest["reply_markup"]
    if callback.message.answers:
        return callback.message.answers[-1]
    if callback.message.edits:
        return callback.message.edits[-1]
    for text, reply_markup in reversed(callback.answer_payloads):
        if text or reply_markup is not None:
            return text, reply_markup
    raise AssertionError("expected edited panel")


# ---------------------------------------------------------------------------
# Booking flow stub
# ---------------------------------------------------------------------------

class _BookingFlowStub:
    def __init__(self) -> None:
        now = datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc)
        self.session = BookingSession(
            booking_session_id="sess_1",
            clinic_id="clinic_main",
            branch_id="branch_1",
            telegram_user_id=1001,
            resolved_patient_id="pat_1",
            status="awaiting_service",
            route_type="service_first",
            service_id=None,
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

    async def start_or_resume_returning_patient_booking(self, **kwargs):
        return SimpleNamespace(booking_session=self.session, trusted_shortcut_applied=False)

    async def start_or_resume_existing_booking_session(self, **kwargs):
        return self.session

    async def resolve_existing_booking_for_known_patient(self, **kwargs):
        return SimpleNamespace(kind="no_match", bookings=(), booking_session=self.session)

    async def determine_resume_panel(self, **kwargs):
        return BookingResumePanel(panel_key="service_selection", booking_session=self.session)

    def list_services(self, *, clinic_id: str):
        return [
            Service(
                service_id="svc_consult",
                clinic_id=clinic_id,
                code="CONSULT",
                title_key="service.consultation",
                duration_minutes=30,
            )
        ]

    def list_doctors(self, *, clinic_id: str, branch_id: str | None = None):
        return [
            Doctor(
                doctor_id="doc_1",
                clinic_id=clinic_id,
                display_name="Dr One",
                specialty_code="dent",
                branch_id="branch_1",
            )
        ]

    async def update_doctor_preference(self, **kwargs):
        return self.session

    async def update_service(self, **kwargs):
        return self.session

    async def get_booking_session(self, *, booking_session_id: str):
        return self.session if booking_session_id == self.session.booking_session_id else None

    async def validate_active_session_callback(self, **kwargs):
        return True

    async def list_slots_for_session(self, **kwargs):
        return []

    async def select_slot(self, **kwargs):
        return OrchestrationSuccess(kind="success", entity=self.session)


class _ReminderActions:
    async def handle_action(self, **kwargs):
        return SimpleNamespace(kind="invalid")


class _RecommendationRepo:
    async def find_patient_id_by_telegram_user(self, *, clinic_id: str, telegram_user_id: int) -> str:
        return "pat_1"


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def _build_router():
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    repo = InMemoryClinicReferenceRepository()
    repo.upsert_clinic(Clinic(clinic_id="clinic_main", code="MAIN", display_name="Main", timezone="UTC", default_locale="en"))
    repo.upsert_branch(Branch(branch_id="branch_1", clinic_id="clinic_main", display_name="Main Branch", address_text="-", timezone="UTC"))
    repo.upsert_service(Service(service_id="svc_consult", clinic_id="clinic_main", code="CONSULT", title_key="service.consultation", duration_minutes=30))
    repo.upsert_doctor(Doctor(doctor_id="doc_1", clinic_id="clinic_main", display_name="Dr One", specialty_code="dent", branch_id="branch_1"))
    reference = ClinicReferenceService(repo)
    booking_flow = _BookingFlowStub()
    router = make_router(
        i18n=i18n,
        booking_flow=booking_flow,
        reference=reference,
        reminder_actions=_ReminderActions(),
        recommendation_service=None,
        care_commerce_service=None,
        recommendation_repository=_RecommendationRepo(),
        default_locale="en",
        card_runtime=runtime,
        card_callback_codec=codec,
    )
    return router, runtime, booking_flow


def _handler(router, name: str, *, kind: str = "message"):
    handlers = router.message.handlers if kind == "message" else router.callback_query.handlers
    for h in handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(f"handler not found: {name}")


def _nav_row(markup) -> list:
    """Return the last row of an InlineKeyboardMarkup (navigation row)."""
    return markup.inline_keyboard[-1]


# ---------------------------------------------------------------------------
# [1] Service picker: Back callback = phome:home
# ---------------------------------------------------------------------------

def test_p0_03a_service_picker_back_callback_is_phome_home() -> None:
    """Back button in the service picker must carry callback_data='phome:home'."""
    router, runtime, _ = _build_router()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}},
        )
    )
    callback = _Callback(data="qbook:other:sess_1", user_id=1001)
    asyncio.run(_handler(router, "quick_book_other", kind="callback")(callback))

    _, markup = _latest_panel(callback)
    nav = _nav_row(markup)
    back_btn = nav[0]
    assert back_btn.callback_data == "phome:home", (
        f"Service picker Back callback must be 'phome:home', got '{back_btn.callback_data}'"
    )


# ---------------------------------------------------------------------------
# [2] Service picker: Home callback = phome:home
# ---------------------------------------------------------------------------

def test_p0_03a_service_picker_home_callback_is_phome_home() -> None:
    """Home button in the service picker must carry callback_data='phome:home'."""
    router, runtime, _ = _build_router()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}},
        )
    )
    callback = _Callback(data="qbook:other:sess_1", user_id=1001)
    asyncio.run(_handler(router, "quick_book_other", kind="callback")(callback))

    _, markup = _latest_panel(callback)
    nav = _nav_row(markup)
    home_btn = nav[-1]
    assert home_btn.callback_data == "phome:home", (
        f"Service picker Home callback must be 'phome:home', got '{home_btn.callback_data}'"
    )


# ---------------------------------------------------------------------------
# [3] Doctor picker: Back callback = book:back:doctors:{session_id}
# ---------------------------------------------------------------------------

def test_p0_03a_doctor_picker_back_callback_is_book_back_doctors() -> None:
    """Back button in the doctor picker must carry callback_data='book:back:doctors:<session_id>'."""
    router, runtime, _ = _build_router()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}},
        )
    )
    callback = _Callback(data="book:back:doctors:sess_1", user_id=1001)
    asyncio.run(_handler(router, "booking_back_to_doctors", kind="callback")(callback))

    _, markup = _latest_panel(callback)
    nav = _nav_row(markup)
    back_btn = nav[0]
    assert back_btn.callback_data == "book:back:doctors:sess_1", (
        f"Doctor picker Back callback must be 'book:back:doctors:sess_1', got '{back_btn.callback_data}'"
    )


# ---------------------------------------------------------------------------
# [4] Doctor picker: Home callback = phome:home
# ---------------------------------------------------------------------------

def test_p0_03a_doctor_picker_home_callback_is_phome_home() -> None:
    """Home button in the doctor picker must carry callback_data='phome:home'."""
    router, runtime, _ = _build_router()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_flow", "care": {}},
        )
    )
    callback = _Callback(data="book:back:doctors:sess_1", user_id=1001)
    asyncio.run(_handler(router, "booking_back_to_doctors", kind="callback")(callback))

    _, markup = _latest_panel(callback)
    nav = _nav_row(markup)
    home_btn = nav[-1]
    assert home_btn.callback_data == "phome:home", (
        f"Doctor picker Home callback must be 'phome:home', got '{home_btn.callback_data}'"
    )


# ---------------------------------------------------------------------------
# [5] Contact reply keyboard: Home removes ReplyKeyboardMarkup
# ---------------------------------------------------------------------------

def test_p0_03a_contact_home_text_removes_reply_keyboard_markup() -> None:
    """Sending the Home text while in new_booking_contact mode must send ReplyKeyboardRemove."""
    router, runtime, _ = _build_router()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}},
        )
    )
    msg = _Message(text="🏠 Main menu", user_id=1001)
    asyncio.run(_handler(router, "on_contact_navigation")(msg))

    assert any(isinstance(reply_markup, ReplyKeyboardRemove) for _, reply_markup in msg.answers), (
        "Home navigation from contact step must send ReplyKeyboardRemove to dismiss the reply keyboard"
    )


# ---------------------------------------------------------------------------
# [6] Contact reply keyboard: Back removes ReplyKeyboardMarkup
# ---------------------------------------------------------------------------

def test_p0_03a_contact_back_text_removes_reply_keyboard_markup() -> None:
    """Sending the Back text while in new_booking_contact mode must send ReplyKeyboardRemove."""
    router, runtime, _ = _build_router()
    asyncio.run(
        runtime.bind_actor_session_state(
            scope="patient_flow",
            actor_id=1001,
            payload={"booking_session_id": "sess_1", "booking_mode": "new_booking_contact", "care": {}},
        )
    )
    msg = _Message(text="⬅️ Back", user_id=1001)
    asyncio.run(_handler(router, "on_contact_navigation")(msg))

    assert any(isinstance(reply_markup, ReplyKeyboardRemove) for _, reply_markup in msg.answers), (
        "Back navigation from contact step must send ReplyKeyboardRemove to dismiss the reply keyboard"
    )
