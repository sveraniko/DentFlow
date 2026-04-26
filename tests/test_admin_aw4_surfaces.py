from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.care_catalog_sync.models import CatalogImportResult, CatalogIssue
from app.application.access import AccessResolver, InMemoryAccessRepository
from app.application.admin.workdesk import CarePickupQueueRow, OpsIssueQueueRow, WaitlistQueueRow
from app.application.booking.orchestration_outcomes import OrchestrationSuccess
from app.application.search.models import PatientSearchResponse, PatientSearchResult, SearchResultOrigin
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

    def get_branch(self, clinic_id: str, branch_id: str):
        return SimpleNamespace(display_name="Main")


class _Search:
    async def search_patients(self, query):
        row = PatientSearchResult(
            patient_id="p1",
            clinic_id=query.clinic_id,
            display_name="Jane Roe",
            patient_number="1001",
            primary_phone_normalized="+15551234567",
            active_flags_summary="vip",
            status="active",
            origin=SearchResultOrigin.POSTGRES_STRICT,
        )
        return PatientSearchResponse(exact_matches=[row], suggestions=[])


class _BookingFlow:
    def __init__(self) -> None:
        self._sessions: dict[str, SimpleNamespace] = {}
        self._issue_states: dict[tuple[str, str], str] = {}
        self._bookings_by_patient: dict[str, list[SimpleNamespace]] = {"p1": [self._booking()]}
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
        return self._booking(booking_id=booking_id)

    async def list_bookings_by_patient(self, *, patient_id: str):
        return list(self._bookings_by_patient.get(patient_id, []))

    async def start_admin_reschedule_session(self, *, clinic_id: str, telegram_user_id: int, booking_id: str):
        session_id = f"sess_{booking_id}"
        self._sessions[session_id] = SimpleNamespace(
            booking_session_id=session_id,
            clinic_id=clinic_id,
            telegram_user_id=telegram_user_id,
            route_type="reschedule_booking_control",
            selected_slot_id=None,
        )
        return SimpleNamespace(kind="ready", booking_session=self._sessions[session_id])

    async def validate_active_session_callback(self, **kwargs):
        return kwargs.get("callback_session_id") in self._sessions

    async def list_slots_for_session(self, *, booking_session_id: str):
        return [SimpleNamespace(slot_id="slot_ok", start_at=datetime(2026, 4, 21, 11, 0, tzinfo=timezone.utc))]

    async def select_slot(self, *, booking_session_id: str, slot_id: str):
        self._sessions[booking_session_id].selected_slot_id = slot_id
        return OrchestrationSuccess(kind="success", entity=self._sessions[booking_session_id])

    async def get_booking_session(self, *, booking_session_id: str):
        return self._sessions.get(booking_session_id)

    async def get_availability_slot(self, *, slot_id: str):
        return SimpleNamespace(slot_id=slot_id, start_at=datetime(2026, 4, 21, 11, 0, tzinfo=timezone.utc))

    async def complete_admin_reschedule_from_session(self, **kwargs):
        return OrchestrationSuccess(kind="success", entity=self._booking(status="confirmed"))

    async def get_issue_escalation(self, *, clinic_id: str, issue_type: str, issue_ref_id: str):
        status = self._issue_states.get((issue_type, issue_ref_id))
        if status is None:
            return None
        return SimpleNamespace(status=status)

    async def take_issue_escalation(self, *, issue_type: str, issue_ref_id: str, **kwargs):
        self._issue_states[(issue_type, issue_ref_id)] = "in_progress"
        return SimpleNamespace(status="in_progress")

    async def resolve_issue_escalation(self, *, issue_type: str, issue_ref_id: str, **kwargs):
        if self._issue_states.get((issue_type, issue_ref_id)) != "in_progress":
            return None
        self._issue_states[(issue_type, issue_ref_id)] = "resolved"
        return SimpleNamespace(status="resolved")

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
            patient_label="Jane Roe",
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

    def _booking(self, booking_id: str = "b1", status: str = "pending_confirmation"):
        return SimpleNamespace(
            booking_id=booking_id,
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
    async def get_today_schedule(self, **kwargs):
        return []

    async def get_waitlist_queue(self, **kwargs):
        return [
            WaitlistQueueRow(
                clinic_id="c1",
                branch_id="br1",
                waitlist_entry_id="w1",
                patient_id="p1",
                preferred_doctor_id="d1",
                preferred_service_id="s1",
                preferred_time_window_summary="morning",
                status="active",
                patient_display_name="Jane Roe",
                doctor_display_name="Dr A",
                service_label="admin.today.title",
                updated_at=datetime.now(timezone.utc),
            )
        ]

    async def get_care_pickup_queue(self, **kwargs):
        return [
            CarePickupQueueRow(
                clinic_id="c1",
                branch_id="br1",
                care_order_id="co1",
                patient_id="p1",
                pickup_status="ready_for_pickup",
                local_ready_date=date(2026, 4, 19),
                local_ready_time="14:00",
                patient_display_name="Jane Roe",
                branch_label="Main",
                compact_item_summary="Kit",
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
                severity="high",
                patient_id="p1",
                booking_id="b1",
                care_order_id=None,
                local_related_date=date(2026, 4, 19),
                local_related_time="08:00",
                summary_text="raw",
                patient_display_name="Jane Roe",
                updated_at=datetime.now(timezone.utc),
            ),
            OpsIssueQueueRow(
                clinic_id="c1",
                branch_id="br1",
                issue_type="reminder_failed",
                issue_ref_id="r_fail_1",
                issue_status="open",
                severity="medium",
                patient_id="p1",
                booking_id="b1",
                care_order_id=None,
                local_related_date=date(2026, 4, 19),
                local_related_time="10:00",
                summary_text="raw",
                patient_display_name="Jane Roe",
                updated_at=datetime.now(timezone.utc),
            ),
            OpsIssueQueueRow(
                clinic_id="c1",
                branch_id="br1",
                issue_type="reminder_failed",
                issue_ref_id="r_fail_2",
                issue_status="open",
                severity="medium",
                patient_id="p1",
                booking_id=None,
                care_order_id=None,
                local_related_date=date(2026, 4, 19),
                local_related_time="10:00",
                summary_text="raw",
                patient_display_name="Jane Roe",
                updated_at=datetime.now(timezone.utc),
            ),
            OpsIssueQueueRow(
                clinic_id="c1",
                branch_id="br1",
                issue_type="unknown_issue",
                issue_ref_id="unknown_1",
                issue_status="open",
                severity="low",
                patient_id="p1",
                booking_id="b1",
                care_order_id=None,
                local_related_date=date(2026, 4, 19),
                local_related_time="11:30",
                summary_text="raw",
                patient_display_name="Jane Roe",
                updated_at=datetime.now(timezone.utc),
            ),
        ]


class _CareService:
    async def get_order(self, care_order_id: str):
        return SimpleNamespace(care_order_id=care_order_id, patient_id="p1", status="ready_for_pickup", pickup_branch_id="br1")

    async def apply_admin_order_action(self, *, care_order_id: str, action: str, **kwargs):
        return SimpleNamespace(care_order_id=care_order_id, status="fulfilled")


class _ReminderRecovery:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._seen: set[str] = set()

    async def retry_failed_reminder(self, *, reminder_id: str, now):  # noqa: ANN001
        self.calls.append(reminder_id)
        if reminder_id in self._seen:
            return SimpleNamespace(outcome="already_pending", reminder_id=f"rem_mr_{reminder_id}")
        self._seen.add(reminder_id)
        return SimpleNamespace(outcome="scheduled", reminder_id=f"rem_mr_{reminder_id}")


class _CatalogSyncService:
    async def sync_google_sheet(self, *, clinic_id: str, sheet_url_or_id: str, tmp_path: str):
        result = CatalogImportResult(source="google_sheets")
        result.tabs_processed.extend(["product_i18n", "products"])
        stats_products = result.ensure_tab("products")
        stats_products.added = 2
        stats_i18n = result.ensure_tab("product_i18n")
        stats_i18n.updated = 1
        result.warnings.append(CatalogIssue(level="warning", tab="products", row_number=3, code="trimmed_whitespace", message="trimmed"))
        return result

    async def import_xlsx(self, *, clinic_id: str, path: str, source: str = "xlsx"):
        result = CatalogImportResult(source=source)
        result.fatal_errors.append(CatalogIssue(level="fatal", tab="workbook", row_number=None, code="missing_tab", message="missing products"))
        return result


class _CatalogSyncServiceLargeIssues(_CatalogSyncService):
    async def sync_google_sheet(self, *, clinic_id: str, sheet_url_or_id: str, tmp_path: str):
        result = CatalogImportResult(source="google_sheets")
        for i in range(1, 5):
            result.warnings.append(
                CatalogIssue(level="warning", tab="products", row_number=i, code=f"w_{i}", message=f"warning_{i}")
            )
        for i in range(1, 5):
            result.validation_errors.append(
                CatalogIssue(level="error", tab="products", row_number=10 + i, code=f"e_{i}", message=f"error_{i}")
            )
        for i in range(1, 5):
            result.fatal_errors.append(
                CatalogIssue(level="fatal", tab="workbook", row_number=None, code=f"f_{i}", message=f"fatal_{i}")
            )
        return result


class _CatalogSyncServiceRaisesSheets(_CatalogSyncService):
    async def sync_google_sheet(self, *, clinic_id: str, sheet_url_or_id: str, tmp_path: str):
        raise RuntimeError("boom sheets")


class _CatalogSyncServiceRaisesXlsx(_CatalogSyncService):
    async def import_xlsx(self, *, clinic_id: str, path: str, source: str = "xlsx"):
        raise RuntimeError("boom xlsx")


def _access() -> AccessResolver:
    repo = InMemoryAccessRepository()
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    repo.upsert_actor_identity(ActorIdentity(actor_id="a1", actor_type=ActorType.STAFF, display_name="Admin", status=ActorStatus.ACTIVE, locale="en"))
    repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id="t1", actor_id="a1", telegram_user_id=501))
    repo.upsert_staff_member(StaffMember(staff_id="s1", actor_id="a1", clinic_id="c1", full_name="Admin", display_name="Admin", staff_status=StaffStatus.ACTIVE))
    repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id="r1", staff_id="s1", clinic_id="c1", role_code=RoleCode.ADMIN, granted_at=now))
    return AccessResolver(repo)


