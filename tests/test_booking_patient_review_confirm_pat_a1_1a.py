from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.booking.orchestration_outcomes import OrchestrationSuccess
from app.application.booking.telegram_flow import BookingResumePanel, PatientResolutionFlowResult
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.common.i18n import I18nService
from app.domain.booking import AvailabilitySlot, Booking, BookingSession
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, Service
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
from app.interfaces.cards.runtime_state import InMemoryRedis


class _Bot:
    async def edit_message_text(self, **kwargs):  # noqa: ANN003
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
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _CallbackMessage(message_id=message_id)
        self.answers: list[str] = []

    async def answer(self, text: str = "", show_alert: bool = False) -> None:
        if text:
            self.answers.append(text)


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
        self.finalize_calls = 0

    async def start_or_resume_session(self, **kwargs):  # noqa: ANN003
        return self.session

    async def determine_resume_panel(self, **kwargs):  # noqa: ANN003
        return BookingResumePanel(panel_key="contact_collection", booking_session=self.session)

    async def validate_active_session_callback(self, **kwargs):  # noqa: ANN003
        return kwargs["callback_session_id"] == self.session.booking_session_id

    def list_services(self, *, clinic_id: str):
        return []

    def list_doctors(self, *, clinic_id: str, branch_id: str | None = None):
        return []

    async def list_slots_for_session(self, **kwargs):  # noqa: ANN003
        return [self.slot]

    async def select_slot(self, **kwargs):  # noqa: ANN003
        return OrchestrationSuccess(kind="success", entity=self.session)

    async def set_contact_phone(self, *, booking_session_id: str, phone: str):
        self.session = BookingSession(**{**asdict(self.session), "contact_phone_snapshot": phone})
        return self.session

    async def resolve_patient_from_contact(self, **kwargs):  # noqa: ANN003
        return PatientResolutionFlowResult(kind="exact_match", booking_session=self.session)

    async def mark_review_ready(self, **kwargs):  # noqa: ANN003
        self.session = BookingSession(**{**asdict(self.session), "status": "review_ready"})
        return OrchestrationSuccess(kind="success", entity=self.session)

    async def finalize(self, **kwargs):  # noqa: ANN003
        self.finalize_calls += 1
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



def _reference() -> ClinicReferenceService:
    repo = InMemoryClinicReferenceRepository()
    repo.upsert_clinic(Clinic(clinic_id="clinic_main", code="MAIN", display_name="Main", timezone="UTC", default_locale="en"))
    repo.upsert_branch(Branch(branch_id="branch_1", clinic_id="clinic_main", display_name="Main Branch", address_text="-", timezone="UTC"))
    repo.upsert_service(Service(service_id="service_consult", clinic_id="clinic_main", code="CONSULT", title_key="svc", duration_minutes=30))
    repo.upsert_doctor(Doctor(doctor_id="doctor_1", clinic_id="clinic_main", display_name="Dr One", specialty_code="dent", branch_id="branch_1"))
    return ClinicReferenceService(repo)


def _handler(router, name: str, *, kind: str = "message"):
    handlers = router.message.handlers if kind == "message" else router.callback_query.handlers
    for h in handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(name)


def test_contact_submission_shows_review_and_defers_finalize_until_confirm() -> None:
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
    assert "Review your booking before confirming" in msg.answers[-1][0]
    review_keyboard = msg.answers[-1][1]
    assert review_keyboard.inline_keyboard[0][0].callback_data == "book:confirm:sess_1"

    assert booking_flow.finalize_calls == 0
