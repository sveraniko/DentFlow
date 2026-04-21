from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.booking.orchestration_outcomes import InvalidStateOutcome, OrchestrationSuccess
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.application.communication.actions import ReminderActionService
from app.application.communication.delivery import render_booking_reminder_message
from app.common.i18n import I18nService
from app.domain.booking import Booking
from app.domain.clinic_reference.models import Branch, Clinic, Doctor, Service
from app.domain.communication import ReminderJob
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore, PanelFamily
from app.interfaces.cards.runtime_state import InMemoryRedis


class _MemoryTx(AbstractAsyncContextManager):
    def __init__(self, repo: "_TxRepository") -> None:
        self.repo = repo
        self._snapshot_reminders: dict[str, ReminderJob] = {}
        self._snapshot_bookings: dict[str, Booking] = {}

    async def __aenter__(self):
        self._snapshot_reminders = dict(self.repo.reminders)
        self._snapshot_bookings = dict(self.repo.bookings)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.repo.reminders = self._snapshot_reminders
            self.repo.bookings = self._snapshot_bookings
        return False

    async def get_reminder_for_update_in_transaction(self, *, reminder_id: str) -> ReminderJob | None:
        return self.repo.reminders.get(reminder_id)

    async def mark_reminder_acknowledged_in_transaction(self, *, reminder_id: str, acknowledged_at: datetime) -> bool:
        current = self.repo.reminders.get(reminder_id)
        if current is None or current.status != "sent":
            return False
        self.repo.reminders[reminder_id] = ReminderJob(
            **{**asdict(current), "status": "acknowledged", "acknowledged_at": acknowledged_at, "updated_at": acknowledged_at}
        )
        return True

    async def has_sent_delivery_for_provider_message_in_transaction(self, *, reminder_id: str, provider_message_id: str) -> bool:
        return provider_message_id == self.repo.valid_message_id and reminder_id in self.repo.reminders

    async def get_booking_for_update(self, booking_id: str) -> Booking | None:
        return self.repo.bookings.get(booking_id)


class _TxRepository:
    def __init__(self, reminders: list[ReminderJob], bookings: list[Booking], *, valid_message_id: str = "777") -> None:
        self.reminders = {row.reminder_id: row for row in reminders}
        self.bookings = {row.booking_id: row for row in bookings}
        self.valid_message_id = valid_message_id

    def transaction(self) -> _MemoryTx:
        return _MemoryTx(self)


class _TrackingOrchestration:
    def __init__(self) -> None:
        self.confirm_calls = 0
        self.cancel_calls = 0
        self.reschedule_calls = 0

    async def confirm_booking_in_transaction(self, *, tx: _MemoryTx, booking_id: str, reason_code: str | None = None):
        booking = await tx.get_booking_for_update(booking_id)
        if booking is None or booking.status != "pending_confirmation":
            return InvalidStateOutcome(kind="invalid_state", reason="booking cannot transition to confirmed")
        self.confirm_calls += 1
        tx.repo.bookings[booking_id] = Booking(**{**asdict(booking), "status": "confirmed", "confirmed_at": datetime.now(timezone.utc)})
        return OrchestrationSuccess(kind="success", entity=tx.repo.bookings[booking_id])

    async def request_booking_reschedule_in_transaction(self, *, tx: _MemoryTx, booking_id: str, reason_code: str | None = None):
        self.reschedule_calls += 1
        return InvalidStateOutcome(kind="invalid_state", reason="unused in this suite")

    async def cancel_booking_in_transaction(self, *, tx: _MemoryTx, booking_id: str, reason_code: str | None = None):
        self.cancel_calls += 1
        return InvalidStateOutcome(kind="invalid_state", reason="unused in this suite")


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