def _router(catalog_sync_service=None):
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    recovery = _ReminderRecovery()
    booking_flow = _BookingFlow()
    return make_router(
        i18n,
        _access(),
        _Reference(),
        booking_flow,
        search_service=_Search(),
        stt_service=SimpleNamespace(),
        voice_mode_store=SimpleNamespace(),
        care_commerce_service=_CareService(),
        care_catalog_sync_service=catalog_sync_service or _CatalogSyncService(),
        admin_workdesk=_Workdesk(),
        reminder_recovery=recovery,
        default_locale="en",
        max_voice_duration_sec=60,
        max_voice_file_size_bytes=1024,
        voice_mode_ttl_sec=30,
        card_runtime=runtime,
        card_callback_codec=codec,
    ), codec, recovery


def _router_with_flow():
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    recovery = _ReminderRecovery()
    booking_flow = _BookingFlow()
    router = make_router(
        i18n,
        _access(),
        _Reference(),
        booking_flow,
        search_service=_Search(),
        stt_service=SimpleNamespace(),
        voice_mode_store=SimpleNamespace(),
        care_commerce_service=_CareService(),
        care_catalog_sync_service=_CatalogSyncService(),
        admin_workdesk=_Workdesk(),
        reminder_recovery=recovery,
        default_locale="en",
        max_voice_duration_sec=60,
        max_voice_file_size_bytes=1024,
        voice_mode_ttl_sec=30,
        card_runtime=runtime,
        card_callback_codec=codec,
    )
    return router, codec, recovery, booking_flow


