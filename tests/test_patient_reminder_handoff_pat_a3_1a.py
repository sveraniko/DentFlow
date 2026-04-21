from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.common.i18n import I18nService
from app.domain.booking import Booking
from app.domain.communication import ReminderJob
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
    def __init__(self, data: str, *, user_id: int = 1001, message_id: int = 777) -> None:
        self.data = data
        self.bot = _Bot()
        self.chat = SimpleNamespace(id=9001)
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _CallbackMessage(message_id=message_id)
        self.answered: list[tuple[str, bool]] = []

    async def answer(self, text: str = "", show_alert: bool = False, reply_markup=None) -> None:  # noqa: ARG002
        self.answered.append((text, show_alert))


class _ReminderActions:
    def __init__(self, *, outcome_kind: str, outcome_reason: str, booking_id: str | None = "b1") -> None:
        self._outcome_kind = outcome_kind
        self._outcome_reason = outcome_reason
        self._booking_id = booking_id
        self.calls: list[dict[str, object | None]] = []
        self.repository = _ReminderRepository(booking_id=booking_id)

    async def handle_action(self, **kwargs):  # noqa: ANN003
        self.calls.append(kwargs)
        return SimpleNamespace(kind=self._outcome_kind, reason=self._outcome_reason, booking_id=self._booking_id)


class _BookingFlowStub:
    def __init__(self, *, status: str = "confirmed", start_kind: str = "ready") -> None:
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
            status=status,
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
        self.start_kind = start_kind
        self.reschedule_start_kind = "ready"

    async def start_existing_booking_control_for_booking(self, **kwargs):  # noqa: ANN003
        if self.start_kind != "ready":
            return SimpleNamespace(kind=self.start_kind, booking=None, booking_session=None)
        session = SimpleNamespace(booking_session_id="sess_rem_1")
        return SimpleNamespace(kind="ready", booking=self.booking, booking_session=session)

    async def start_patient_reschedule_session(self, **kwargs):  # noqa: ANN003
        if self.reschedule_start_kind != "ready":
            return SimpleNamespace(kind=self.reschedule_start_kind, booking=None, booking_session=None)
        session = SimpleNamespace(booking_session_id="sess_rsch_1")
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
            status=self.booking.status,
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


class _ReminderRepository:
    def __init__(self, *, booking_id: str | None) -> None:
        now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
        self._reminder = ReminderJob(
            reminder_id="rem_1",
            clinic_id="clinic_main",
            patient_id="pat_1",
            booking_id=booking_id,
            care_order_id=None,
            recommendation_id=None,
            reminder_type="booking_confirmation",
            channel="telegram",
            status="sent",
            scheduled_for=now,
            payload_key="booking.confirmation",
            locale_at_send_time="en",
            planning_group="g1",
            supersedes_reminder_id=None,
            created_at=now,
            updated_at=now,
        )

    async def get_reminder(self, *, reminder_id: str) -> ReminderJob | None:
        if reminder_id != "rem_1":
            return None
        return self._reminder


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


def _build_router(*, reminder_actions, booking_flow):
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    router = make_router(
        i18n=i18n,
        booking_flow=booking_flow,
        reference=_reference(),
        reminder_actions=reminder_actions,
        recommendation_service=None,
        care_commerce_service=None,
        recommendation_repository=None,
        default_locale="en",
        card_runtime=runtime,
        card_callback_codec=codec,
    )
    return router, runtime


