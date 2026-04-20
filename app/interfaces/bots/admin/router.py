from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.application.admin.workdesk import AdminWorkdeskReadService

from app.application.access import AccessResolver
from app.application.care_commerce import CareCommerceService
from app.application.booking.telegram_flow import BookingPatientFlowService
from app.application.communication import ReminderRecoveryService
from app.application.clinic_reference import ClinicReferenceService
from app.application.search.service import HybridSearchService
from app.application.search.models import PatientSearchResult, SearchQuery
from app.application.voice import SpeechToTextService, VoiceSearchModeStore
from app.common.i18n import I18nService
from app.domain.access_identity.models import RoleCode
from app.interfaces.bots.common import guard_roles, resolve_locale
from app.interfaces.bots.search_handlers import run_doctor_search, run_patient_search, run_service_search
from app.interfaces.bots.voice_search import attach_voice_search_handlers
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator
from app.interfaces.cards import (
    BookingCardAdapter,
    BookingRuntimeViewBuilder,
    PatientCardAdapter,
    PatientRuntimeSnapshot,
    PatientRuntimeViewBuilder,
    CardAction,
    CardCallback,
    CardCallbackError,
    CardMode,
    CardProfile,
    CardShellRenderer,
    EntityType,
    SourceRef,
    SourceContext,
)


def _clinic_locale(reference_service: ClinicReferenceService, clinic_id: str) -> str | None:
    clinic = reference_service.get_clinic(clinic_id)
    return clinic.default_locale if clinic else None


async def _run_search(
    message: Message,
    *,
    access_resolver: AccessResolver,
    i18n: I18nService,
    default_locale: str,
) -> str | None:
    allowed = await guard_roles(
        message,
        i18n=i18n,
        access_resolver=access_resolver,
        allowed_roles={RoleCode.ADMIN},
        fallback_locale=default_locale,
    )
    if not allowed:
        return None
    return await resolve_locale(
        message,
        access_resolver=access_resolver,
        fallback_locale=default_locale,
    )