def _booking_button(markup, *, text: str) -> str:
    return next(
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.text == text
    )


def _booking_action_callback(markup, codec: CardCallbackCodec, *, page_or_index: str) -> str:
    for row in markup.inline_keyboard:
        for button in row:
            cb = button.callback_data
            if not cb:
                continue
            decoded = asyncio.run(codec.decode(cb))
            if decoded.page_or_index == page_or_index:
                return cb
    raise AssertionError(page_or_index)


def _handler(router, name: str, kind: str = "message"):
    handlers = router.message.handlers if kind == "message" else router.callback_query.handlers
    for h in handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(name)


def test_admin_patients_search_and_open_card() -> None:
    router, codec, _ = _router()
    msg = _Message("/admin_patients jane")
    asyncio.run(_handler(router, "admin_patients")(msg))
    text, keyboard = msg.answers[-1]
    assert "Patients" in text
    cb = keyboard.inline_keyboard[0][0].callback_data
    decoded = asyncio.run(codec.decode(cb))
    assert decoded.source_context == SourceContext.ADMIN_PATIENTS


def test_admin_catalog_sync_usage_and_result_surface() -> None:
    router, _, _ = _router()
    usage = _Message("/admin_catalog_sync")
    asyncio.run(_handler(router, "admin_catalog_sync")(usage))
    assert "Usage: /admin_catalog_sync" in usage.answers[-1][0]

    ok_msg = _Message("/admin_catalog_sync sheets https://docs.google.com/spreadsheets/d/test/edit#gid=0")
    asyncio.run(_handler(router, "admin_catalog_sync")(ok_msg))
    response = ok_msg.answers[-1][0]
    assert "source=google_sheets ok=true" in response
    assert "tab=product_i18n added=0 updated=1 unchanged=0 skipped=0" in response
    assert "tab=products added=2 updated=0 unchanged=0 skipped=0" in response
    assert "warning [products:3] trimmed_whitespace: trimmed" in response


