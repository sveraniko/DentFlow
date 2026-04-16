from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup

from app.application.booking.orchestration_outcomes import ConflictOutcome, InvalidStateOutcome, OrchestrationSuccess, SlotUnavailableOutcome
from app.application.booking.telegram_flow import BookingPatientFlowService
from app.application.clinic_reference import ClinicReferenceService
from app.common.i18n import I18nService


@dataclass(slots=True)
class _PanelState:
    message_id: int
    session_id: str


def make_router(
    i18n: I18nService,
    booking_flow: BookingPatientFlowService,
    reference: ClinicReferenceService,
    *,
    default_locale: str,
) -> Router:
    router = Router(name="patient_router")
    panel_by_user: dict[int, _PanelState] = {}
    session_by_user: dict[int, str] = {}

    def _locale() -> str:
        return default_locale

    def _primary_clinic_id() -> str | None:
        clinics = list(reference.repository.clinics.values())
        return clinics[0].clinic_id if clinics else None

    async def _send_or_edit_panel(
        *,
        actor_id: int,
        message: Message | CallbackQuery,
        text: str,
        keyboard: InlineKeyboardMarkup | None = None,
        session_id: str,
        reply_keyboard: ReplyKeyboardMarkup | None = None,
    ) -> None:
        state = panel_by_user.get(actor_id)
        if isinstance(message, CallbackQuery):
            current_message = message.message
            if current_message:
                await current_message.edit_text(text=text, reply_markup=keyboard)
                panel_by_user[actor_id] = _PanelState(message_id=current_message.message_id, session_id=session_id)
            await message.answer()
            return
        if state:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=state.message_id,
                    text=text,
                    reply_markup=keyboard,
                )
                panel_by_user[actor_id] = _PanelState(message_id=state.message_id, session_id=session_id)
                return
            except Exception:
                pass
        sent = await message.answer(text, reply_markup=reply_keyboard or keyboard)
        panel_by_user[actor_id] = _PanelState(message_id=sent.message_id, session_id=session_id)

    async def _render_service_panel(message: Message | CallbackQuery, *, actor_id: int, session_id: str, clinic_id: str) -> None:
        locale = _locale()
        services = booking_flow.list_services(clinic_id=clinic_id)
        buttons = [[InlineKeyboardButton(text=svc.code, callback_data=f"book:svc:{svc.service_id}")] for svc in services[:8]]
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=i18n.t("patient.booking.service.prompt", locale),
            keyboard=InlineKeyboardMarkup(inline_keyboard=buttons),
        )

    async def _render_doctor_pref_panel(
        message: Message | CallbackQuery, *, actor_id: int, session_id: str, clinic_id: str, branch_id: str | None
    ) -> None:
        locale = _locale()
        doctors = booking_flow.list_doctors(clinic_id=clinic_id, branch_id=branch_id)
        rows = [[InlineKeyboardButton(text=i18n.t("patient.booking.doctor.any", locale), callback_data="book:doc:any")]]
        rows.extend([[InlineKeyboardButton(text=doctor.display_name, callback_data=f"book:doc:{doctor.doctor_id}")] for doctor in doctors[:6]])
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=i18n.t("patient.booking.doctor.prompt", locale),
            keyboard=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    async def _render_slot_panel(message: Message | CallbackQuery, *, actor_id: int, session_id: str) -> None:
        locale = _locale()
        slots = await booking_flow.list_slots_for_session(booking_session_id=session_id)
        if not slots:
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.slot.empty", locale),
            )
            return
        rows = []
        for slot in slots:
            label = slot.start_at.astimezone(timezone.utc).strftime("%a %d %b · %H:%M UTC")
            rows.append([InlineKeyboardButton(text=label, callback_data=f"book:slot:{slot.slot_id}")])
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=session_id,
            text=i18n.t("patient.booking.slot.prompt", locale),
            keyboard=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(i18n.t("role.patient.home", _locale()))

    @router.message(Command("book"))
    async def book_entry(message: Message) -> None:
        if not message.from_user:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await message.answer(i18n.t("patient.booking.unavailable", _locale()))
            return
        session = await booking_flow.start_or_resume_session(
            clinic_id=clinic_id,
            telegram_user_id=message.from_user.id,
        )
        session_by_user[message.from_user.id] = session.booking_session_id
        await _render_service_panel(
            message,
            actor_id=message.from_user.id,
            session_id=session.booking_session_id,
            clinic_id=clinic_id,
        )

    @router.callback_query(F.data.startswith("book:svc:"))
    async def select_service(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        session_id = session_by_user.get(callback.from_user.id)
        clinic_id = _primary_clinic_id()
        if not session_id or not clinic_id:
            await callback.answer(i18n.t("patient.booking.session.missing", _locale()), show_alert=True)
            return
        service_id = callback.data.split(":")[-1]
        session = await booking_flow.update_service(booking_session_id=session_id, service_id=service_id)
        await _render_doctor_pref_panel(
            callback,
            actor_id=callback.from_user.id,
            session_id=session.booking_session_id,
            clinic_id=session.clinic_id,
            branch_id=session.branch_id,
        )

    @router.callback_query(F.data.startswith("book:doc:"))
    async def select_doctor_preference(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        session_id = session_by_user.get(callback.from_user.id)
        if not session_id:
            await callback.answer(i18n.t("patient.booking.session.missing", _locale()), show_alert=True)
            return
        doctor_token = callback.data.split(":")[-1]
        if doctor_token == "any":
            await booking_flow.update_doctor_preference(booking_session_id=session_id, doctor_preference_type="any", doctor_id=None)
        else:
            await booking_flow.update_doctor_preference(
                booking_session_id=session_id,
                doctor_preference_type="specific",
                doctor_id=doctor_token,
            )
        await _render_slot_panel(callback, actor_id=callback.from_user.id, session_id=session_id)

    @router.callback_query(F.data.startswith("book:slot:"))
    async def select_slot(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        locale = _locale()
        session_id = session_by_user.get(callback.from_user.id)
        if not session_id:
            await callback.answer(i18n.t("patient.booking.session.missing", locale), show_alert=True)
            return
        slot_id = callback.data.split(":")[-1]
        selected = await booking_flow.select_slot(booking_session_id=session_id, slot_id=slot_id)
        if isinstance(selected, (SlotUnavailableOutcome, ConflictOutcome)):
            await callback.answer(i18n.t("patient.booking.slot.unavailable", locale), show_alert=True)
            await _render_slot_panel(callback, actor_id=callback.from_user.id, session_id=session_id)
            return
        contact_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=i18n.t("patient.booking.contact.share", locale), request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await _send_or_edit_panel(
            actor_id=callback.from_user.id,
            message=callback,
            session_id=session_id,
            text=i18n.t("patient.booking.contact.prompt", locale),
            reply_keyboard=contact_keyboard,
        )

    @router.message(F.contact)
    async def on_contact_share(message: Message) -> None:
        if not message.from_user or not message.contact:
            return
        await _handle_contact_submission(message, actor_id=message.from_user.id, phone=message.contact.phone_number)

    @router.message(F.text.regexp(r"^\+?\d[\d\-\s\(\)]{6,}$"))
    async def on_contact_text(message: Message) -> None:
        if not message.from_user or not message.text:
            return
        await _handle_contact_submission(message, actor_id=message.from_user.id, phone=message.text)

    async def _handle_contact_submission(message: Message, *, actor_id: int, phone: str) -> None:
        locale = _locale()
        session_id = session_by_user.get(actor_id)
        if not session_id:
            return
        await booking_flow.set_contact_phone(booking_session_id=session_id, phone=phone)
        display_name = (message.from_user.full_name or "").strip() or i18n.t("patient.booking.contact.default_name", locale)
        resolution = await booking_flow.resolve_patient_from_contact(
            booking_session_id=session_id,
            phone=phone,
            fallback_display_name=display_name,
        )
        if resolution.kind == "ambiguous_escalated":
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.escalated", locale),
            )
            return
        review = await booking_flow.mark_review_ready(booking_session_id=session_id)
        if isinstance(review, InvalidStateOutcome):
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.review.invalid", locale),
            )
            return
        finalized = await booking_flow.finalize(booking_session_id=session_id)
        if isinstance(finalized, OrchestrationSuccess):
            booking = finalized.entity
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.success", locale).format(
                    doctor=booking.doctor_id,
                    service=booking.service_id,
                    datetime=booking.scheduled_start_at.strftime("%Y-%m-%d %H:%M UTC"),
                    branch=booking.branch_id or "-",
                    status=booking.status,
                ),
            )
            return
        key = {
            "invalid_state": "patient.booking.finalize.invalid_state",
            "slot_unavailable": "patient.booking.finalize.slot_unavailable",
            "conflict": "patient.booking.finalize.conflict",
            "escalated": "patient.booking.escalated",
        }.get(finalized.kind, "patient.booking.finalize.invalid_state")
        await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=session_id, text=i18n.t(key, locale))

    return router

