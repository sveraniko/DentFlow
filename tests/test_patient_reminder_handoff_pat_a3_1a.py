from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.common.i18n import I18nService
from app.domain.booking import Booking
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, Service
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import BookingRuntimeSnapshot, CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore, PanelFamily
from app.interfaces.cards.runtime_state import InMemoryRedis


class _Bot:
    async def edit_message_text(self, **kwargs):  # noqa: ANN003
        return None


class _CallbackMessage:
    def __init__(self, message_id: int = 777) -> None:
        self.bot = _Bot()
        self.chat = SimpleNamespace(id=9001)
        self.message_id = message_id
        self.reply_markup_cleared = 0
        self.answers: list[tuple[str, object | None]] = []

    async def edit_reply_markup(self, reply_markup=None):
        self.reply_markup_cleared += 1
        return None

    async def answer(self, text: str, reply_markup=None):
        self.answers.append((text, reply_markup))
        return SimpleNamespace(chat=self.chat, message_id=900 + len(self.answers))


class _Callback:
    def __init__(self, data: str, *, user_id: int = 1001) -> None:
        self.data = data
        self.bot = _Bot()
        self.chat = SimpleNamespace(id=9001)
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _CallbackMessage()
        self.answered = 0

    async def answer(self, text: str = "", show_alert: bool = False, reply_markup=None) -> None:  # noqa: ARG002
        self.answered += 1
        return None


class _ReminderActions:
    async def handle_action(self, **kwargs):  # noqa: ANN003
        return SimpleNamespace(kind="accepted", reason="booking_confirmed", booking_id="b1")


class _BookingFlowStub:
    def __init__(self) -> None:
        now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
        self.booking = Booking(
            booking_id="b1",
            clinic_id="clinic_main",
            branch_id="branch_1",
            patient_id="pat_1",
            doctor_id="doctor_1",
            service_id="service_consult",
            slot_id="slot_1",
            booking_mode="patient_bot",
            source_channel="telegram",
            scheduled_start_at=now,
            scheduled_end_at=now,
            status="confirmed",
            reason_for_visit_short=None,
            patient_note=None,
            confirmation_required=True,
            confirmed_at=None,
            canceled_at=None,
            checked_in_at=None,
            in_service_at=None,
            completed_at=None,
            no_show_at=None,
            created_at=now,
            updated_at=now,
        )

    async def start_existing_booking_control_for_booking(self, **kwargs):  # noqa: ANN003
        session = SimpleNamespace(booking_session_id="sess_rem_1")
        return SimpleNamespace(kind="ready", booking=self.booking, booking_session=session)

    def build_booking_snapshot(self, **kwargs):  # noqa: ANN003
        return BookingRuntimeSnapshot(
            booking_id="b1",
            state_token="sess_rem_1",
            role_variant="patient",
            scheduled_start_at=self.booking.scheduled_start_at,
            timezone_name="UTC",
            patient_label="You",
            doctor_label="Dr One",
            service_label="Consultation",
            branch_label="Main Branch",
            status="confirmed",
            source_channel="telegram",
            patient_contact=None,
            chart_summary_entry=None,
            recommendation_summary=None,
            care_order_summary=None,
            next_step_note_key="booking.next_step.confirmed",
            compact_flags=(),
            reminder_summary=None,
            reschedule_summary=None,
        )


def _reference() -> ClinicReferenceService:
    repo = InMemoryClinicReferenceRepository()
    repo.upsert_clinic(Clinic(clinic_id="clinic_main", code="MAIN", display_name="Main", timezone="UTC", default_locale="en"))
    repo.upsert_branch(Branch(branch_id="branch_1", clinic_id="clinic_main", display_name="Main Branch", address_text="-", timezone="UTC"))
    repo.upsert_service(Service(service_id="service_consult", clinic_id="clinic_main", code="CONSULT", title_key="service.consult", duration_minutes=30))
    repo.upsert_doctor(Doctor(doctor_id="doctor_1", clinic_id="clinic_main", display_name="Dr One", specialty_code="dent", branch_id="branch_1"))
    return ClinicReferenceService(repo)


def _handler(router, name: str):
    for h in router.callback_query.handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(name)


def test_accepted_reminder_action_hands_off_to_booking_panel() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    router = make_router(
        i18n=i18n,
        booking_flow=_BookingFlowStub(),
        reference=_reference(),
        reminder_actions=_ReminderActions(),
        recommendation_service=None,
        care_commerce_service=None,
        recommendation_repository=None,
        default_locale="en",
        card_runtime=runtime,
        card_callback_codec=codec,
    )

    callback = _Callback("rem:confirm:rem_1", user_id=1001)
    asyncio.run(_handler(router, "reminder_action_callback")(callback))

    assert callback.message.reply_markup_cleared == 1
    assert callback.message.answers
    sent_text, sent_keyboard = callback.message.answers[-1]
    assert "Booking confirmed." in sent_text
    assert "Consultation" in sent_text
    assert "Main Branch" in sent_text
    assert sent_keyboard is not None

    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_session_id"] == "sess_rem_1"
    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    assert active is not None