def test_admin_catalog_sync_xlsx_failure_summary() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_catalog_sync xlsx /tmp/catalog.xlsx")
    asyncio.run(_handler(router, "admin_catalog_sync")(msg))
    assert "source=xlsx ok=false" in msg.answers[-1][0]
    assert "fatal [workbook] missing_tab: missing products" in msg.answers[-1][0]


def test_admin_catalog_sync_result_is_bounded_and_includes_issue_counts() -> None:
    router, _, _ = _router(catalog_sync_service=_CatalogSyncServiceLargeIssues())
    msg = _Message("/admin_catalog_sync sheets sheet_id")
    asyncio.run(_handler(router, "admin_catalog_sync")(msg))
    response = msg.answers[-1][0]
    assert "issues warnings=4 validation_errors=4 fatal_errors=4" in response
    assert response.count("warning [") == 4
    assert response.count("error [") == 4
    assert response.count("fatal [") == 0
    assert "... and 4 more issues omitted" in response


def test_admin_catalog_sync_sheets_unexpected_exception_is_bounded() -> None:
    router, _, _ = _router(catalog_sync_service=_CatalogSyncServiceRaisesSheets())
    msg = _Message("/admin_catalog_sync sheets sheet_id")
    asyncio.run(_handler(router, "admin_catalog_sync")(msg))
    assert msg.answers[-1][0] == "Catalog sync failed unexpectedly. Please retry or check runtime logs."