@pytest.mark.parametrize(
    ("action", "reason", "status", "expected_header", "expect_confirm_button"),
    [
        ("confirm", "booking_confirmed", "confirmed", "Booking confirmed.", False),
        ("reschedule", "reschedule_requested", "reschedule_requested", "Reschedule request received.", False),
        ("ack", "acknowledged", "pending_confirmation", "Got it, thanks.", True),
    ],
)
def test_accepted_reminder_actions_handoff_to_canonical_booking_panel(
    action: str,
    reason: str,
    status: str,
    expected_header: str,
    expect_confirm_button: bool,
) -> None:
    router, runtime = _build_router(
        reminder_actions=_ReminderActions(outcome_kind="accepted", outcome_reason=reason, booking_id="b1"),
        booking_flow=_BookingFlowStub(status=status),
    )
    callback = _Callback(f"rem:{action}:rem_1", user_id=1001)

    asyncio.run(_handler(router, "reminder_action_callback")(callback))

    assert callback.message.reply_markup_cleared == 1
    sent_text, sent_keyboard = callback.message.answers[-1]
    assert expected_header in sent_text
    if action == "reschedule":
        assert "Reschedule mode started." in sent_text
        assert "select a new time" in sent_text.lower()
        assert sent_keyboard is not None
        rendered_labels = [button.text for row in sent_keyboard.inline_keyboard for button in row]
        assert rendered_labels == ["Select new time"]
    else:
        assert "Consultation" in sent_text
        assert "Main Branch" in sent_text
        assert sent_keyboard is not None
        rendered_labels = [button.text for row in sent_keyboard.inline_keyboard for button in row]
        assert ("Confirm" in rendered_labels) is expect_confirm_button

    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    if action == "reschedule":
        assert state["booking_session_id"] == "sess_rsch_1"
        assert state["booking_mode"] == "reschedule_booking_control"
    else:
        assert state["booking_session_id"] == "sess_rem_1"
        assert state["booking_mode"] == "existing_booking_control"
    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    assert active is not None


def test_reminder_cancel_first_tap_shows_confirmation_and_does_not_mutate() -> None:
    reminder_actions = _ReminderActions(outcome_kind="accepted", outcome_reason="booking_canceled", booking_id="b1")
    router, runtime = _build_router(
        reminder_actions=reminder_actions,
        booking_flow=_BookingFlowStub(status="confirmed"),
    )
    callback = _Callback("rem:cancel:rem_1", user_id=1001)

    asyncio.run(_handler(router, "reminder_action_callback")(callback))

    assert reminder_actions.calls == []
    assert callback.message.reply_markup_cleared == 1
    sent_text, sent_keyboard = callback.message.answers[-1]
    assert sent_text == "Cancel this booking?"
    assert sent_keyboard is not None
    rendered = [button.text for row in sent_keyboard.inline_keyboard for button in row]
    assert rendered == ["Yes", "No"]
    callback_data = [button.callback_data for row in sent_keyboard.inline_keyboard for button in row]
    assert callback_data == ["remc:confirm:rem_1:777", "remc:abort:rem_1:777"]
    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    assert active is None


def test_reminder_cancel_confirm_cancels_and_handoffs_to_canonical_panel() -> None:
    reminder_actions = _ReminderActions(outcome_kind="accepted", outcome_reason="booking_canceled", booking_id="b1")
    router, runtime = _build_router(
        reminder_actions=reminder_actions,
        booking_flow=_BookingFlowStub(status="canceled"),
    )
    callback = _Callback("remc:confirm:rem_1:777", user_id=1001, message_id=991)

    asyncio.run(_handler(router, "reminder_cancel_confirm_callback")(callback))

    assert len(reminder_actions.calls) == 1
    assert reminder_actions.calls[0] == {"reminder_id": "rem_1", "action": "cancel", "provider_message_id": "777"}
    assert callback.message.reply_markup_cleared == 1
    sent_text, sent_keyboard = callback.message.answers[-1]
    assert "Booking canceled." in sent_text
    assert "Consultation" in sent_text
    assert sent_keyboard is not None
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "existing_booking_control"
    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    assert active is not None


def test_reminder_cancel_abort_does_not_mutate_booking() -> None:
    reminder_actions = _ReminderActions(outcome_kind="accepted", outcome_reason="booking_canceled", booking_id="b1")
    router, runtime = _build_router(
        reminder_actions=reminder_actions,
        booking_flow=_BookingFlowStub(status="confirmed"),
    )
    callback = _Callback("remc:abort:rem_1:777", user_id=1001, message_id=991)

    asyncio.run(_handler(router, "reminder_cancel_confirm_callback")(callback))

    assert reminder_actions.calls == []
    assert callback.message.reply_markup_cleared == 1
    sent_text, sent_keyboard = callback.message.answers[-1]
    assert "Cancellation aborted." in sent_text
    assert "Consultation" in sent_text
    assert sent_keyboard is not None
    assert callback.answered[-1] == ("", False)
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "existing_booking_control"
    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    assert active is not None


