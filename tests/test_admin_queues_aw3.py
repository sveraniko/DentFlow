from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.application.admin.workdesk import ConfirmationQueueRow, RescheduleQueueRow, WaitlistQueueRow
from app.common.i18n import I18nService
from app.domain.access_identity.models import (
    ActorIdentity,
    ActorStatus,
    ActorType,
    ClinicRoleAssignment,
    RoleCode,
    StaffMember,
    StaffStatus,
    TelegramBinding,
)
from app.interfaces.bots.admin.router import make_router
from app.interfaces.cards import CardCallback, CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
from app.interfaces.cards.models import CardAction, CardMode, CardProfile, EntityType, SourceContext
from app.interfaces.cards.runtime_state import InMemoryRedis


class _Message:
    def __init__(self, text: str, user_id: int = 501) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))


class _CallbackMessage:
    def __init__(self) -> None:
        self.edits: list[tuple[str, object | None]] = []

    async def edit_text(self, text: str, reply_markup=None) -> None:
        self.edits.append((text, reply_markup))


class _Callback:
    def __init__(self, data: str, user_id: int = 501) -> None:
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _CallbackMessage()
        self.answers: list[str] = []

    async def answer(self, text: str, show_alert: bool = False) -> None:
        self.answers.append(text)


class _Reference:
    def get_clinic(self, clinic_id: str):
        return SimpleNamespace(default_locale="en")

    def get_service(self, clinic_id: str, service_id: str):
        return None


class _BookingFlow:
    def __init__(self) -> None:
        self.reads = self
        self.orchestration = SimpleNamespace(
            confirm_booking=self._ok,
            request_booking_reschedule=self._ok,
            cancel_booking=self._ok,
            booking_state_service=SimpleNamespace(transition_booking=self._ok),
        )

    async def _ok(self, **kwargs):
        return SimpleNamespace(kind="success", entity=self._booking())

    async def get_booking(self, booking_id: str):
        return self._booking(status="reschedule_requested" if booking_id == "b2" else "pending_confirmation")

    def build_booking_snapshot(self, **kwargs):
        booking = kwargs["booking"]
        return SimpleNamespace(
            doctor_label="Dr A",
            service_label="Consultation",
            branch_label="Main",
            next_step_note_key="patient.booking.card.next.default",
            booking_id=booking.booking_id,
            state_token=booking.booking_id,
            role_variant="admin",
            scheduled_start_at=datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
            timezone_name="UTC",
            patient_label="p1",
            status=booking.status,
            source_channel="telegram",
            patient_contact=None,
            compact_flags=(),
            reminder_summary=None,
            reschedule_summary=None,
            recommendation_summary=None,
            care_order_summary=None,
            chart_summary_entry=None,
        )

    def _booking(self, status: str = "pending_confirmation"):
        return SimpleNamespace(
            booking_id="b1" if status == "pending_confirmation" else "b2",
            patient_id="p1",
            doctor_id="d1",
            service_id="s1",
            clinic_id="c1",
            branch_id="br1",
            status=status,
            source_channel="telegram",
            scheduled_start_at=datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
        )


class _Workdesk:
    async def get_confirmation_queue(self, **kwargs):
        return [
            ConfirmationQueueRow(
                clinic_id="c1",
                branch_id="br1",
                booking_id="b1",
                patient_id="p1",
                doctor_id="d1",
                local_service_date=date(2026, 4, 19),
                local_service_time="09:00",
                booking_status="pending_confirmation",
                confirmation_signal="pending",
                reminder_state_summary="no_response",
                no_response_flag=True,
                patient_display_name="Jane Roe",
                doctor_display_name="Dr A",
                service_label="svc.consult",
                branch_label="Main",
                updated_at=datetime.now(timezone.utc),
            )
        ]

    async def get_reschedule_queue(self, **kwargs):
        return [
            RescheduleQueueRow(
                clinic_id="c1",
                branch_id="br1",
                booking_id="b2",
                patient_id="p2",
                doctor_id="d2",
                local_service_date=date(2026, 4, 19),
                local_service_time="10:00",
                booking_status="reschedule_requested",
                reschedule_context="patient_requested",
                patient_display_name="John Roe",
                doctor_display_name="Dr B",
                service_label="svc.clean",
                branch_label="Main",
                updated_at=datetime.now(timezone.utc),
            )
        ]

    async def get_waitlist_queue(self, **kwargs):
        return [
            WaitlistQueueRow(
                clinic_id="c1",
                branch_id="br1",
                waitlist_entry_id="w1",
                patient_id="p9",
                preferred_doctor_id="d1",
                preferred_service_id="s1",
                preferred_time_window_summary="morning",
                status="active",
                patient_display_name="Wait Person",
                doctor_display_name="Dr A",
                service_label="Consultation",
                updated_at=datetime.now(timezone.utc),
            )
        ]