def test_admin_catalog_sync_xlsx_unexpected_exception_is_bounded() -> None:
    router, _, _ = _router(catalog_sync_service=_CatalogSyncServiceRaisesXlsx())
    msg = _Message("/admin_catalog_sync xlsx /tmp/catalog.xlsx")
    asyncio.run(_handler(router, "admin_catalog_sync")(msg))
    assert msg.answers[-1][0] == "Catalog sync failed unexpectedly. Please retry or check runtime logs."


def test_admin_patients_open_active_booking_from_card() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_patients jane")
    asyncio.run(_handler(router, "admin_patients")(msg))
    _, keyboard = msg.answers[-1]
    cb = keyboard.inline_keyboard[0][0].callback_data
    callback = _Callback(cb)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(callback))
    assert any("Jane Roe" in row[0] for row in callback.message.edits)
    panel_text, panel_markup = callback.message.edits[-1]
    assert "Jane Roe" in panel_text
    assert panel_markup is not None
    bookings_cb = _booking_button(panel_markup, text="Open active booking")
    open_booking = _Callback(bookings_cb)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(open_booking))
    opened_text, opened_markup = open_booking.message.edits[-1]
    assert "Jane Roe" in opened_text
    assert "Consultation" in opened_text
    assert opened_markup is not None


def test_search_patient_is_harmonized_with_admin_patients_continuity() -> None:
    router, codec, _ = _router()
    admin_msg = _Message("/admin_patients jane")
    asyncio.run(_handler(router, "admin_patients")(admin_msg))
    admin_text, admin_keyboard = admin_msg.answers[-1]
    search_msg = _Message("/search_patient jane")
    asyncio.run(_handler(router, "search_patient")(search_msg))
    search_text, search_keyboard = search_msg.answers[-1]
    assert admin_text == search_text
    assert search_keyboard is not None
    search_open_cb = search_keyboard.inline_keyboard[0][0].callback_data
    decoded = asyncio.run(codec.decode(search_open_cb))
    assert decoded.source_context == SourceContext.ADMIN_PATIENTS
    assert decoded.source_ref == "search_patient:jane"

    callback = _Callback(search_open_cb)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(callback))
    panel_text, panel_markup = callback.message.edits[-1]
    assert "Jane Roe" in panel_text
    assert panel_markup is not None


def test_patient_origin_booking_back_and_actions_keep_patient_continuity() -> None:
    router, codec, _ = _router()
    msg = _Message("/search_patient jane")
    asyncio.run(_handler(router, "search_patient")(msg))
    open_patient_cb = msg.answers[-1][1].inline_keyboard[0][0].callback_data
    open_patient = _Callback(open_patient_cb)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(open_patient))
    patient_panel_text, patient_panel_markup = open_patient.message.edits[-1]
    assert "Jane Roe" in patient_panel_text
    assert patient_panel_markup is not None

    open_booking_cb = _booking_button(patient_panel_markup, text="Open active booking")
    open_booking = _Callback(open_booking_cb)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(open_booking))
    booking_text, booking_markup = open_booking.message.edits[-1]
    assert "Consultation" in booking_text
    assert booking_markup is not None

    for page_or_index in ("confirm", "cancel", "reschedule"):
        action_cb = _booking_action_callback(booking_markup, codec, page_or_index=page_or_index)
        decoded = asyncio.run(codec.decode(action_cb))
        assert decoded.source_context == SourceContext.ADMIN_PATIENTS
        assert decoded.source_ref == "search_patient:jane|patient:p1"
        action = _Callback(action_cb)
        asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(action))
        action_text_out, action_markup_out = action.message.edits[-1]
        assert "Jane Roe" in action_text_out
        assert action_markup_out is not None

    open_booking_decoded = asyncio.run(codec.decode(open_booking_cb))
    checked_in_cb = asyncio.run(
        codec.encode(
            CardCallback(
                profile=CardProfile.BOOKING,
                entity_type=EntityType.BOOKING,
                entity_id=open_booking_decoded.entity_id,
                action=CardAction.CHECKED_IN,
                mode=CardMode.EXPANDED,
                source_context=open_booking_decoded.source_context,
                source_ref=open_booking_decoded.source_ref,
                page_or_index="checked_in",
                state_token=open_booking_decoded.state_token,
            )
        )
    )
    checked_in = _Callback(checked_in_cb)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(checked_in))
    checked_text, checked_markup = checked_in.message.edits[-1]
    assert "Jane Roe" in checked_text
    assert checked_markup is not None

    back_cb = _booking_button(booking_markup, text="Back")
    back = _Callback(back_cb)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(back))
    back_panel_text, back_panel_markup = back.message.edits[-1]
    assert "Jane Roe" in back_panel_text
    assert back_panel_markup is not None

    patient_back_cb = _booking_button(back_panel_markup, text="Back")
    patient_back = _Callback(patient_back_cb)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(patient_back))
    queue_text, queue_markup = patient_back.message.edits[-1]
    assert "Patients" in queue_text
    assert "Jane Roe" in queue_text
    assert queue_markup is not None