def test_accepted_handoff_without_booking_context_uses_safe_fallback() -> None:
    router, runtime = _build_router(
        reminder_actions=_ReminderActions(outcome_kind="accepted", outcome_reason="booking_confirmed", booking_id=None),
        booking_flow=_BookingFlowStub(),
    )
    callback = _Callback("rem:confirm:rem_1", user_id=1001)

    asyncio.run(_handler(router, "reminder_action_callback")(callback))

    sent_text, sent_keyboard = callback.message.answers[-1]
    assert "Booking confirmed." in sent_text
    assert "booking details are unavailable" in sent_text.lower()
    assert sent_keyboard is None

    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state in ({}, None)


def test_accepted_handoff_when_session_bind_cannot_start_uses_safe_fallback() -> None:
    router, _ = _build_router(
        reminder_actions=_ReminderActions(outcome_kind="accepted", outcome_reason="booking_confirmed", booking_id="b1"),
        booking_flow=_BookingFlowStub(start_kind="booking_missing"),
    )
    callback = _Callback("rem:confirm:rem_1", user_id=1001)

    asyncio.run(_handler(router, "reminder_action_callback")(callback))

    sent_text, sent_keyboard = callback.message.answers[-1]
    assert "Booking confirmed." in sent_text
    assert "booking details are unavailable" in sent_text.lower()
    assert "booking_missing" not in sent_text
    assert sent_keyboard is None


def test_stale_reminder_callback_is_bounded_and_does_not_handoff() -> None:
    router, runtime = _build_router(
        reminder_actions=_ReminderActions(outcome_kind="stale", outcome_reason="reminder_acknowledged", booking_id="b1"),
        booking_flow=_BookingFlowStub(),
    )
    callback = _Callback("rem:confirm:rem_1", user_id=1001)

    asyncio.run(_handler(router, "reminder_action_callback")(callback))

    assert callback.message.reply_markup_cleared == 0
    assert callback.message.answers == []
    assert callback.answered[-1] == ("This reminder action is no longer active.", True)
    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    assert active is None


def test_invalid_reminder_callback_is_bounded_and_does_not_handoff() -> None:
    router, runtime = _build_router(
        reminder_actions=_ReminderActions(outcome_kind="invalid", outcome_reason="message_mismatch", booking_id="b1"),
        booking_flow=_BookingFlowStub(),
    )
    callback = _Callback("rem:confirm:rem_1", user_id=1001)

    asyncio.run(_handler(router, "reminder_action_callback")(callback))

    assert callback.message.reply_markup_cleared == 0
    assert callback.message.answers == []
    assert callback.answered[-1] == ("This reminder action is invalid.", True)
    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    assert active is None



def test_reminder_cancel_confirm_with_malformed_payload_is_safe() -> None:
    reminder_actions = _ReminderActions(outcome_kind="accepted", outcome_reason="booking_canceled", booking_id="b1")
    router, runtime = _build_router(
        reminder_actions=reminder_actions,
        booking_flow=_BookingFlowStub(status="confirmed"),
    )
    callback = _Callback("remc:confirm:rem_1", user_id=1001, message_id=991)

    asyncio.run(_handler(router, "reminder_cancel_confirm_callback")(callback))

    assert reminder_actions.calls == []
    assert callback.message.reply_markup_cleared == 0
    assert callback.message.answers == []
    assert callback.answered[-1] == ("This reminder action is invalid.", True)
    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    assert active is None


def test_reminder_cancel_confirm_stale_outcome_is_safe() -> None:
    reminder_actions = _ReminderActions(outcome_kind="stale", outcome_reason="reminder_acknowledged", booking_id="b1")
    router, runtime = _build_router(
        reminder_actions=reminder_actions,
        booking_flow=_BookingFlowStub(status="confirmed"),
    )
    callback = _Callback("remc:confirm:rem_1:777", user_id=1001, message_id=991)

    asyncio.run(_handler(router, "reminder_cancel_confirm_callback")(callback))

    assert reminder_actions.calls == [{"reminder_id": "rem_1", "action": "cancel", "provider_message_id": "777"}]
    assert callback.message.reply_markup_cleared == 0
    assert callback.message.answers == []
    assert callback.answered[-1] == ("This reminder action is no longer active.", True)
    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    assert active is None


def test_pat_a3_1_no_migration_directories_present() -> None:
    assert not Path("migrations").exists()
    assert not Path("alembic").exists()