def _access() -> AccessResolver:
    repo = InMemoryAccessRepository()
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    repo.upsert_actor_identity(ActorIdentity(actor_id="a1", actor_type=ActorType.STAFF, display_name="Admin", status=ActorStatus.ACTIVE, locale="en"))
    repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id="t1", actor_id="a1", telegram_user_id=501))
    repo.upsert_staff_member(StaffMember(staff_id="s1", actor_id="a1", clinic_id="c1", full_name="Admin", display_name="Admin", staff_status=StaffStatus.ACTIVE))
    repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id="r1", staff_id="s1", clinic_id="c1", role_code=RoleCode.ADMIN, granted_at=now))
    return AccessResolver(repo)


def _router():
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    return make_router(
        i18n,
        _access(),
        _Reference(),
        _BookingFlow(),
        search_service=SimpleNamespace(),
        stt_service=SimpleNamespace(),
        voice_mode_store=SimpleNamespace(),
        care_commerce_service=None,
        admin_workdesk=_Workdesk(),
        default_locale="en",
        max_voice_duration_sec=60,
        max_voice_file_size_bytes=1024,
        voice_mode_ttl_sec=30,
        card_runtime=runtime,
        card_callback_codec=codec,
    ), codec


def _handler(router, name: str, kind: str = "message"):
    handlers = router.message.handlers if kind == "message" else router.callback_query.handlers
    for h in handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(name)


def test_admin_confirmations_queue_render_and_booking_open_context() -> None:
    router, codec = _router()
    msg = _Message("/admin_confirmations")
    asyncio.run(_handler(router, "admin_confirmations")(msg))
    text, keyboard = msg.answers[-1]
    assert "Confirmations Queue" in text
    assert "No response" in text
    cb = keyboard.inline_keyboard[1][0].callback_data
    decoded = asyncio.run(codec.decode(cb))
    assert decoded.source_context == SourceContext.ADMIN_CONFIRMATIONS


def test_admin_reschedules_queue_render_open_and_back_preserves_queue() -> None:
    router, codec = _router()
    msg = _Message("/admin_reschedules")
    asyncio.run(_handler(router, "admin_reschedules")(msg))
    text, keyboard = msg.answers[-1]
    assert "Reschedules Queue" in text
    cb_open = keyboard.inline_keyboard[0][0].callback_data
    decoded = asyncio.run(codec.decode(cb_open))
    assert decoded.source_context == SourceContext.ADMIN_RESCHEDULES

    callback_open = _Callback(cb_open)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(callback_open))
    assert callback_open.message.edits
    _, opened_markup = callback_open.message.edits[-1]
    assert opened_markup is not None
    assert any(
        button.callback_data.startswith("c2|")
        for row in opened_markup.inline_keyboard
        for button in row
    )

    cb_back = asyncio.run(
        codec.encode(
            CardCallback(
                profile=CardProfile.BOOKING,
                entity_type=EntityType.BOOKING,
                entity_id="b2",
                action=CardAction.BACK,
                mode=CardMode.EXPANDED,
                source_context=SourceContext.ADMIN_RESCHEDULES,
                source_ref=decoded.source_ref,
                page_or_index=decoded.page_or_index,
                state_token=decoded.state_token,
            )
        )
    )
    callback_back = _Callback(cb_back)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(callback_back))
    assert any("Reschedules Queue" in t for t, _ in callback_back.message.edits)


def test_admin_waitlist_queue_open_close_and_stale_safe() -> None:
    router, _ = _router()
    msg = _Message("/admin_waitlist")
    asyncio.run(_handler(router, "admin_waitlist")(msg))
    text, keyboard = msg.answers[-1]
    assert "Waitlist Queue" in text

    open_cb = keyboard.inline_keyboard[1][0].callback_data
    callback_open = _Callback(open_cb)
    asyncio.run(_handler(router, "admin_waitlist_callback", kind="callback")(callback_open))
    assert any("Waitlist w1" in t for t, _ in callback_open.message.edits)
    assert callback_open.message.edits[-1][1] is not None

    close_cb = keyboard.inline_keyboard[2][0].callback_data
    callback_close = _Callback(close_cb)
    asyncio.run(_handler(router, "admin_waitlist_callback", kind="callback")(callback_close))
    assert any("manual closure" in t for t, _ in callback_close.message.edits)
    assert callback_close.message.edits[-1][1] is not None

    stale = _Callback("aw3w:open:w1:stale")
    asyncio.run(_handler(router, "admin_waitlist_callback", kind="callback")(stale))
    assert any("outdated" in x for x in stale.answers)


def test_admin_confirmations_queue_stale_callback_is_safe() -> None:
    router, _ = _router()
    callback = _Callback("aw3:confirmations:focus:stale")
    asyncio.run(_handler(router, "admin_aw3_queue_callback", kind="callback")(callback))
    assert any("outdated" in x for x in callback.answers)