def test_patient_origin_booking_back_callback_stale_token_is_bounded() -> None:
    router, codec, _ = _router()
    stale_back_cb = asyncio.run(
        codec.encode(
            CardCallback(
                profile=CardProfile.BOOKING,
                entity_type=EntityType.BOOKING,
                entity_id="b1",
                action=CardAction.BACK,
                mode=CardMode.EXPANDED,
                source_context=SourceContext.ADMIN_PATIENTS,
                source_ref="search_patient:jane|patient:p1",
                page_or_index="patients_open:p1",
                state_token="stale",
            )
        )
    )
    callback = _Callback(stale_back_cb)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(callback))
    assert any("outdated" in answer for answer in callback.answers)


def test_admin_patient_card_open_active_booking_no_match_is_bounded() -> None:
    router, _, _, booking_flow = _router_with_flow()
    msg = _Message("/admin_patients jane")
    asyncio.run(_handler(router, "admin_patients")(msg))
    open_patient_cb = msg.answers[-1][1].inline_keyboard[0][0].callback_data
    open_patient = _Callback(open_patient_cb)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(open_patient))
    assert open_patient.message.edits

    booking_flow._bookings_by_patient["p1"] = []

    panel_markup = open_patient.message.edits[-1][1]
    bookings_cb = _booking_button(panel_markup, text="Open active booking")
    request_open = _Callback(bookings_cb)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(request_open))
    assert any("No active or upcoming booking found" in answer for answer in request_open.answers)


def test_admin_patient_card_handcrafted_stale_booking_callback_is_bounded() -> None:
    router, codec, _ = _router()
    stale_cb = asyncio.run(
        codec.encode(
            CardCallback(
                profile=CardProfile.PATIENT,
                entity_type=EntityType.PATIENT,
                entity_id="p1",
                action=CardAction.BOOKINGS,
                mode=CardMode.EXPANDED,
                source_context=SourceContext.ADMIN_PATIENTS,
                source_ref="admin_patients:jane",
                page_or_index="open_patient",
                state_token="stale",
            )
        )
    )
    callback = _Callback(stale_cb)
    asyncio.run(_handler(router, "admin_runtime_card_callback", kind="callback")(callback))
    assert any("outdated" in answer for answer in callback.answers)


def test_admin_care_pickups_queue_and_action() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_care_pickups")
    asyncio.run(_handler(router, "admin_care_pickups")(msg))
    text, keyboard = msg.answers[-1]
    assert "Care Pickups Queue" in text

    action_cb = keyboard.inline_keyboard[2][0].callback_data
    callback = _Callback(action_cb)
    asyncio.run(_handler(router, "admin_care_pickups_callback", kind="callback")(callback))
    assert any("Care Pickups Queue" in row[0] for row in callback.message.edits)


