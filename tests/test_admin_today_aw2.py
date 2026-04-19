from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.application.admin.workdesk import OpsIssueQueueRow, TodayScheduleRow
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

    def list_branches(self, clinic_id: str):
        return [SimpleNamespace(branch_id="br1"), SimpleNamespace(branch_id="br2")]

    def list_doctors(self, clinic_id: str):
        return [SimpleNamespace(doctor_id="d1"), SimpleNamespace(doctor_id="d2")]

    def get_service(self, clinic_id: str, service_id: str):
        return SimpleNamespace(code="CONS", title_key="svc.consult")


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
        return self._booking()

    def build_booking_snapshot(self, **kwargs):
        return SimpleNamespace(
            doctor_label="Dr A",
            service_label="CONS (svc.consult)",
            branch_label="Main",
            next_step_note_key="patient.booking.card.next.default",
            booking_id="b1",
            state_token="b1",
            role_variant="admin",
            scheduled_start_at=datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
            timezone_name="UTC",
            patient_label="p1",
            status="pending_confirmation",
            source_channel="telegram",
            patient_contact=None,
            compact_flags=(),
            reminder_summary=None,
            reschedule_summary=None,
            recommendation_summary=None,
            care_order_summary=None,
            chart_summary_entry=None,
        )

    def _booking(self):
        return SimpleNamespace(
            booking_id="b1",
            patient_id="p1",
            doctor_id="d1",
            service_id="s1",
            clinic_id="c1",
            branch_id="br1",
            status="pending_confirmation",
            source_channel="telegram",
            scheduled_start_at=datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
        )


class _Workdesk:
    async def get_today_schedule(self, **kwargs):
        return [
            TodayScheduleRow(
                clinic_id="c1",
                branch_id="br1",
                booking_id="b1",
                patient_id="p1",
                doctor_id="d1",
                service_id="s1",
                local_service_date=date(2026, 4, 19),
                local_service_time="09:00",
                scheduled_start_at_utc=datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
                scheduled_end_at_utc=None,
                booking_status="pending_confirmation",
                confirmation_state="pending",
                checkin_state="not_arrived",
                no_show_flag=False,
                reschedule_requested_flag=False,
                waitlist_linked_flag=False,
                recommendation_linked_flag=False,
                care_order_linked_flag=False,
                patient_display_name="Jane Roe",
                doctor_display_name="Dr A",
                service_label="svc.consult",
                branch_label="Main",
                compact_flags_summary="pending",
                updated_at=datetime.now(timezone.utc),
            )
        ]

    async def get_ops_issue_queue(self, **kwargs):
        return [
            OpsIssueQueueRow(
                clinic_id="c1",
                branch_id="br1",
                issue_type="confirmation_no_response",
                issue_ref_id="b1",
                issue_status="open",
                severity="medium",
                patient_id="p1",
                booking_id="b1",
                care_order_id=None,
                local_related_date=date(2026, 4, 19),
                local_related_time="08:00",
                summary_text="Confirmation reminder sent but no patient response yet",
                patient_display_name="Jane Roe",
                updated_at=datetime.now(timezone.utc),
            )
        ]


def _access(role: RoleCode) -> AccessResolver:
    repo = InMemoryAccessRepository()
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    repo.upsert_actor_identity(ActorIdentity(actor_id="a1", actor_type=ActorType.STAFF, display_name="Admin", status=ActorStatus.ACTIVE, locale="en"))
    repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id="t1", actor_id="a1", telegram_user_id=501))
    repo.upsert_staff_member(StaffMember(staff_id="s1", actor_id="a1", clinic_id="c1", full_name="Admin", display_name="Admin", staff_status=StaffStatus.ACTIVE))
    repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id="r1", staff_id="s1", clinic_id="c1", role_code=role, granted_at=now))
    return AccessResolver(repo)


def _router(role: RoleCode):
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    return make_router(
        i18n,
        _access(role),
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


def test_admin_today_is_admin_only_and_localized_rows() -> None:
    router, _ = _router(RoleCode.ADMIN)
    msg = _Message("/admin_today")
    asyncio.run(_handler(router, "admin_today")(msg))
    text, _ = msg.answers[-1]
    assert "Today Workdesk" in text
    assert "No response" in text
    assert "svc.consult" not in text

    denied_router, _ = _router(RoleCode.DOCTOR)
    denied = _Message("/admin_today")
    asyncio.run(_handler(denied_router, "admin_today")(denied))
    assert any("Access denied" in t for t, _ in denied.answers)


def test_admin_today_open_uses_booking_card_admin_today_context() -> None:
    router, codec = _router(RoleCode.ADMIN)
    msg = _Message("/admin_today")
    asyncio.run(_handler(router, "admin_today")(msg))
    _, keyboard = msg.answers[-1]
    callback_data = keyboard.inline_keyboard[1][0].callback_data
    decoded = asyncio.run(codec.decode(callback_data))
    assert decoded.source_context == SourceContext.ADMIN_TODAY


def test_admin_today_stale_filter_callback_fails_safe() -> None:
    router, _ = _router(RoleCode.ADMIN)
    callback = _Callback("aw2:filter:status:stale")
    asyncio.run(_handler(router, "admin_today_callback", kind="callback")(callback))
    assert any("outdated" in x for x in callback.answers)


def test_admin_today_back_from_booking_card_returns_workdesk() -> None:
    router, codec = _router(RoleCode.ADMIN)
    msg = _Message("/admin_today")
    asyncio.run(_handler(router, "admin_today")(msg))
    cb_open = msg.answers[-1][1].inline_keyboard[1][0].callback_data
    decoded_open = asyncio.run(codec.decode(cb_open))
    callback_open = _Callback(cb_open)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(callback_open))
    back_payload = CardCallback(
        profile=CardProfile.BOOKING,
        entity_type=EntityType.BOOKING,
        entity_id="b1",
        action=CardAction.BACK,
        mode=CardMode.EXPANDED,
        source_context=SourceContext.ADMIN_TODAY,
        source_ref=decoded_open.source_ref,
        page_or_index=decoded_open.page_or_index,
        state_token=decoded_open.state_token,
    )
    cb_back = asyncio.run(codec.encode(back_payload))
    callback_back = _Callback(cb_back)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(callback_back))
    assert any("Today Workdesk" in text for text, _ in callback_back.message.edits)