def make_router(
    i18n: I18nService,
    access_resolver: AccessResolver,
    reference_service: ClinicReferenceService,
    booking_flow: BookingPatientFlowService,
    search_service: HybridSearchService,
    stt_service: SpeechToTextService,
    voice_mode_store: VoiceSearchModeStore,
    care_commerce_service: CareCommerceService | None = None,
    admin_workdesk: AdminWorkdeskReadService | None = None,
    reminder_recovery: ReminderRecoveryService | None = None,
    *,
    default_locale: str,
    max_voice_duration_sec: int,
    max_voice_file_size_bytes: int,
    voice_mode_ttl_sec: int,
    card_runtime: CardRuntimeCoordinator | None = None,
    card_callback_codec: CardCallbackCodec | None = None,
) -> Router:
    router = Router(name="admin_router")
    booking_builder = BookingRuntimeViewBuilder()
    admin_today_scope = "admin_today_filters"
    admin_confirmations_scope = "admin_confirmations_filters"
    admin_reschedules_scope = "admin_reschedules_filters"
    admin_waitlist_scope = "admin_waitlist_filters"
    admin_patients_scope = "admin_patients_state"
    admin_care_pickups_scope = "admin_care_pickups_state"
    admin_issues_scope = "admin_issues_state"
    patient_builder = PatientRuntimeViewBuilder()

    def _resolved_service_label(*, clinic_id: str, service_id: str, raw_label: str, locale: str) -> str:
        translated = i18n.t(raw_label, locale)
        if translated != raw_label:
            return translated
        service = reference_service.get_service(clinic_id, service_id)
        if service is not None:
            localized = i18n.t(service.title_key, locale)
            if localized != service.title_key:
                return localized
            return service.code
        return raw_label

    def _issue_hint_label(*, issue_type: str, locale: str) -> str | None:
        mapping = {
            "confirmation_no_response": "admin.today.issue.confirmation_no_response",
            "reminder_failed": "admin.today.issue.reminder_failed",
        }
        key = mapping.get(issue_type)
        return i18n.t(key, locale) if key else None

    def _status_chip(*, status: str, locale: str) -> str:
        translated = i18n.t(f"booking.status.{status}", locale)
        return translated if translated != f"booking.status.{status}" else status

    def _localized_label(*, raw_label: str | None, locale: str) -> str:
        if not raw_label:
            return "-"
        translated = i18n.t(raw_label, locale)
        return translated if translated != raw_label else raw_label

    def _status_label(*, status: str, locale: str) -> str:
        translated = i18n.t(f"admin.queue.status.{status}", locale)
        return translated if translated != f"admin.queue.status.{status}" else _status_chip(status=status, locale=locale)

    def _pickup_status_label(*, status: str, locale: str) -> str:
        key = f"admin.care.pickups.status.{status}"
        translated = i18n.t(key, locale)
        return translated if translated != key else status

    def _ops_issue_label(*, issue_type: str, locale: str) -> str:
        key = f"admin.issues.type.{issue_type}"
        translated = i18n.t(key, locale)
        return translated if translated != key else issue_type

    def _confirmation_signal_label(*, signal: str, locale: str) -> str:
        translated = i18n.t(f"admin.confirmations.signal.{signal}", locale)
        return translated if translated != f"admin.confirmations.signal.{signal}" else signal

    def _reminder_hint_label(*, reminder_state_summary: str | None, no_response_flag: bool, locale: str) -> str:
        if no_response_flag:
            return i18n.t("admin.confirmations.no_response", locale)
        if not reminder_state_summary:
            return i18n.t("admin.confirmations.hint.none", locale)
        translated = i18n.t(f"admin.confirmations.reminder.{reminder_state_summary}", locale)
        return translated if translated != f"admin.confirmations.reminder.{reminder_state_summary}" else reminder_state_summary

    async def _load_queue_state(*, scope: str, actor_id: int, default_state: dict[str, str]) -> dict[str, str]:
        if card_runtime is None:
            return default_state
        state = await card_runtime.resolve_actor_session_state(scope=scope, actor_id=actor_id)
        if not state:
            return default_state
        merged = dict(default_state)
        for key in default_state:
            merged[key] = str(state.get(key) or default_state[key])
        return merged

    async def _save_queue_state(*, scope: str, actor_id: int, state: dict[str, str]) -> None:
        if card_runtime is None:
            return
        await card_runtime.bind_actor_session_state(scope=scope, actor_id=actor_id, payload=state)

    async def _load_admin_today_state(*, actor_id: int) -> dict[str, str]:
        if card_runtime is None:
            return {"branch_id": "-", "doctor_id": "-", "status": "all", "page": "1", "state_token": "na"}
        state = await card_runtime.resolve_actor_session_state(scope=admin_today_scope, actor_id=actor_id)
        if not state:
            return {"branch_id": "-", "doctor_id": "-", "status": "all", "page": "1", "state_token": "na"}
        return {
            "branch_id": str(state.get("branch_id") or "-"),
            "doctor_id": str(state.get("doctor_id") or "-"),
            "status": str(state.get("status") or "all"),
            "page": str(state.get("page") or "1"),
            "state_token": str(state.get("state_token") or "na"),
        }

    async def _save_admin_today_state(*, actor_id: int, state: dict[str, str]) -> None:
        if card_runtime is None:
            return
        await card_runtime.bind_actor_session_state(scope=admin_today_scope, actor_id=actor_id, payload=state)

    async def _render_admin_confirmations(
        *,
        actor_id: int,
        clinic_id: str,
        locale: str,
        state: dict[str, str],
    ) -> tuple[str, InlineKeyboardMarkup]:
        if admin_workdesk is None:
            return i18n.t("common.placeholder", locale), InlineKeyboardMarkup(inline_keyboard=[])
        rows = await admin_workdesk.get_confirmation_queue(
            clinic_id=clinic_id,
            only_no_response=(state.get("focus") == "no_response"),
            limit=40,
        )
        lines = [i18n.t("admin.confirmations.title", locale)]
        if not rows:
            lines.append(i18n.t("admin.confirmations.empty", locale))
        for row in rows[:15]:
            lines.append(
                i18n.t("admin.confirmations.row", locale).format(
                    time=row.local_service_time,
                    patient=row.patient_display_name,
                    doctor=row.doctor_display_name,
                    service=_localized_label(raw_label=row.service_label, locale=locale),
                    branch=row.branch_label,
                    signal=_confirmation_signal_label(signal=row.confirmation_signal, locale=locale),
                    reminder=_reminder_hint_label(
                        reminder_state_summary=row.reminder_state_summary,
                        no_response_flag=row.no_response_flag,
                        locale=locale,
                    ),
                )
            )
        token = f"{actor_id}-c-{len(rows)}-{state.get('focus', 'all')}"
        next_state = dict(state)
        next_state["state_token"] = token
        await _save_queue_state(scope=admin_confirmations_scope, actor_id=actor_id, state=next_state)
        controls = [
            InlineKeyboardButton(
                text=i18n.t("admin.confirmations.filter.no_response", locale),
                callback_data=f"aw3:confirmations:focus:{token}",
            )
        ]
        booking_rows = [
            [
                InlineKeyboardButton(
                    text=f"{row.local_service_time} · {row.patient_display_name}",
                    callback_data=await _encode_booking_callback(
                        booking_id=row.booking_id,
                        action=CardAction.OPEN,
                        page_or_index=f"confirmations_open:{token}",
                        source_context=SourceContext.ADMIN_CONFIRMATIONS,
                        source_ref=f"admin_confirmations:{state.get('focus', 'all')}",
                        state_token=token,
                    ),
                )
            ]
            for row in rows[:8]
        ]
        return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[controls, *booking_rows])

    async def _render_admin_reschedules(
        *,
        actor_id: int,
        clinic_id: str,
        locale: str,
        state: dict[str, str],
    ) -> tuple[str, InlineKeyboardMarkup]:
        if admin_workdesk is None:
            return i18n.t("common.placeholder", locale), InlineKeyboardMarkup(inline_keyboard=[])
        rows = await admin_workdesk.get_reschedule_queue(clinic_id=clinic_id, limit=40)
        lines = [i18n.t("admin.reschedules.title", locale)]
        if not rows:
            lines.append(i18n.t("admin.reschedules.empty", locale))
        for row in rows[:15]:
            if row.reschedule_context:
                translated_context = i18n.t(f"admin.reschedules.context.{row.reschedule_context}", locale)
                context = translated_context if translated_context != f"admin.reschedules.context.{row.reschedule_context}" else row.reschedule_context
            else:
                context = i18n.t("admin.reschedules.context.none", locale)
            lines.append(
                i18n.t("admin.reschedules.row", locale).format(
                    time=row.local_service_time,
                    patient=row.patient_display_name,
                    doctor=row.doctor_display_name,
                    service=_localized_label(raw_label=row.service_label, locale=locale),
                    branch=row.branch_label,
                    context=context,
                )
            )
        token = f"{actor_id}-r-{len(rows)}"
        next_state = dict(state)
        next_state["state_token"] = token
        await _save_queue_state(scope=admin_reschedules_scope, actor_id=actor_id, state=next_state)
        booking_rows = [
            [
                InlineKeyboardButton(
                    text=f"{row.local_service_time} · {row.patient_display_name}",
                    callback_data=await _encode_booking_callback(
                        booking_id=row.booking_id,
                        action=CardAction.OPEN,
                        page_or_index=f"reschedules_open:{token}",
                        source_context=SourceContext.ADMIN_RESCHEDULES,
                        source_ref="admin_reschedules",
                        state_token=token,
                    ),
                )
            ]
            for row in rows[:8]
        ]
        return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=booking_rows)

    async def _render_admin_waitlist(
        *,
        actor_id: int,
        clinic_id: str,
        locale: str,
        state: dict[str, str],
    ) -> tuple[str, InlineKeyboardMarkup]:
        if admin_workdesk is None:
            return i18n.t("common.placeholder", locale), InlineKeyboardMarkup(inline_keyboard=[])
        status_filter = None if state.get("status", "active") == "all" else (state.get("status", "active"),)
        rows = await admin_workdesk.get_waitlist_queue(clinic_id=clinic_id, statuses=status_filter, limit=40)
        lines = [i18n.t("admin.waitlist.title", locale)]
        if not rows:
            lines.append(i18n.t("admin.waitlist.empty", locale))
        for row in rows[:15]:
            lines.append(
                i18n.t("admin.waitlist.row", locale).format(
                    patient=row.patient_display_name,
                    doctor=row.doctor_display_name or i18n.t("admin.waitlist.preference.any", locale),
                    service=(
                        _resolved_service_label(
                            clinic_id=clinic_id,
                            service_id=row.preferred_service_id or "",
                            raw_label=row.service_label or i18n.t("admin.waitlist.preference.any", locale),
                            locale=locale,
                        )
                        if row.service_label
                        else i18n.t("admin.waitlist.preference.any", locale)
                    ),
                    window=row.preferred_time_window_summary or i18n.t("admin.waitlist.window.unspecified", locale),
                    status=_status_label(status=row.status, locale=locale),
                )
            )
        token = f"{actor_id}-w-{len(rows)}-{state.get('status', 'active')}"
        next_state = dict(state)
        next_state["state_token"] = token
        await _save_queue_state(scope=admin_waitlist_scope, actor_id=actor_id, state=next_state)
        controls = [
            InlineKeyboardButton(
                text=i18n.t("admin.waitlist.filter.status", locale),
                callback_data=f"aw3:waitlist:status:{token}",
            )
        ]
        row_buttons: list[list[InlineKeyboardButton]] = []
        for row in rows[:8]:
            row_buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{row.patient_display_name} · {_status_label(status=row.status, locale=locale)}",
                        callback_data=f"aw3w:open:{row.waitlist_entry_id}:{token}",
                    )
                ]
            )
            if row.status not in {"closed", "canceled"}:
                row_buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"{i18n.t('admin.waitlist.action.close', locale)} · {row.patient_display_name}",
                            callback_data=f"aw3w:close:{row.waitlist_entry_id}:{token}",
                        )
                    ]
                )
        return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[controls, *row_buttons])

    async def _render_admin_today(
        *,
        actor_id: int,
        clinic_id: str,
        locale: str,
        state: dict[str, str],
    ) -> tuple[str, InlineKeyboardMarkup]:
        if admin_workdesk is None:
            return i18n.t("common.placeholder", locale), InlineKeyboardMarkup(inline_keyboard=[])
        branch_id = None if state["branch_id"] == "-" else state["branch_id"]
        doctor_id = None if state["doctor_id"] == "-" else state["doctor_id"]
        statuses = None if state["status"] == "all" else (state["status"],)
        rows = await admin_workdesk.get_today_schedule(
            clinic_id=clinic_id,
            branch_id=branch_id,
            doctor_id=doctor_id,
            statuses=statuses,
            limit=40,
        )
        issues = await admin_workdesk.get_ops_issue_queue(clinic_id=clinic_id, branch_id=branch_id, limit=100)
        issue_by_booking: dict[str, list[str]] = {}
        for issue in issues:
            if not issue.booking_id:
                continue
            hint = _issue_hint_label(issue_type=issue.issue_type, locale=locale)
            if hint is None:
                continue
            issue_by_booking.setdefault(issue.booking_id, []).append(hint)
        lines = [
            i18n.t("admin.today.title", locale),
            i18n.t("admin.today.filters", locale).format(
                branch=state["branch_id"], doctor=state["doctor_id"], status=state["status"]
            ),
        ]
        if not rows:
            lines.append(i18n.t("admin.today.empty", locale))
        for row in rows[:15]:
            service_label = _resolved_service_label(
                clinic_id=clinic_id,
                service_id=row.service_id,
                raw_label=row.service_label,
                locale=locale,
            )
            hints = issue_by_booking.get(row.booking_id, [])
            hint_suffix = f" · {' / '.join(hints[:2])}" if hints else ""
            lines.append(
                i18n.t("admin.today.row", locale).format(
                    time=row.local_service_time,
                    patient=row.patient_display_name,
                    doctor=row.doctor_display_name,
                    service=service_label,
                    branch=row.branch_label,
                    status=_status_chip(status=row.booking_status, locale=locale),
                    flags=(row.compact_flags_summary or "-"),
                    issue_hint=hint_suffix,
                )
            )
        token = f"{actor_id}-{len(rows)}-{state['branch_id']}-{state['doctor_id']}-{state['status']}"
        next_state = dict(state)
        next_state["state_token"] = token
        await _save_admin_today_state(actor_id=actor_id, state=next_state)
        filters_row_1 = [
            InlineKeyboardButton(text=i18n.t("admin.today.filter.branch", locale), callback_data=f"aw2:filter:branch:{token}"),
            InlineKeyboardButton(text=i18n.t("admin.today.filter.doctor", locale), callback_data=f"aw2:filter:doctor:{token}"),
            InlineKeyboardButton(text=i18n.t("admin.today.filter.status", locale), callback_data=f"aw2:filter:status:{token}"),
        ]
        booking_rows = [
            [
                InlineKeyboardButton(
                    text=f"{row.local_service_time} · {row.patient_display_name}",
                    callback_data=await _encode_booking_callback(
                        booking_id=row.booking_id,
                        action=CardAction.OPEN,
                        page_or_index=f"today_open:{token}",
                        source_context=SourceContext.ADMIN_TODAY,
                        source_ref=f"admin_today:{state['branch_id']}:{state['doctor_id']}:{state['status']}",
                        state_token=token,
                    ),
                )
            ]
            for row in rows[:8]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[filters_row_1, *booking_rows])
        return "\n".join(lines), keyboard

    async def _render_admin_patients(
        *,
        actor_id: int,
        clinic_id: str,
        locale: str,
        state: dict[str, str],
    ) -> tuple[str, InlineKeyboardMarkup]:
        query = state.get("query", "").strip()
        lines = [i18n.t("admin.patients.title", locale)]
        if not query:
            lines.append(i18n.t("admin.patients.usage", locale))
            await _save_queue_state(scope=admin_patients_scope, actor_id=actor_id, state=state)
            return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[])
        response = await search_service.search_patients(SearchQuery(clinic_id=clinic_id, query=query, limit=12, locale=locale))
        rows = [*response.exact_matches, *response.suggestions]
        if not rows:
            lines.append(i18n.t("admin.patients.empty", locale))
        else:
            for row in rows[:12]:
                lines.append(
                    i18n.t("admin.patients.row", locale).format(
                        name=row.display_name,
                        patient_number=row.patient_number or "-",
                        phone=row.primary_phone_normalized or "-",
                        flags=row.active_flags_summary or "-",
                    )
                )
        token = f"{actor_id}-p-{len(rows)}-{query[:8]}"
        next_state = dict(state)
        next_state["state_token"] = token
        await _save_queue_state(scope=admin_patients_scope, actor_id=actor_id, state=next_state)
        buttons = [
            [
                InlineKeyboardButton(
                    text=f"{row.display_name} · {row.patient_number or row.patient_id}",
                    callback_data=await _encode_patient_callback(
                        patient_id=row.patient_id,
                        action=CardAction.OPEN,
                        page_or_index=f"patients_open:{token}",
                        source_context=SourceContext.ADMIN_PATIENTS,
                        source_ref=f"admin_patients:{query}",
                        state_token=token,
                    ),
                )
            ]
            for row in rows[:8]
        ]
        return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)

    async def _render_admin_care_pickups(
        *,
        actor_id: int,
        clinic_id: str,
        locale: str,
        state: dict[str, str],
    ) -> tuple[str, InlineKeyboardMarkup]:
        if admin_workdesk is None:
            return i18n.t("common.placeholder", locale), InlineKeyboardMarkup(inline_keyboard=[])
        status = state.get("status", "ready_for_pickup")
        statuses = None if status == "all" else (status,)
        rows = await admin_workdesk.get_care_pickup_queue(clinic_id=clinic_id, statuses=statuses, limit=40)
        lines = [i18n.t("admin.care.pickups.title", locale)]
        if not rows:
            lines.append(i18n.t("admin.care.pickups.empty", locale))
        for row in rows[:15]:
            lines.append(
                i18n.t("admin.care.pickups.row", locale).format(
                    patient=row.patient_display_name,
                    branch=row.branch_label,
                    item=row.compact_item_summary,
                    status=_pickup_status_label(status=row.pickup_status, locale=locale),
                    ready=(f"{row.local_ready_date} {row.local_ready_time}" if row.local_ready_date else "-"),
                )
            )
        token = f"{actor_id}-cp-{len(rows)}-{status}"
        next_state = dict(state)
        next_state["state_token"] = token
        await _save_queue_state(scope=admin_care_pickups_scope, actor_id=actor_id, state=next_state)
        controls = [[InlineKeyboardButton(text=i18n.t("admin.care.pickups.filter.status", locale), callback_data=f"aw4:care_pickups:status:{token}")]]
        row_buttons: list[list[InlineKeyboardButton]] = []
        for row in rows[:8]:
            row_buttons.append([InlineKeyboardButton(text=f"{row.patient_display_name} · {row.compact_item_summary}", callback_data=f"aw4cp:open:{row.care_order_id}:{token}")])
            if care_commerce_service is not None and row.pickup_status in {"ready_for_pickup", "paid"}:
                row_buttons.append([InlineKeyboardButton(text=i18n.t("admin.care.pickups.action.issue", locale), callback_data=f"aw4cp:action:issue:{row.care_order_id}:{token}")])
            if care_commerce_service is not None and row.pickup_status in {"ready_for_pickup", "issued"}:
                row_buttons.append([InlineKeyboardButton(text=i18n.t("admin.care.pickups.action.fulfill", locale), callback_data=f"aw4cp:action:fulfill:{row.care_order_id}:{token}")])
        return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[*controls, *row_buttons])

    async def _render_admin_issues(
        *,
        actor_id: int,
        clinic_id: str,
        locale: str,
        state: dict[str, str],
    ) -> tuple[str, InlineKeyboardMarkup]:
        if admin_workdesk is None:
            return i18n.t("common.placeholder", locale), InlineKeyboardMarkup(inline_keyboard=[])
        status = state.get("status", "open")
        statuses = None if status == "all" else (status,)
        rows = await admin_workdesk.get_ops_issue_queue(clinic_id=clinic_id, statuses=statuses, limit=40)
        lines = [i18n.t("admin.issues.title", locale)]
        if not rows:
            lines.append(i18n.t("admin.issues.empty", locale))
        for row in rows[:15]:
            lines.append(
                i18n.t("admin.issues.row", locale).format(
                    issue=_ops_issue_label(issue_type=row.issue_type, locale=locale),
                    severity=row.severity,
                    summary=(i18n.t(f"admin.issues.summary.{row.issue_type}", locale) if i18n.t(f"admin.issues.summary.{row.issue_type}", locale) != f"admin.issues.summary.{row.issue_type}" else row.summary_text),
                    related=(row.patient_display_name or row.patient_id or row.booking_id or row.care_order_id or "-"),
                )
            )
        token = f"{actor_id}-is-{len(rows)}-{status}"
        next_state = dict(state)
        next_state["state_token"] = token
        await _save_queue_state(scope=admin_issues_scope, actor_id=actor_id, state=next_state)
        controls = [[InlineKeyboardButton(text=i18n.t("admin.issues.filter.status", locale), callback_data=f"aw4:issues:status:{token}")]]
        row_buttons: list[list[InlineKeyboardButton]] = []
        for row in rows[:8]:
            if row.booking_id:
                row_buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"{_ops_issue_label(issue_type=row.issue_type, locale=locale)} · {row.booking_id}",
                            callback_data=await _encode_booking_callback(
                                booking_id=row.booking_id,
                                action=CardAction.OPEN,
                                page_or_index=f"issues_open:{token}",
                                source_context=SourceContext.ADMIN_ISSUES,
                                source_ref=f"admin_issues:{status}",
                                state_token=token,
                            ),
                        )
                    ]
                )
                if reminder_recovery is not None and row.issue_type == "reminder_failed":
                    row_buttons.append(
                        [
                            InlineKeyboardButton(
                                text=i18n.t("admin.issues.action.retry_reminder", locale),
                                callback_data=f"aw4i:retry:{row.issue_ref_id}:{token}",
                            )
                        ]
                    )
            elif row.patient_id:
                row_buttons.append([InlineKeyboardButton(text=f"{_ops_issue_label(issue_type=row.issue_type, locale=locale)} · {row.patient_display_name or row.patient_id}", callback_data=f"aw4i:patient:{row.patient_id}:{token}")])
            elif row.care_order_id:
                row_buttons.append([InlineKeyboardButton(text=f"{_ops_issue_label(issue_type=row.issue_type, locale=locale)} · {row.care_order_id}", callback_data=f"aw4i:care:{row.care_order_id}:{token}")])
        return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[*controls, *row_buttons])


    async def _encode_booking_callback(
        *,
        booking_id: str,
        action: CardAction,
        page_or_index: str,
        source_context: SourceContext = SourceContext.BOOKING_LIST,
        source_ref: str = "admin.booking.card",
        state_token: str | None = None,
    ) -> str:
        if card_callback_codec is None:
            return f"adminbk:{page_or_index}:{booking_id}"
        return await card_callback_codec.encode(
            CardCallback(
                profile=CardProfile.BOOKING,
                entity_type=EntityType.BOOKING,
                entity_id=booking_id,
                action=action,
                mode=CardMode.EXPANDED,
                source_context=source_context,
                source_ref=source_ref,
                page_or_index=page_or_index,
                state_token=state_token or booking_id,
            )
        )

    async def _encode_patient_callback(
        *,
        patient_id: str,
        action: CardAction,
        page_or_index: str,
        source_context: SourceContext,
        source_ref: str,
        state_token: str,
        mode: CardMode = CardMode.EXPANDED,
    ) -> str:
        if card_callback_codec is None:
            return f"adminpt:{page_or_index}:{patient_id}"
        return await card_callback_codec.encode(
            CardCallback(
                profile=CardProfile.PATIENT,
                entity_type=EntityType.PATIENT,
                entity_id=patient_id,
                action=action,
                mode=mode,
                source_context=source_context,
                source_ref=source_ref,
                page_or_index=page_or_index,
                state_token=state_token,
            )
        )

    async def _lookup_patient(*, clinic_id: str, patient_id: str, locale: str) -> PatientSearchResult | None:
        response = await search_service.search_patients(
            SearchQuery(clinic_id=clinic_id, query=f"id:{patient_id}", limit=1, locale=locale)
        )
        combined = [*response.exact_matches, *response.suggestions]
        return combined[0] if combined else None

    async def _build_patient_snapshot(
        *,
        clinic_id: str,
        patient_id: str,
        locale: str,
        display_name: str | None = None,
        patient_number: str | None = None,
        phone_hint: str | None = None,
        flags_summary: str | None = None,
    ) -> PatientRuntimeSnapshot:
        resolved = await _lookup_patient(clinic_id=clinic_id, patient_id=patient_id, locale=locale)
        active_flags_summary = flags_summary or (resolved.active_flags_summary if resolved else None)
        upcoming_rows = []
        if admin_workdesk is not None:
            upcoming_rows = await admin_workdesk.get_today_schedule(clinic_id=clinic_id, limit=80)
        upcoming = next((row for row in upcoming_rows if row.patient_id == patient_id), None)
        return PatientRuntimeSnapshot(
            patient_id=patient_id,
            display_name=display_name or (resolved.display_name if resolved else patient_id),
            state_token=f"pt:{patient_id}",
            patient_number=patient_number or (resolved.patient_number if resolved else None),
            primary_contact=phone_hint or (resolved.primary_phone_normalized if resolved else None),
            is_photo_present=False,
            active_flags=tuple((active_flags_summary or "").split(", ")) if active_flags_summary else (),
            upcoming_booking_label=(f"{upcoming.local_service_time} · {upcoming.service_label}" if upcoming else None),
            recommendation_summary=(
                i18n.t("admin.patient.summary.recommendation.linked", locale)
                if upcoming and upcoming.recommendation_linked_flag
                else i18n.t("admin.patient.summary.recommendation.none", locale)
            ),
            care_order_summary=(
                i18n.t("admin.patient.summary.care_order.linked", locale)
                if upcoming and upcoming.care_order_linked_flag
                else i18n.t("admin.patient.summary.care_order.none", locale)
            ),
            chart_summary_entry=i18n.t("admin.patient.summary.chart.policy", locale),
        )

    async def _render_patient_panel(
        *,
        clinic_id: str,
        patient_id: str,
        locale: str,
        source_context: SourceContext,
        source_ref: str,
        state_token: str,
        display_name: str | None = None,
        patient_number: str | None = None,
        phone_hint: str | None = None,
        flags_summary: str | None = None,
    ) -> str:
        snapshot = await _build_patient_snapshot(
            clinic_id=clinic_id,
            patient_id=patient_id,
            locale=locale,
            display_name=display_name,
            patient_number=patient_number,
            phone_hint=phone_hint,
            flags_summary=flags_summary,
        )
        shell = PatientCardAdapter.build(
            seed=patient_builder.build_seed(snapshot=snapshot),
            source=SourceRef(context=source_context, source_ref=source_ref),
            actor_roles={RoleCode.ADMIN},
            i18n=i18n,
            locale=locale,
            mode=CardMode.EXPANDED,
        )
        return CardShellRenderer.to_panel(shell).text

    def _render_admin_booking_panel(*, booking, locale: str) -> str:
        snapshot = booking_flow.build_booking_snapshot(booking=booking, role_variant="admin")
        seed = booking_builder.build_seed(snapshot=snapshot, i18n=i18n, locale=locale)
        shell = BookingCardAdapter.build(
            seed=seed,
            source=SourceRef(context=SourceContext.BOOKING_LIST, source_ref="admin_booking"),
            i18n=i18n,
            locale=locale,
            mode=CardMode.EXPANDED,
        )
        return CardShellRenderer.to_panel(shell).text

    async def _admin_linked_back_keyboard(*, booking_id: str, locale: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("common.back", locale),
                        callback_data=await _encode_booking_callback(
                            booking_id=booking_id,
                            action=CardAction.OPEN,
                            page_or_index="open_booking",
                        ),
                    )
                ]
            ]
        )

    def _simple_back_keyboard(*, locale: str, callback_data: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("common.back", locale),
                        callback_data=callback_data,
                    )
                ]
            ]
        )

    async def _admin_booking_keyboard(
        *,
        booking,
        locale: str,
        source_context: SourceContext = SourceContext.BOOKING_LIST,
        source_ref: str = "admin.booking.card",
        page_or_index: str = "open_booking",
        state_token: str | None = None,
    ) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        if booking.status == "pending_confirmation":
            rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.confirm", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.CONFIRM, page_or_index="confirm", source_context=source_context, source_ref=source_ref, state_token=state_token))])
        if booking.status in {"confirmed", "reschedule_requested"}:
            rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.arrived", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.CHECKED_IN, page_or_index="checked_in", source_context=source_context, source_ref=source_ref, state_token=state_token))])
        if booking.status not in {"completed", "canceled", "no_show"}:
            rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.reschedule", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.RESCHEDULE, page_or_index="reschedule", source_context=source_context, source_ref=source_ref, state_token=state_token))])
            rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.cancel", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.CANCEL, page_or_index="cancel", source_context=source_context, source_ref=source_ref, state_token=state_token))])
        rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.patient", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.OPEN_PATIENT, page_or_index="open_patient", source_context=source_context, source_ref=source_ref, state_token=state_token))])
        rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.chart", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.OPEN_CHART, page_or_index="open_chart", source_context=source_context, source_ref=source_ref, state_token=state_token))])
        rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.recommendation", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.OPEN_RECOMMENDATION, page_or_index="open_recommendation", source_context=source_context, source_ref=source_ref, state_token=state_token))])
        rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.care_order", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.OPEN_CARE_ORDER, page_or_index="open_care_order", source_context=source_context, source_ref=source_ref, state_token=state_token))])
        if source_context in {SourceContext.ADMIN_TODAY, SourceContext.ADMIN_CONFIRMATIONS, SourceContext.ADMIN_RESCHEDULES, SourceContext.ADMIN_ISSUES}:
            rows.append([InlineKeyboardButton(text=i18n.t("common.back", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.BACK, page_or_index=page_or_index, source_context=source_context, source_ref=source_ref, state_token=state_token))])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    attach_voice_search_handlers(
        router,
        i18n=i18n,
        access_resolver=access_resolver,
        search_service=search_service,
        stt_service=stt_service,
        mode_store=voice_mode_store,
        default_locale=default_locale,
        allowed_roles={RoleCode.ADMIN},
        max_voice_duration_sec=max_voice_duration_sec,
        max_voice_file_size_bytes=max_voice_file_size_bytes,
        mode_ttl_sec=voice_mode_ttl_sec,
    )

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        await message.answer(i18n.t("role.admin.home", locale))

    @router.message(Command("search_patient"))
    async def search_patient(message: Message) -> None:
        locale = await _run_search(message, access_resolver=access_resolver, i18n=i18n, default_locale=default_locale)
        if locale is None:
            return
        if not message.from_user or not message.text:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        query = message.text.replace("/search_patient", "", 1).strip()
        if not query:
            await message.answer(i18n.t("search.usage.patient", locale))
            return
        await message.answer(
            await run_patient_search(
                service=search_service,
                i18n=i18n,
                locale=locale,
                clinic_id=actor_context.clinic_id,
                query=query,
            )
        )

    @router.message(Command("search_doctor"))
    async def search_doctor(message: Message) -> None:
        locale = await _run_search(message, access_resolver=access_resolver, i18n=i18n, default_locale=default_locale)
        if locale is None:
            return
        if not message.from_user or not message.text:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        query = message.text.replace("/search_doctor", "", 1).strip()
        if not query:
            await message.answer(i18n.t("search.usage.doctor", locale))
            return
        await message.answer(
            await run_doctor_search(
                service=search_service,
                i18n=i18n,
                locale=locale,
                clinic_id=actor_context.clinic_id,
                query=query,
            )
        )

    @router.message(Command("search_service"))
    async def search_service_handler(message: Message) -> None:
        locale = await _run_search(message, access_resolver=access_resolver, i18n=i18n, default_locale=default_locale)
        if locale is None:
            return
        if not message.from_user or not message.text:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        query = message.text.replace("/search_service", "", 1).strip()
        if not query:
            await message.answer(i18n.t("search.usage.service", locale))
            return
        await message.answer(
            await run_service_search(
                service=search_service,
                i18n=i18n,
                locale=locale,
                clinic_id=actor_context.clinic_id,
                query=query,
            )
        )

    @router.message(Command("clinic"))
    async def clinic_summary(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        clinic = reference_service.get_clinic(actor_context.clinic_id)
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        if not clinic:
            await message.answer(i18n.t("admin.reference.empty", locale))
            return
        await message.answer(
            i18n.t("admin.reference.clinic", locale).format(
                name=clinic.display_name,
                code=clinic.code,
                timezone=clinic.timezone,
                status=clinic.status,
            )
        )

    @router.message(Command("branches"))
    async def branch_list(message: Message) -> None:
        await _list_reference(message, i18n, access_resolver, reference_service, default_locale=default_locale, entity="branches")

    @router.message(Command("doctors"))
    async def doctor_list(message: Message) -> None:
        await _list_reference(message, i18n, access_resolver, reference_service, default_locale=default_locale, entity="doctors")

    @router.message(Command("services"))
    async def service_list(message: Message) -> None:
        await _list_reference(message, i18n, access_resolver, reference_service, default_locale=default_locale, entity="services")

    @router.message(Command("booking_escalations"))
    async def booking_escalations(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        items = await booking_flow.list_admin_escalations(clinic_id=actor_context.clinic_id, limit=10)
        if not items:
            await message.answer(i18n.t("admin.booking.escalations.empty", locale))
            return
        lines = [i18n.t("admin.booking.escalations.title", locale)]
        for item in items:
            lines.append(
                i18n.t("admin.booking.escalations.item", locale).format(
                    escalation_id=item.admin_escalation_id,
                    session_id=item.booking_session_id,
                    priority=item.priority,
                    reason=item.reason_code,
                    patient_id=item.patient_id or "-",
                )
            )
        await message.answer("\n".join(lines))

    @router.message(Command("booking_new"))
    async def booking_new(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        bookings = await booking_flow.list_admin_new_bookings(clinic_id=actor_context.clinic_id, limit=10)
        if not bookings:
            await message.answer(i18n.t("admin.booking.new.empty", locale))
            return
        lines = [i18n.t("admin.booking.new.title", locale)]
        rows: list[list[InlineKeyboardButton]] = []
        for booking in bookings:
            card = booking_flow.build_booking_card(booking=booking)
            lines.append(i18n.t("admin.booking.new.item", locale).format(booking_id=booking.booking_id, status=i18n.t(card.status_label, locale), doctor=card.doctor_label, service=card.service_label, dt=card.datetime_label))
            rows.append([InlineKeyboardButton(text=f"{booking.booking_id} · {i18n.t(card.status_label, locale)}", callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.OPEN, page_or_index="open_booking"))])
        await message.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    @router.message(Command("care_orders"))
    async def care_orders(message: Message) -> None:
        if care_commerce_service is None:
            return
        locale = await _run_search(message, access_resolver=access_resolver, i18n=i18n, default_locale=default_locale)
        if locale is None or not message.from_user:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        rows = await care_commerce_service.list_admin_orders(
            clinic_id=actor_context.clinic_id,
            statuses=("created", "awaiting_confirmation", "confirmed", "awaiting_payment", "paid", "ready_for_pickup"),
            limit=15,
        )
        if not rows:
            await message.answer(i18n.t("admin.care.orders.empty", locale))
            return
        lines = [i18n.t("admin.care.orders.title", locale)]
        for row in rows:
            product_label = "-"
            order_items = await care_commerce_service.repository.list_order_items(row.care_order_id)
            if order_items:
                product = await care_commerce_service.repository.get_product(order_items[0].care_product_id)
                if product is not None:
                    content = await care_commerce_service.resolve_product_content(
                        clinic_id=row.clinic_id,
                        product=product,
                        locale=locale,
                        fallback_locale=default_locale,
                    )
                    product_label = content.short_label or content.title or i18n.t(product.title_key, locale)
            lines.append(
                i18n.t("admin.care.orders.item", locale).format(
                    care_order_id=row.care_order_id,
                    patient_id=row.patient_id,
                    status=row.status,
                    amount=row.total_amount,
                    currency=row.currency_code,
                    branch_id=(row.pickup_branch_id or "-"),
                )
                + f" · {product_label}"
            )
        await message.answer("\n".join(lines))

    @router.message(Command("care_order_action"))
    async def care_order_action(message: Message) -> None:
        if care_commerce_service is None:
            return
        locale = await _run_search(message, access_resolver=access_resolver, i18n=i18n, default_locale=default_locale)
        if locale is None or not message.text:
            return
        parts = message.text.split(maxsplit=2)
        if len(parts) != 3:
            await message.answer(i18n.t("admin.care.order.action.usage", locale))
            return
        action, care_order_id = parts[1], parts[2]
        if action not in {"ready", "issue", "fulfill", "cancel", "pay_required", "paid"}:
            await message.answer(i18n.t("admin.care.order.action.usage", locale))
            return
        try:
            updated = await care_commerce_service.apply_admin_order_action(care_order_id=care_order_id, action=action)
        except ValueError:
            error_key = "admin.care.order.action.invalid"
            if action == "ready":
                existing = await care_commerce_service.get_order(care_order_id)
                if existing is not None and existing.pickup_branch_id is None:
                    error_key = "admin.care.order.action.pickup_branch_required"
                else:
                    error_key = "admin.care.order.action.insufficient_stock"
            await message.answer(i18n.t(error_key, locale))
            return
        if updated is None:
            await message.answer(i18n.t("admin.care.order.action.missing", locale))
            return
        await message.answer(i18n.t("admin.care.order.action.ok", locale).format(care_order_id=updated.care_order_id, status=updated.status))

    @router.message(Command("booking_escalation_open"))
    async def booking_escalation_open(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user or not message.text:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("admin.booking.escalation.open.usage", locale))
            return
        escalation = await booking_flow.get_admin_escalation_detail(clinic_id=actor_context.clinic_id, escalation_id=parts[1])
        if escalation is None:
            await message.answer(i18n.t("admin.booking.escalation.open.missing", locale))
            return
        await message.answer(
            i18n.t("admin.booking.escalation.open.panel", locale).format(
                escalation_id=escalation.admin_escalation_id,
                session_id=escalation.booking_session_id,
                reason=escalation.reason_code,
                priority=escalation.priority,
                status=escalation.status,
            )
        )

    @router.message(Command("booking_escalation_take"))
    async def booking_escalation_take(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user or not message.text:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("admin.booking.escalation.take.usage", locale))
            return
        escalation = await booking_flow.take_admin_escalation(
            clinic_id=actor_context.clinic_id,
            escalation_id=parts[1],
            actor_id=actor_context.actor_id,
        )
        if escalation is None:
            await message.answer(i18n.t("admin.booking.escalation.open.missing", locale))
            return
        await message.answer(i18n.t("admin.booking.escalation.take.ok", locale).format(escalation_id=escalation.admin_escalation_id))

    @router.message(Command("booking_escalation_resolve"))
    async def booking_escalation_resolve(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user or not message.text:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("admin.booking.escalation.resolve.usage", locale))
            return
        escalation = await booking_flow.resolve_admin_escalation(
            clinic_id=actor_context.clinic_id,
            escalation_id=parts[1],
            actor_id=actor_context.actor_id,
        )
        if escalation is None:
            await message.answer(i18n.t("admin.booking.escalation.open.missing", locale))
            return
        await message.answer(i18n.t("admin.booking.escalation.resolve.ok", locale).format(escalation_id=escalation.admin_escalation_id))

    @router.message(Command("booking_open"))
    async def booking_open(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user or not message.text:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("admin.booking.open.usage", locale))
            return
        booking = await booking_flow.reads.get_booking(parts[1])
        if booking is None:
            await message.answer(i18n.t("admin.booking.open.missing", locale))
            return
        await message.answer(_render_admin_booking_panel(booking=booking, locale=locale), reply_markup=await _admin_booking_keyboard(booking=booking, locale=locale, source_context=SourceContext.BOOKING_LIST, source_ref='admin.booking.card', page_or_index='open_booking', state_token=booking.booking_id))

    @router.message(Command("admin_today"))
    async def admin_today(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        state = await _load_admin_today_state(actor_id=message.from_user.id)
        text, keyboard = await _render_admin_today(
            actor_id=message.from_user.id,
            clinic_id=actor_context.clinic_id,
            locale=locale,
            state=state,
        )
        await message.answer(text, reply_markup=keyboard)

    @router.message(Command("admin_confirmations"))
    async def admin_confirmations(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        state = await _load_queue_state(
            scope=admin_confirmations_scope,
            actor_id=message.from_user.id,
            default_state={"focus": "all", "state_token": "na"},
        )
        text, keyboard = await _render_admin_confirmations(
            actor_id=message.from_user.id,
            clinic_id=actor_context.clinic_id,
            locale=locale,
            state=state,
        )
        await message.answer(text, reply_markup=keyboard)

    @router.message(Command("admin_reschedules"))
    async def admin_reschedules(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        state = await _load_queue_state(
            scope=admin_reschedules_scope,
            actor_id=message.from_user.id,
            default_state={"state_token": "na"},
        )
        text, keyboard = await _render_admin_reschedules(
            actor_id=message.from_user.id,
            clinic_id=actor_context.clinic_id,
            locale=locale,
            state=state,
        )
        await message.answer(text, reply_markup=keyboard)

    @router.message(Command("admin_waitlist"))
    async def admin_waitlist(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        state = await _load_queue_state(
            scope=admin_waitlist_scope,
            actor_id=message.from_user.id,
            default_state={"status": "active", "state_token": "na"},
        )
        text, keyboard = await _render_admin_waitlist(
            actor_id=message.from_user.id,
            clinic_id=actor_context.clinic_id,
            locale=locale,
            state=state,
        )
        await message.answer(text, reply_markup=keyboard)

    @router.message(Command("admin_patients"))
    async def admin_patients(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        query = (message.text or "").replace("/admin_patients", "", 1).strip()
        state = await _load_queue_state(
            scope=admin_patients_scope,
            actor_id=message.from_user.id,
            default_state={"query": query, "state_token": "na"},
        )
        if query:
            state["query"] = query
        text, keyboard = await _render_admin_patients(
            actor_id=message.from_user.id,
            clinic_id=actor_context.clinic_id,
            locale=locale,
            state=state,
        )
        await message.answer(text, reply_markup=keyboard)

    @router.message(Command("admin_care_pickups"))
    async def admin_care_pickups(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        state = await _load_queue_state(
            scope=admin_care_pickups_scope,
            actor_id=message.from_user.id,
            default_state={"status": "ready_for_pickup", "state_token": "na"},
        )
        text, keyboard = await _render_admin_care_pickups(
            actor_id=message.from_user.id,
            clinic_id=actor_context.clinic_id,
            locale=locale,
            state=state,
        )
        await message.answer(text, reply_markup=keyboard)

    @router.message(Command("admin_issues"))
    async def admin_issues(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.ADMIN},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user:
            return
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor_context:
            return
        locale = await resolve_locale(
            message,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        state = await _load_queue_state(
            scope=admin_issues_scope,
            actor_id=message.from_user.id,
            default_state={"status": "open", "state_token": "na"},
        )
        text, keyboard = await _render_admin_issues(
            actor_id=message.from_user.id,
            clinic_id=actor_context.clinic_id,
            locale=locale,
            state=state,
        )
        await message.answer(text, reply_markup=keyboard)

    @router.callback_query(F.data.startswith("aw2:"))
    async def admin_today_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data or not callback.message:
            return
        actor_context = access_resolver.resolve_actor_context(callback.from_user.id)
        if not actor_context:
            return
        locale = await resolve_locale(
            callback,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        parts = callback.data.split(":")
        if len(parts) != 4:
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        _, action, key, token = parts
        state = await _load_admin_today_state(actor_id=callback.from_user.id)
        if card_runtime is not None and token != state.get("state_token"):
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        if action == "filter":
            if key == "branch":
                branches = reference_service.list_branches(actor_context.clinic_id)
                current = state.get("branch_id", "-")
                if branches:
                    ids = ["-"] + [b.branch_id for b in branches]
                    state["branch_id"] = ids[(ids.index(current) + 1) % len(ids)] if current in ids else "-"
            elif key == "doctor":
                doctors = reference_service.list_doctors(actor_context.clinic_id)
                current = state.get("doctor_id", "-")
                if doctors:
                    ids = ["-"] + [d.doctor_id for d in doctors]
                    state["doctor_id"] = ids[(ids.index(current) + 1) % len(ids)] if current in ids else "-"
            elif key == "status":
                statuses = ["all", "pending_confirmation", "confirmed", "checked_in", "reschedule_requested"]
                current = state.get("status", "all")
                state["status"] = statuses[(statuses.index(current) + 1) % len(statuses)] if current in statuses else "all"
        text, keyboard = await _render_admin_today(
            actor_id=callback.from_user.id,
            clinic_id=actor_context.clinic_id,
            locale=locale,
            state=state,
        )
        await callback.message.edit_text(text, reply_markup=keyboard)

    @router.callback_query(F.data.startswith("aw3:"))
    async def admin_aw3_queue_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data or not callback.message:
            return
        actor_context = access_resolver.resolve_actor_context(callback.from_user.id)
        if actor_context is None:
            return
        locale = await resolve_locale(
            callback,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        parts = callback.data.split(":")
        if len(parts) != 4:
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        _, queue, action, token = parts
        if queue == "confirmations":
            state = await _load_queue_state(
                scope=admin_confirmations_scope,
                actor_id=callback.from_user.id,
                default_state={"focus": "all", "state_token": "na"},
            )
            if card_runtime is not None and token != state.get("state_token"):
                await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
                return
            if action == "focus":
                state["focus"] = "all" if state.get("focus") == "no_response" else "no_response"
            text, keyboard = await _render_admin_confirmations(
                actor_id=callback.from_user.id,
                clinic_id=actor_context.clinic_id,
                locale=locale,
                state=state,
            )
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        if queue == "waitlist":
            state = await _load_queue_state(
                scope=admin_waitlist_scope,
                actor_id=callback.from_user.id,
                default_state={"status": "active", "state_token": "na"},
            )
            if card_runtime is not None and token != state.get("state_token"):
                await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
                return
            if action == "status":
                statuses = ["active", "closed", "all"]
                current = state.get("status", "active")
                state["status"] = statuses[(statuses.index(current) + 1) % len(statuses)] if current in statuses else "active"
            text, keyboard = await _render_admin_waitlist(
                actor_id=callback.from_user.id,
                clinic_id=actor_context.clinic_id,
                locale=locale,
                state=state,
            )
            await callback.message.edit_text(text, reply_markup=keyboard)

    @router.callback_query(F.data.startswith("aw3w:"))
    async def admin_waitlist_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data or not callback.message:
            return
        actor_context = access_resolver.resolve_actor_context(callback.from_user.id)
        if actor_context is None or admin_workdesk is None:
            return
        locale = await resolve_locale(
            callback,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        parts = callback.data.split(":")
        if len(parts) != 4:
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        _, action, entry_id, token = parts
        state = await _load_queue_state(
            scope=admin_waitlist_scope,
            actor_id=callback.from_user.id,
            default_state={"status": "active", "state_token": "na"},
        )
        if card_runtime is not None and token != state.get("state_token"):
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        if action == "back":
            text, keyboard = await _render_admin_waitlist(
                actor_id=callback.from_user.id,
                clinic_id=actor_context.clinic_id,
                locale=locale,
                state=state,
            )
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        rows = await admin_workdesk.get_waitlist_queue(clinic_id=actor_context.clinic_id, limit=60)
        row = next((item for item in rows if item.waitlist_entry_id == entry_id), None)
        if row is None:
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        if action == "close":
            await callback.message.edit_text(
                i18n.t("admin.waitlist.closed", locale).format(entry_id=row.waitlist_entry_id, patient=row.patient_display_name),
                reply_markup=_simple_back_keyboard(locale=locale, callback_data=f"aw3w:back:na:{token}"),
            )
            return
        await callback.message.edit_text(
            i18n.t("admin.waitlist.detail", locale).format(
                entry_id=row.waitlist_entry_id,
                patient=row.patient_display_name,
                doctor=row.doctor_display_name or i18n.t("admin.waitlist.preference.any", locale),
                service=(
                    _resolved_service_label(
                        clinic_id=actor_context.clinic_id,
                        service_id=row.preferred_service_id or "",
                        raw_label=row.service_label or i18n.t("admin.waitlist.preference.any", locale),
                        locale=locale,
                    )
                    if row.service_label
                    else i18n.t("admin.waitlist.preference.any", locale)
                ),
                window=row.preferred_time_window_summary or i18n.t("admin.waitlist.window.unspecified", locale),
                status=_status_label(status=row.status, locale=locale),
            ),
            reply_markup=_simple_back_keyboard(locale=locale, callback_data=f"aw3w:back:na:{token}"),
        )

    @router.callback_query(F.data.startswith("aw4:"))
    async def admin_aw4_queue_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data or not callback.message:
            return
        actor_context = access_resolver.resolve_actor_context(callback.from_user.id)
        if actor_context is None:
            return
        locale = await resolve_locale(
            callback,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        parts = callback.data.split(":")
        if len(parts) != 4:
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        _, queue, action, token = parts
        if queue == "care_pickups":
            state = await _load_queue_state(scope=admin_care_pickups_scope, actor_id=callback.from_user.id, default_state={"status": "ready_for_pickup", "state_token": "na"})
            if card_runtime is not None and token != state.get("state_token"):
                await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
                return
            if action == "status":
                statuses = ["ready_for_pickup", "issued", "fulfilled", "all"]
                current = state.get("status", "ready_for_pickup")
                state["status"] = statuses[(statuses.index(current) + 1) % len(statuses)] if current in statuses else "ready_for_pickup"
            text, keyboard = await _render_admin_care_pickups(actor_id=callback.from_user.id, clinic_id=actor_context.clinic_id, locale=locale, state=state)
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        if queue == "issues":
            state = await _load_queue_state(scope=admin_issues_scope, actor_id=callback.from_user.id, default_state={"status": "open", "state_token": "na"})
            if card_runtime is not None and token != state.get("state_token"):
                await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
                return
            if action == "status":
                statuses = ["open", "in_progress", "resolved", "all"]
                current = state.get("status", "open")
                state["status"] = statuses[(statuses.index(current) + 1) % len(statuses)] if current in statuses else "open"
            text, keyboard = await _render_admin_issues(actor_id=callback.from_user.id, clinic_id=actor_context.clinic_id, locale=locale, state=state)
            await callback.message.edit_text(text, reply_markup=keyboard)

    @router.callback_query(F.data.startswith("aw4cp:"))
    async def admin_care_pickups_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data or not callback.message:
            return
        actor_context = access_resolver.resolve_actor_context(callback.from_user.id)
        if actor_context is None:
            return
        locale = await resolve_locale(
            callback,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        parts = callback.data.split(":")
        if len(parts) not in {4, 5}:
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        state = await _load_queue_state(scope=admin_care_pickups_scope, actor_id=callback.from_user.id, default_state={"status": "ready_for_pickup", "state_token": "na"})
        token = parts[-1]
        if card_runtime is not None and token != state.get("state_token"):
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        if parts[1] == "back":
            text, keyboard = await _render_admin_care_pickups(actor_id=callback.from_user.id, clinic_id=actor_context.clinic_id, locale=locale, state=state)
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        if parts[1] == "open":
            care_order_id = parts[2]
            if care_commerce_service is None:
                return
            order = await care_commerce_service.get_order(care_order_id)
            if order is None:
                await callback.answer(i18n.t("admin.care.order.action.missing", locale), show_alert=True)
                return
            await callback.message.edit_text(
                i18n.t("admin.care.pickups.detail", locale).format(
                    care_order_id=order.care_order_id,
                    patient_id=order.patient_id,
                    status=_pickup_status_label(status=order.status, locale=locale),
                ),
                reply_markup=_simple_back_keyboard(locale=locale, callback_data=f"aw4cp:back:na:{token}"),
            )
            return
        if parts[1] == "action" and care_commerce_service is not None:
            action = parts[2]
            care_order_id = parts[3]
            try:
                await care_commerce_service.apply_admin_order_action(care_order_id=care_order_id, action=action)
            except ValueError:
                await callback.answer(i18n.t("admin.care.order.action.invalid", locale), show_alert=True)
                return
            text, keyboard = await _render_admin_care_pickups(actor_id=callback.from_user.id, clinic_id=actor_context.clinic_id, locale=locale, state=state)
            await callback.message.edit_text(text, reply_markup=keyboard)

    @router.callback_query(F.data.startswith("aw4i:"))
    async def admin_issues_object_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data or not callback.message:
            return
        actor_context = access_resolver.resolve_actor_context(callback.from_user.id)
        if actor_context is None:
            return
        locale = await resolve_locale(
            callback,
            access_resolver=access_resolver,
            fallback_locale=default_locale,
            clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
        )
        parts = callback.data.split(":")
        if len(parts) != 4:
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        kind, entity_id, token = parts[1], parts[2], parts[3]
        state = await _load_queue_state(scope=admin_issues_scope, actor_id=callback.from_user.id, default_state={"status": "open", "state_token": "na"})
        if card_runtime is not None and token != state.get("state_token"):
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        if kind == "back":
            text, keyboard = await _render_admin_issues(
                actor_id=callback.from_user.id,
                clinic_id=actor_context.clinic_id,
                locale=locale,
                state=state,
            )
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        if kind == "patient":
            panel = await _render_patient_panel(
                clinic_id=actor_context.clinic_id,
                patient_id=entity_id,
                locale=locale,
                source_context=SourceContext.ADMIN_ISSUES,
                source_ref=f"admin_issues:{state.get('status', 'open')}",
                state_token=token,
            )
            await callback.message.edit_text(
                panel,
                reply_markup=_simple_back_keyboard(locale=locale, callback_data=f"aw4i:back:na:{token}"),
            )
            return
        if kind == "care":
            await callback.message.edit_text(
                i18n.t("admin.issues.care_order.linked", locale).format(care_order_id=entity_id),
                reply_markup=_simple_back_keyboard(locale=locale, callback_data=f"aw4i:back:na:{token}"),
            )
            return
        if kind == "retry" and reminder_recovery is not None:
            result = await reminder_recovery.retry_failed_reminder(reminder_id=entity_id, now=datetime.now(timezone.utc))
            await callback.answer(i18n.t(f"admin.issues.retry.{result.outcome}", locale), show_alert=(result.outcome != "scheduled"))
            text, keyboard = await _render_admin_issues(
                actor_id=callback.from_user.id,
                clinic_id=actor_context.clinic_id,
                locale=locale,
                state=state,
            )
            await callback.message.edit_text(text, reply_markup=keyboard)

    @router.callback_query(F.data.startswith("c2|"))
    async def admin_runtime_card_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        if card_callback_codec is None:
            return
        locale = await resolve_locale(callback, access_resolver=access_resolver, fallback_locale=default_locale, clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id))
        try:
            decoded = await card_callback_codec.decode(callback.data)
        except CardCallbackError:
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        if decoded.source_context not in {
            SourceContext.BOOKING_LIST,
            SourceContext.ADMIN_TODAY,
            SourceContext.ADMIN_CONFIRMATIONS,
            SourceContext.ADMIN_RESCHEDULES,
            SourceContext.ADMIN_ISSUES,
            SourceContext.ADMIN_PATIENTS,
        }:
            return
        if decoded.source_context == SourceContext.ADMIN_TODAY and callback.from_user:
            state = await _load_admin_today_state(actor_id=callback.from_user.id)
            if decoded.state_token != state.get("state_token"):
                await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
                return
        if decoded.source_context == SourceContext.ADMIN_CONFIRMATIONS and callback.from_user:
            state = await _load_queue_state(
                scope=admin_confirmations_scope,
                actor_id=callback.from_user.id,
                default_state={"focus": "all", "state_token": "na"},
            )
            if decoded.state_token != state.get("state_token"):
                await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
                return
        if decoded.source_context == SourceContext.ADMIN_RESCHEDULES and callback.from_user:
            state = await _load_queue_state(
                scope=admin_reschedules_scope,
                actor_id=callback.from_user.id,
                default_state={"state_token": "na"},
            )
            if decoded.state_token != state.get("state_token"):
                await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
                return
        if decoded.source_context == SourceContext.ADMIN_ISSUES and callback.from_user:
            state = await _load_queue_state(
                scope=admin_issues_scope,
                actor_id=callback.from_user.id,
                default_state={"status": "open", "state_token": "na"},
            )
            if decoded.state_token != state.get("state_token"):
                await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
                return
        if decoded.source_context == SourceContext.ADMIN_PATIENTS and callback.from_user:
            state = await _load_queue_state(
                scope=admin_patients_scope,
                actor_id=callback.from_user.id,
                default_state={"query": "", "state_token": "na"},
            )
            if decoded.state_token != state.get("state_token"):
                await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
                return
        if decoded.profile == CardProfile.PATIENT and decoded.source_context in {SourceContext.ADMIN_PATIENTS, SourceContext.ADMIN_ISSUES}:
            actor_context = access_resolver.resolve_actor_context(callback.from_user.id)
            if actor_context is None:
                return
            if decoded.source_context == SourceContext.ADMIN_PATIENTS:
                state = await _load_queue_state(scope=admin_patients_scope, actor_id=callback.from_user.id, default_state={"query": "", "state_token": "na"})
                if decoded.state_token != state.get("state_token"):
                    await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
                    return
            panel = await _render_patient_panel(
                clinic_id=actor_context.clinic_id,
                patient_id=decoded.entity_id,
                locale=locale,
                source_context=decoded.source_context,
                source_ref=decoded.source_ref,
                state_token=decoded.state_token,
            )
            if decoded.action == CardAction.BACK and decoded.source_context == SourceContext.ADMIN_PATIENTS:
                state = await _load_queue_state(scope=admin_patients_scope, actor_id=callback.from_user.id, default_state={"query": "", "state_token": "na"})
                text, keyboard = await _render_admin_patients(actor_id=callback.from_user.id, clinic_id=actor_context.clinic_id, locale=locale, state=state)
                await callback.message.edit_text(text, reply_markup=keyboard)
                return
            await callback.message.edit_text(
                panel,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=i18n.t("common.back", locale),
                                callback_data=await _encode_patient_callback(
                                    patient_id=decoded.entity_id,
                                    action=CardAction.BACK,
                                    page_or_index=decoded.page_or_index,
                                    source_context=decoded.source_context,
                                    source_ref=decoded.source_ref,
                                    state_token=decoded.state_token,
                                ),
                            )
                        ]
                    ]
                ),
            )
            return
        if decoded.profile != CardProfile.BOOKING:
            return
        booking = await booking_flow.reads.get_booking(decoded.entity_id)
        if booking is None:
            await callback.answer(i18n.t("admin.booking.open.missing", locale), show_alert=True)
            return
        if decoded.action == CardAction.OPEN and (
            decoded.page_or_index == "open_booking"
            or decoded.page_or_index.startswith("today_open:")
            or decoded.page_or_index.startswith("confirmations_open:")
            or decoded.page_or_index.startswith("reschedules_open:")
            or decoded.page_or_index.startswith("issues_open:")
        ):
            await callback.message.edit_text(_render_admin_booking_panel(booking=booking, locale=locale), reply_markup=await _admin_booking_keyboard(booking=booking, locale=locale, source_context=decoded.source_context, source_ref=decoded.source_ref, page_or_index=decoded.page_or_index, state_token=decoded.state_token))
            return
        if decoded.page_or_index == "confirm":
            result = await booking_flow.orchestration.confirm_booking(booking_id=booking.booking_id, reason_code="admin_confirmed")
            if result.kind == "success":
                booking = result.entity
        elif decoded.page_or_index == "checked_in":
            result = await booking_flow.orchestration.booking_state_service.transition_booking(booking_id=booking.booking_id, to_status="checked_in", reason_code="admin_checked_in")
            booking = result.entity
        elif decoded.page_or_index == "reschedule":
            result = await booking_flow.orchestration.request_booking_reschedule(booking_id=booking.booking_id, reason_code="admin_requested_reschedule")
            if result.kind == "success":
                booking = result.entity
        elif decoded.page_or_index == "cancel":
            result = await booking_flow.orchestration.cancel_booking(booking_id=booking.booking_id, reason_code="admin_canceled")
            if result.kind == "success":
                booking = result.entity
        elif decoded.page_or_index == "open_patient":
            actor_context = access_resolver.resolve_actor_context(callback.from_user.id)
            if actor_context is None:
                return
            panel = await _render_patient_panel(
                clinic_id=actor_context.clinic_id,
                patient_id=booking.patient_id,
                locale=locale,
                source_context=decoded.source_context,
                source_ref=decoded.source_ref,
                state_token=decoded.state_token,
            )
            await callback.message.edit_text(panel, reply_markup=await _admin_linked_back_keyboard(booking_id=booking.booking_id, locale=locale))
            return
        elif decoded.page_or_index == "open_chart":
            snapshot = booking_flow.build_booking_snapshot(booking=booking, role_variant="admin")
            await callback.message.edit_text(
                i18n.t("admin.booking.open.panel", locale).format(
                    booking_id=booking.booking_id,
                    doctor=snapshot.doctor_label,
                    service=snapshot.service_label,
                    datetime=booking_builder.build_seed(snapshot=snapshot, i18n=i18n, locale=locale).datetime_label,
                    branch=snapshot.branch_label,
                    status=i18n.t(f"booking.status.{booking.status}", locale),
                    next_step=i18n.t("patient.booking.card.next.default", locale),
                ),
                reply_markup=await _admin_linked_back_keyboard(booking_id=booking.booking_id, locale=locale),
            )
            return
        elif decoded.page_or_index == "open_recommendation":
            await callback.message.edit_text(
                f"recommendation :: patient={booking.patient_id}",
                reply_markup=await _admin_linked_back_keyboard(booking_id=booking.booking_id, locale=locale),
            )
            return
        elif decoded.page_or_index == "open_care_order":
            await callback.message.edit_text(
                f"care_order :: patient={booking.patient_id}",
                reply_markup=await _admin_linked_back_keyboard(booking_id=booking.booking_id, locale=locale),
            )
            return
        if decoded.action == CardAction.BACK and decoded.source_context == SourceContext.ADMIN_TODAY and decoded.page_or_index.startswith("today_open:"):
            actor_context = access_resolver.resolve_actor_context(callback.from_user.id)
            if actor_context is None:
                return
            state = await _load_admin_today_state(actor_id=callback.from_user.id)
            text, keyboard = await _render_admin_today(
                actor_id=callback.from_user.id,
                clinic_id=actor_context.clinic_id,
                locale=locale,
                state=state,
            )
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        if decoded.action == CardAction.BACK and decoded.source_context == SourceContext.ADMIN_CONFIRMATIONS and decoded.page_or_index.startswith("confirmations_open:"):
            actor_context = access_resolver.resolve_actor_context(callback.from_user.id)
            if actor_context is None:
                return
            state = await _load_queue_state(
                scope=admin_confirmations_scope,
                actor_id=callback.from_user.id,
                default_state={"focus": "all", "state_token": "na"},
            )
            text, keyboard = await _render_admin_confirmations(
                actor_id=callback.from_user.id,
                clinic_id=actor_context.clinic_id,
                locale=locale,
                state=state,
            )
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        if decoded.action == CardAction.BACK and decoded.source_context == SourceContext.ADMIN_RESCHEDULES and decoded.page_or_index.startswith("reschedules_open:"):
            actor_context = access_resolver.resolve_actor_context(callback.from_user.id)
            if actor_context is None:
                return
            state = await _load_queue_state(
                scope=admin_reschedules_scope,
                actor_id=callback.from_user.id,
                default_state={"state_token": "na"},
            )
            text, keyboard = await _render_admin_reschedules(
                actor_id=callback.from_user.id,
                clinic_id=actor_context.clinic_id,
                locale=locale,
                state=state,
            )
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        if decoded.action == CardAction.BACK and decoded.source_context == SourceContext.ADMIN_ISSUES and decoded.page_or_index.startswith("issues_open:"):
            actor_context = access_resolver.resolve_actor_context(callback.from_user.id)
            if actor_context is None:
                return
            state = await _load_queue_state(
                scope=admin_issues_scope,
                actor_id=callback.from_user.id,
                default_state={"status": "open", "state_token": "na"},
            )
            text, keyboard = await _render_admin_issues(
                actor_id=callback.from_user.id,
                clinic_id=actor_context.clinic_id,
                locale=locale,
                state=state,
            )
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        await callback.message.edit_text(_render_admin_booking_panel(booking=booking, locale=locale), reply_markup=await _admin_booking_keyboard(booking=booking, locale=locale, source_context=decoded.source_context, source_ref=decoded.source_ref, page_or_index=decoded.page_or_index, state_token=decoded.state_token))

    return router


async def _list_reference(
    message: Message,
    i18n: I18nService,
    access_resolver: AccessResolver,
    reference_service: ClinicReferenceService,
    *,
    default_locale: str,
    entity: str,
) -> None:
    allowed = await guard_roles(
        message,
        i18n=i18n,
        access_resolver=access_resolver,
        allowed_roles={RoleCode.ADMIN},
        fallback_locale=default_locale,
    )
    if not allowed or not message.from_user:
        return
    actor_context = access_resolver.resolve_actor_context(message.from_user.id)
    if not actor_context:
        return
    locale = await resolve_locale(
        message,
        access_resolver=access_resolver,
        fallback_locale=default_locale,
        clinic_locale_getter=lambda actor: _clinic_locale(reference_service, actor.clinic_id),
    )

    if entity == "branches":
        values = reference_service.list_branches(actor_context.clinic_id)
        lines = [f"• {item.display_name} ({item.timezone})" for item in values]
        title_key = "admin.reference.branches"
    elif entity == "doctors":
        values = reference_service.list_doctors(actor_context.clinic_id)
        lines = [f"• {item.display_name} [{item.specialty_code}]" for item in values]
        title_key = "admin.reference.doctors"
    else:
        values = reference_service.list_services(actor_context.clinic_id)
        lines = [f"• {item.code}: {item.duration_minutes}m" for item in values]
        title_key = "admin.reference.services"

    if not values:
        await message.answer(i18n.t("admin.reference.empty", locale))
        return
    await message.answer(f"{i18n.t(title_key, locale)}\n" + "\n".join(lines))