def test_admin_care_pickups_detail_has_back_to_queue() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_care_pickups")
    asyncio.run(_handler(router, "admin_care_pickups")(msg))
    _, keyboard = msg.answers[-1]
    open_cb = keyboard.inline_keyboard[1][0].callback_data
    callback = _Callback(open_cb)
    asyncio.run(_handler(router, "admin_care_pickups_callback", kind="callback")(callback))
    _, detail_markup = callback.message.edits[-1]
    assert detail_markup is not None
    back_cb = detail_markup.inline_keyboard[0][0].callback_data
    back = _Callback(back_cb)
    asyncio.run(_handler(router, "admin_care_pickups_callback", kind="callback")(back))
    assert any("Care Pickups Queue" in row[0] for row in back.message.edits)


def test_admin_issues_localized_and_booking_open() -> None:
    router, codec, _ = _router()
    msg = _Message("/admin_issues")
    asyncio.run(_handler(router, "admin_issues")(msg))
    text, keyboard = msg.answers[-1]
    assert "did not respond" in text

    cb = keyboard.inline_keyboard[1][0].callback_data
    decoded = asyncio.run(codec.decode(cb))
    assert decoded.source_context == SourceContext.ADMIN_ISSUES


def test_admin_issues_patient_linked_open_has_back_to_queue() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_issues")
    asyncio.run(_handler(router, "admin_issues")(msg))
    _, keyboard = msg.answers[-1]
    patient_cb = next(
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if (button.callback_data or "").startswith("aw4i:patient:")
    )
    callback = _Callback(patient_cb)
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(callback))
    panel_text, panel_markup = callback.message.edits[-1]
    assert "Jane Roe" in panel_text
    assert panel_markup is not None
    back_cb = panel_markup.inline_keyboard[0][0].callback_data
    back = _Callback(back_cb)
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(back))
    assert any("Issues Queue" in row[0] for row in back.message.edits)


def test_waitlist_detail_uses_localized_service_label() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_waitlist")
    asyncio.run(_handler(router, "admin_waitlist")(msg))
    _, keyboard = msg.answers[-1]
    open_cb = keyboard.inline_keyboard[1][0].callback_data
    callback = _Callback(open_cb)
    asyncio.run(_handler(router, "admin_waitlist_callback", kind="callback")(callback))
    assert any("Today Workdesk" in row[0] for row in callback.message.edits)


def test_admin_issues_retry_action_is_visible_and_bounded() -> None:
    router, _, recovery = _router()
    msg = _Message("/admin_issues")
    asyncio.run(_handler(router, "admin_issues")(msg))
    _, keyboard = msg.answers[-1]
    retry_cb = next(
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if (button.callback_data or "").startswith("aw4i:retry:r_fail_1")
    )

    first = _Callback(retry_cb)
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(first))
    assert "Retry scheduled." in first.answers[-1]

    second = _Callback(retry_cb)
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(second))
    assert "Retry already scheduled." in second.answers[-1]
    assert recovery.calls.count("r_fail_1") == 2


def test_admin_issues_take_and_resolve_callbacks_refresh_queue() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_issues")
    asyncio.run(_handler(router, "admin_issues")(msg))
    _, keyboard = msg.answers[-1]
    take_cb = next(
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if (button.callback_data or "").startswith("aw4i:take:confirmation_no_response:")
    )
    take = _Callback(take_cb)
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(take))
    assert "Issue taken." in take.answers[-1]
    _, take_markup = take.message.edits[-1]
    assert take_markup is not None
    status_cb = take_markup.inline_keyboard[0][0].callback_data
    status_cycle = _Callback(status_cb)
    asyncio.run(_handler(router, "admin_aw4_queue_callback", kind="callback")(status_cycle))
    _, in_progress_markup = status_cycle.message.edits[-1]
    assert in_progress_markup is not None
    assert any(
        (button.callback_data or "").startswith("aw4i:resolve:confirmation_no_response:")
        for row in in_progress_markup.inline_keyboard
        for button in row
    )
    resolve_cb = next(
        button.callback_data
        for row in in_progress_markup.inline_keyboard
        for button in row
        if (button.callback_data or "").startswith("aw4i:resolve:confirmation_no_response:")
    )
    resolve = _Callback(resolve_cb)
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(resolve))
    assert "Issue resolved." in resolve.answers[-1]
    _, resolved_markup = resolve.message.edits[-1]
    assert resolved_markup is not None
    assert all(
        not (button.callback_data or "").startswith("aw4i:resolve:confirmation_no_response:")
        for row in resolved_markup.inline_keyboard
        for button in row
    )