class _ReminderRepository:
    def __init__(self) -> None:
        now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
        self._reminder = ReminderJob(
            reminder_id="rem_1",
            clinic_id="clinic_main",
            patient_id="pat_1",
            booking_id="b1",
            care_order_id=None,
            recommendation_id=None,
            reminder_type="booking_previsit",
            channel="telegram",
            status="sent",
            scheduled_for=now,
            payload_key="booking.reminder.24h",
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


class _ReminderActions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object | None]] = []
        self.repository = _ReminderRepository()

    async def handle_action(self, **kwargs):  # noqa: ANN003
        self.calls.append(kwargs)
        return SimpleNamespace(kind="accepted", reason="acknowledged", booking_id="b1")


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
            status="pending_confirmation",
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

    async def start_patient_reschedule_session(self, **kwargs):  # noqa: ANN003
        return SimpleNamespace(kind="booking_missing", booking=None, booking_session=None)

    def build_booking_snapshot(self, **kwargs):  # noqa: ANN003
        from app.interfaces.cards import BookingRuntimeSnapshot

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
            next_step_note_key="booking.next_step.pending_confirmation",
            compact_flags=(),
            reminder_summary=None,
            reschedule_summary=None,
        )


def _booking(*, status: str = "pending_confirmation") -> Booking:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    return Booking(
        booking_id="b1",
        clinic_id="clinic_main",
        branch_id="branch_1",
        patient_id="pat_1",
        doctor_id="doctor_1",
        service_id="service_consult",
        slot_id="slot_1",
        booking_mode="patient_bot",
        source_channel="telegram",
        scheduled_start_at=now + timedelta(days=1),
        scheduled_end_at=now + timedelta(days=1, minutes=30),
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


def _reminder(*, reminder_id: str = "rem_1", reminder_type: str, status: str = "sent", booking_id: str | None = "b1") -> ReminderJob:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=timezone.utc)
    return ReminderJob(
        reminder_id=reminder_id,
        clinic_id="clinic_main",
        patient_id="pat_1",
        booking_id=booking_id,
        care_order_id=None,
        recommendation_id=None,
        reminder_type=reminder_type,
        channel="telegram",
        status=status,
        scheduled_for=now,
        payload_key="booking.reminder.24h",
        locale_at_send_time="en",
        planning_group="g1",
        supersedes_reminder_id=None,
        created_at=now,
        updated_at=now,
    )


def _service(repo: _TxRepository, orchestration: _TrackingOrchestration | None = None) -> ReminderActionService:
    return ReminderActionService(repository=repo, transaction_repository=repo, booking_orchestration=orchestration or _TrackingOrchestration())


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


def _build_router():
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
    return router, runtime


def test_pat_a6_ack_action_availability_by_reminder_type() -> None:
    booking = _booking(status="pending_confirmation")
    cases = {
        "booking_confirmation": ["confirm", "reschedule", "cancel"],
        "booking_no_response_followup": ["confirm", "reschedule", "cancel"],
        "booking_previsit": ["ack"],
        "booking_day_of": ["ack"],
        "booking_next_visit_recall": ["ack"],
    }

    for reminder_type, expected_actions in cases.items():
        rendered = render_booking_reminder_message(reminder=_reminder(reminder_type=reminder_type), booking=booking)
        assert [item.action for item in rendered.actions] == expected_actions