def test_admin_issues_handcrafted_resolve_on_open_is_rejected() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_issues")
    asyncio.run(_handler(router, "admin_issues")(msg))
    _, keyboard = msg.answers[-1]
    issue_token = next(
        button.callback_data.split(":")[-1]
        for row in keyboard.inline_keyboard
        for button in row
        if (button.callback_data or "").startswith("aw4i:take:confirmation_no_response:")
    )
    handcrafted_resolve = _Callback(f"aw4i:resolve:confirmation_no_response:b1:{issue_token}")
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(handcrafted_resolve))
    assert any("first" in text.lower() for text in handcrafted_resolve.answers)
    assert not handcrafted_resolve.message.edits


def test_admin_issues_retry_and_lifecycle_coexist_without_queue_breakage() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_issues")
    asyncio.run(_handler(router, "admin_issues")(msg))
    _, keyboard = msg.answers[-1]
    retry_cb = next(
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if (button.callback_data or "").startswith("aw4i:retry:r_fail_1")
    )
    retry = _Callback(retry_cb)
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(retry))
    assert "Retry scheduled." in retry.answers[-1]

    take_cb = next(
        button.callback_data
        for row in retry.message.edits[-1][1].inline_keyboard  # type: ignore[union-attr]
        for button in row
        if (button.callback_data or "").startswith("aw4i:take:reminder_failed:r_fail_1")
    )
    take = _Callback(take_cb)
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(take))
    assert "Issue taken." in take.answers[-1]

    status_cb = take.message.edits[-1][1].inline_keyboard[0][0].callback_data  # type: ignore[union-attr]
    status_cycle = _Callback(status_cb)
    asyncio.run(_handler(router, "admin_aw4_queue_callback", kind="callback")(status_cycle))
    resolve_cb = next(
        button.callback_data
        for row in status_cycle.message.edits[-1][1].inline_keyboard  # type: ignore[union-attr]
        for button in row
        if (button.callback_data or "").startswith("aw4i:resolve:reminder_failed:r_fail_1")
    )
    resolve = _Callback(resolve_cb)
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(resolve))
    assert "Issue resolved." in resolve.answers[-1]


def test_admin_issues_unsupported_and_stale_lifecycle_callbacks_are_bounded() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_issues")
    asyncio.run(_handler(router, "admin_issues")(msg))
    _, keyboard = msg.answers[-1]
    stale_take = next(
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if (button.callback_data or "").startswith("aw4i:take:confirmation_no_response:")
    )
    stale = _Callback(stale_take.replace(stale_take.split(":")[-1], "bad"))
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(stale))
    assert any("outdated" in text.lower() for text in stale.answers)

    token = stale_take.split(":")[-1]
    unsupported = _Callback(f"aw4i:take:unknown_issue:unknown_1:{token}")
    asyncio.run(_handler(router, "admin_issues_object_callback", kind="callback")(unsupported))
    assert any("supported" in text.lower() for text in unsupported.answers)


def test_admin_issues_unsupported_kind_has_no_lifecycle_buttons() -> None:
    router, _, _ = _router()
    msg = _Message("/admin_issues")
    asyncio.run(_handler(router, "admin_issues")(msg))
    _, keyboard = msg.answers[-1]
    assert all(
        not (button.callback_data or "").startswith("aw4i:take:unknown_issue")
        and not (button.callback_data or "").startswith("aw4i:resolve:unknown_issue")
        for row in keyboard.inline_keyboard
        for button in row
    )