def test_pat_a6_ack_is_distinct_from_confirm_and_non_destructive() -> None:
    ack_repo = _TxRepository([_reminder(reminder_type="booking_previsit")], [_booking(status="pending_confirmation")])
    ack_orchestration = _TrackingOrchestration()
    ack_service = _service(ack_repo, ack_orchestration)

    ack_outcome = asyncio.run(ack_service.handle_action(reminder_id="rem_1", action="ack", provider_message_id="777"))

    assert ack_outcome.kind == "accepted"
    assert ack_outcome.reason == "acknowledged"
    assert ack_repo.reminders["rem_1"].status == "acknowledged"
    assert ack_repo.bookings["b1"].status == "pending_confirmation"
    assert ack_orchestration.confirm_calls == 0
    assert ack_orchestration.cancel_calls == 0
    assert ack_orchestration.reschedule_calls == 0

    confirm_repo = _TxRepository([_reminder(reminder_type="booking_confirmation")], [_booking(status="pending_confirmation")])
    confirm_orchestration = _TrackingOrchestration()
    confirm_service = _service(confirm_repo, confirm_orchestration)

    confirm_outcome = asyncio.run(confirm_service.handle_action(reminder_id="rem_1", action="confirm", provider_message_id="777"))

    assert confirm_outcome.kind == "accepted"
    assert confirm_outcome.reason == "booking_confirmed"
    assert confirm_repo.reminders["rem_1"].status == "acknowledged"
    assert confirm_repo.bookings["b1"].status == "confirmed"
    assert confirm_orchestration.confirm_calls == 1


def test_pat_a6_ack_duplicate_mismatch_and_terminal_safety() -> None:
    duplicate_repo = _TxRepository([_reminder(reminder_type="booking_previsit")], [_booking(status="confirmed")])
    duplicate_service = _service(duplicate_repo)

    first = asyncio.run(duplicate_service.handle_action(reminder_id="rem_1", action="ack", provider_message_id="777"))
    second = asyncio.run(duplicate_service.handle_action(reminder_id="rem_1", action="ack", provider_message_id="777"))

    assert first.kind == "accepted"
    assert second.kind == "stale"
    assert duplicate_repo.bookings["b1"].status == "confirmed"

    mismatch_repo = _TxRepository([_reminder(reminder_type="booking_previsit")], [_booking(status="confirmed")])
    mismatch_service = _service(mismatch_repo)
    mismatch = asyncio.run(mismatch_service.handle_action(reminder_id="rem_1", action="ack", provider_message_id="mismatch"))
    assert mismatch.kind == "invalid"
    assert mismatch.reason == "message_mismatch"
    assert mismatch_repo.reminders["rem_1"].status == "sent"

    stale_repo = _TxRepository([_reminder(reminder_type="booking_previsit", status="failed")], [_booking(status="confirmed")])
    stale_service = _service(stale_repo)
    stale = asyncio.run(stale_service.handle_action(reminder_id="rem_1", action="ack", provider_message_id="777"))
    assert stale.kind == "stale"
    assert stale_repo.bookings["b1"].status == "confirmed"


def test_pat_a6_ack_has_no_special_future_suppression_by_default() -> None:
    reminders = [
        _reminder(reminder_id="rem_ack", reminder_type="booking_previsit", status="sent"),
        _reminder(reminder_id="rem_future", reminder_type="booking_day_of", status="scheduled"),
    ]
    repo = _TxRepository(reminders, [_booking(status="confirmed")])
    service = _service(repo)

    outcome = asyncio.run(service.handle_action(reminder_id="rem_ack", action="ack", provider_message_id="777"))

    assert outcome.kind == "accepted"
    assert repo.reminders["rem_ack"].status == "acknowledged"
    assert repo.reminders["rem_future"].status == "scheduled"


def test_pat_a6_ack_handoff_goes_to_canonical_booking_panel() -> None:
    router, runtime = _build_router()
    callback = _Callback("rem:ack:rem_1", user_id=1001)

    asyncio.run(_handler(router, "reminder_action_callback")(callback))

    assert callback.message.reply_markup_cleared == 1
    sent_text, sent_keyboard = callback.message.answers[-1]
    assert "Got it, thanks." in sent_text
    assert "Consultation" in sent_text
    assert sent_keyboard is not None
    state = asyncio.run(runtime.resolve_actor_session_state(scope="patient_flow", actor_id=1001))
    assert state["booking_mode"] == "existing_booking_control"
    assert state["booking_session_id"] == "sess_rem_1"
    active = asyncio.run(runtime.resolve_active_panel(actor_id=1001, panel_family=PanelFamily.BOOKING_DETAIL))
    assert active is not None
