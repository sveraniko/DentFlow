from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup

from app.application.communication import ReminderActionService
from app.application.care_commerce import CareCommerceService
from app.application.booking.orchestration_outcomes import ConflictOutcome, InvalidStateOutcome, OrchestrationSuccess, SlotUnavailableOutcome
from app.application.booking.telegram_flow import BookingCardView, BookingControlResolutionResult, BookingPatientFlowService
from app.application.clinic_reference import ClinicReferenceService
from app.common.i18n import I18nService
from app.application.recommendation import RecommendationService


@dataclass(slots=True)
class _PanelState:
    message_id: int
    session_id: str


def make_router(
    i18n: I18nService,
    booking_flow: BookingPatientFlowService,
    reference: ClinicReferenceService,
    reminder_actions: ReminderActionService,
    recommendation_service: RecommendationService | None = None,
    care_commerce_service: CareCommerceService | None = None,
    recommendation_repository=None,
    *,
    default_locale: str,
) -> Router:
    router = Router(name="patient_router")
    panel_by_user: dict[int, _PanelState] = {}
    session_by_user: dict[int, str] = {}
    mode_by_user: dict[int, str] = {}

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
        buttons = [[InlineKeyboardButton(text=svc.code, callback_data=f"book:svc:{session_id}:{svc.service_id}")] for svc in services[:8]]
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
        rows = [[InlineKeyboardButton(text=i18n.t("patient.booking.doctor.any", locale), callback_data=f"book:doc:{session_id}:any")]]
        rows.extend([[InlineKeyboardButton(text=doctor.display_name, callback_data=f"book:doc:{session_id}:{doctor.doctor_id}")] for doctor in doctors[:6]])
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
            rows.append([InlineKeyboardButton(text=label, callback_data=f"book:slot:{session_id}:{slot.slot_id}")])
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

    async def _resolve_patient_id_for_user(telegram_user_id: int) -> str | None:
        clinic_id = _primary_clinic_id()
        if clinic_id is None or recommendation_repository is None:
            return None
        list_finder = getattr(recommendation_repository, "find_patient_ids_by_telegram_user", None)
        if callable(list_finder):
            rows = await list_finder(clinic_id=clinic_id, telegram_user_id=telegram_user_id)
            if len(rows) != 1:
                return None
            return rows[0]
        finder = getattr(recommendation_repository, "find_patient_id_by_telegram_user", None)
        if not callable(finder):
            return None
        return await finder(clinic_id=clinic_id, telegram_user_id=telegram_user_id)

    @router.message(Command("recommendations"))
    async def recommendations_list(message: Message) -> None:
        if not message.from_user or recommendation_service is None:
            return
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        if not patient_id:
            await message.answer(i18n.t("patient.recommendations.patient_resolution_failed", _locale()))
            return
        rows = await recommendation_service.list_for_patient(patient_id=patient_id)
        if not rows:
            await message.answer(i18n.t("patient.recommendations.empty", _locale()))
            return
        lines = [i18n.t("patient.recommendations.title", _locale())]
        for row in rows[:8]:
            lines.append(f"• {row.title} [{row.recommendation_type}] ({row.status})")
            lines.append(f"  /recommendation_open {row.recommendation_id}")
        await message.answer("\n".join(lines))

    @router.message(Command("recommendation_open"))
    async def recommendations_open(message: Message) -> None:
        if not message.from_user or not message.text or recommendation_service is None:
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("patient.recommendations.open.usage", _locale()))
            return
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        recommendation = await recommendation_service.get(parts[1].strip())
        if not patient_id or recommendation is None or recommendation.patient_id != patient_id:
            await message.answer(i18n.t("patient.recommendations.not_found", _locale()))
            return
        if recommendation.status == "issued":
            recommendation = await recommendation_service.mark_viewed(recommendation_id=recommendation.recommendation_id)
        text = i18n.t("patient.recommendations.detail", _locale()).format(
            title=recommendation.title if recommendation else "-",
            body=(recommendation.body_text if recommendation else "-"),
            recommendation_type=(recommendation.recommendation_type if recommendation else "-"),
            status=(recommendation.status if recommendation else "-"),
            recommendation_id=parts[1].strip(),
        )
        await message.answer(text)

    @router.message(Command("recommendation_action"))
    async def recommendations_action(message: Message) -> None:
        if not message.from_user or not message.text or recommendation_service is None:
            return
        parts = message.text.split(maxsplit=3)
        if len(parts) != 4:
            await message.answer(i18n.t("patient.recommendations.action.usage", _locale()))
            return
        action = parts[1].strip()
        recommendation_id = parts[2].strip()
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        recommendation = await recommendation_service.get(recommendation_id)
        if not patient_id or recommendation is None or recommendation.patient_id != patient_id:
            await message.answer(i18n.t("patient.recommendations.not_found", _locale()))
            return
        try:
            if action == "ack":
                updated = await recommendation_service.acknowledge(recommendation_id=recommendation_id)
            elif action == "accept":
                updated = await recommendation_service.accept(recommendation_id=recommendation_id)
            elif action == "decline":
                updated = await recommendation_service.decline(recommendation_id=recommendation_id)
            else:
                await message.answer(i18n.t("patient.recommendations.action.usage", _locale()))
                return
        except ValueError:
            await message.answer(i18n.t("patient.recommendations.action.invalid_state", _locale()))
            return
        await message.answer(i18n.t("patient.recommendations.action.ok", _locale()).format(status=(updated.status if updated else recommendation.status)))

    @router.message(Command("recommendation_products"))
    async def recommendation_products(message: Message) -> None:
        if not message.from_user or not message.text or recommendation_service is None or care_commerce_service is None:
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("patient.care.products.open.usage", _locale()))
            return
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        if not patient_id:
            await message.answer(i18n.t("patient.recommendations.patient_resolution_failed", _locale()))
            return
        recommendation = await recommendation_service.get(parts[1].strip())
        if recommendation is None or recommendation.patient_id != patient_id:
            await message.answer(i18n.t("patient.recommendations.not_found", _locale()))
            return
        resolved = await care_commerce_service.resolve_recommendation_targets(
            clinic_id=_primary_clinic_id() or recommendation.clinic_id,
            recommendation_id=recommendation.recommendation_id,
            recommendation_type=recommendation.recommendation_type,
            locale=_locale(),
        )
        if not resolved:
            await message.answer(i18n.t("patient.care.products.empty", _locale()))
            return
        lines = [i18n.t("patient.care.products.title", _locale())]
        rec_explanation = recommendation.rationale_text or recommendation.body_text
        if rec_explanation:
            lines.append(rec_explanation.strip()[:180])
        for item in resolved:
            product = item.product
            content = await care_commerce_service.resolve_product_content(
                clinic_id=_primary_clinic_id() or recommendation.clinic_id,
                product=product,
                locale=_locale(),
                fallback_locale=_locale(),
            )
            title = content.title or i18n.t(product.title_key, _locale())
            lines.append(
                i18n.t("patient.care.products.item", _locale()).format(
                    recommendation_id=item.recommendation_id,
                    product_id=product.care_product_id,
                    title=title,
                    price=product.price_amount,
                    currency=product.currency_code,
                    rank=item.relevance_rank,
                )
            )
            explanation = item.explanation_text or content.justification_text
            if explanation:
                lines.append(f"  · {explanation[:140]}")
        await message.answer("\n".join(lines))

    @router.message(Command("care_order_create"))
    async def care_order_create(message: Message) -> None:
        if not message.from_user or not message.text or recommendation_service is None or care_commerce_service is None:
            return
        parts = message.text.split(maxsplit=3)
        if len(parts) != 4:
            await message.answer(i18n.t("patient.care.order.create.usage", _locale()))
            return
        recommendation_id, care_product_id, pickup_branch_id = parts[1], parts[2], parts[3]
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        clinic_id = _primary_clinic_id()
        if not patient_id or clinic_id is None:
            await message.answer(i18n.t("patient.recommendations.patient_resolution_failed", _locale()))
            return
        recommendation = await recommendation_service.get(recommendation_id)
        if recommendation is None or recommendation.patient_id != patient_id:
            await message.answer(i18n.t("patient.recommendations.not_found", _locale()))
            return
        branches = reference.list_branches(clinic_id)
        if not any(branch.branch_id == pickup_branch_id for branch in branches):
            await message.answer(i18n.t("patient.care.order.branch_invalid", _locale()))
            return
        linked = await care_commerce_service.resolve_recommendation_targets(
            clinic_id=clinic_id,
            recommendation_id=recommendation_id,
            recommendation_type=recommendation.recommendation_type,
            locale=_locale(),
        )
        match = next((item.product for item in linked if item.care_product_id == care_product_id), None)
        if match is None:
            await message.answer(i18n.t("patient.care.order.product_not_linked", _locale()))
            return
        free_qty = await care_commerce_service.compute_free_qty(branch_id=pickup_branch_id, care_product_id=match.care_product_id)
        if free_qty < 1:
            content = await care_commerce_service.resolve_product_content(
                clinic_id=clinic_id,
                product=match,
                locale=_locale(),
                fallback_locale=_locale(),
            )
            await message.answer(
                i18n.t("patient.care.order.out_of_stock", _locale()).format(
                    branch_id=pickup_branch_id,
                    title=content.title or i18n.t(match.title_key, _locale()),
                )
            )
            return
        order = await care_commerce_service.create_order(
            clinic_id=clinic_id,
            patient_id=patient_id,
            payment_mode="pay_at_pickup",
            currency_code=match.currency_code,
            pickup_branch_id=pickup_branch_id,
            recommendation_id=recommendation_id,
            booking_id=recommendation.booking_id,
            items=[(match, 1)],
        )
        await care_commerce_service.transition_order(care_order_id=order.care_order_id, to_status="confirmed")
        await message.answer(i18n.t("patient.care.order.created", _locale()).format(care_order_id=order.care_order_id, status="confirmed", branch_id=pickup_branch_id))

    @router.message(Command("care_orders"))
    async def care_orders(message: Message) -> None:
        if not message.from_user or care_commerce_service is None:
            return
        patient_id = await _resolve_patient_id_for_user(message.from_user.id)
        clinic_id = _primary_clinic_id()
        if not patient_id or clinic_id is None:
            await message.answer(i18n.t("patient.recommendations.patient_resolution_failed", _locale()))
            return
        rows = await care_commerce_service.list_patient_orders(clinic_id=clinic_id, patient_id=patient_id)
        if not rows:
            await message.answer(i18n.t("patient.care.orders.empty", _locale()))
            return
        lines = [i18n.t("patient.care.orders.title", _locale())]
        for row in rows[:8]:
            lines.append(i18n.t("patient.care.orders.item", _locale()).format(care_order_id=row.care_order_id, status=row.status, amount=row.total_amount, currency=row.currency_code, branch_id=(row.pickup_branch_id or "-")))
        await message.answer("\n".join(lines))

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
        await _render_resume_panel(message, actor_id=message.from_user.id, session_id=session.booking_session_id, clinic_id=clinic_id)

    @router.message(Command("my_booking"))
    async def my_booking_entry(message: Message) -> None:
        if not message.from_user:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            await message.answer(i18n.t("patient.booking.unavailable", _locale()))
            return
        session = await booking_flow.start_or_resume_existing_booking_session(clinic_id=clinic_id, telegram_user_id=message.from_user.id)
        session_by_user[message.from_user.id] = session.booking_session_id
        mode_by_user[message.from_user.id] = "existing_lookup_contact"
        await _send_or_edit_panel(
            actor_id=message.from_user.id,
            message=message,
            session_id=session.booking_session_id,
            text=i18n.t("patient.booking.my.contact_prompt", _locale()),
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
        _, _, callback_session_id, service_id = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        session = await booking_flow.update_service(booking_session_id=callback_session_id, service_id=service_id)
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
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        if not session_by_user.get(callback.from_user.id):
            await callback.answer(i18n.t("patient.booking.session.missing", _locale()), show_alert=True)
            return
        _, _, callback_session_id, doctor_token = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        if doctor_token == "any":
            await booking_flow.update_doctor_preference(booking_session_id=callback_session_id, doctor_preference_type="any", doctor_id=None)
        else:
            await booking_flow.update_doctor_preference(
                booking_session_id=callback_session_id,
                doctor_preference_type="specific",
                doctor_id=doctor_token,
            )
        await _render_slot_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)

    @router.callback_query(F.data.startswith("book:slot:"))
    async def select_slot(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        locale = _locale()
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        if not session_by_user.get(callback.from_user.id):
            await callback.answer(i18n.t("patient.booking.session.missing", locale), show_alert=True)
            return
        _, _, callback_session_id, slot_id = callback.data.split(":", 3)
        if not await booking_flow.validate_active_session_callback(clinic_id=clinic_id, telegram_user_id=callback.from_user.id, callback_session_id=callback_session_id):
            await callback.answer(i18n.t("patient.booking.callback.stale", _locale()), show_alert=True)
            return
        selected = await booking_flow.select_slot(booking_session_id=callback_session_id, slot_id=slot_id)
        if isinstance(selected, (SlotUnavailableOutcome, ConflictOutcome)):
            await callback.answer(i18n.t("patient.booking.slot.unavailable", locale), show_alert=True)
            await _render_slot_panel(callback, actor_id=callback.from_user.id, session_id=callback_session_id)
            return
        mode_by_user[callback.from_user.id] = "new_booking_contact"
        contact_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=i18n.t("patient.booking.contact.share", locale), request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await _send_or_edit_panel(
            actor_id=callback.from_user.id,
            message=callback,
            session_id=callback_session_id,
            text=i18n.t("patient.booking.contact.prompt", locale),
            reply_keyboard=contact_keyboard,
        )

    @router.callback_query(F.data.startswith("mybk:reschedule:"))
    async def request_reschedule(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        _, _, callback_session_id, booking_id = callback.data.split(":", 3)
        result = await booking_flow.request_reschedule(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
            booking_id=booking_id,
        )
        if isinstance(result, OrchestrationSuccess):
            card = booking_flow.build_booking_card(booking=result.entity)
            await _send_or_edit_panel(actor_id=callback.from_user.id, message=callback, session_id=session_by_user.get(callback.from_user.id, ""), text=_render_booking_card_text(card, locale=_locale()))
            return
        await callback.answer(i18n.t("patient.booking.finalize.invalid_state", _locale()), show_alert=True)

    @router.callback_query(F.data.startswith("rem:"))
    async def reminder_action_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        callback_parts = callback.data.split(":", 2)
        if len(callback_parts) != 3:
            await callback.answer(i18n.t("patient.reminder.action.invalid", _locale()), show_alert=True)
            return
        _, action, reminder_id = callback_parts
        if action not in {"ack", "confirm", "reschedule", "cancel"}:
            await callback.answer(i18n.t("patient.reminder.action.invalid", _locale()), show_alert=True)
            return
        message_id = str(callback.message.message_id) if callback.message else None
        outcome = await reminder_actions.handle_action(
            reminder_id=reminder_id,
            action=action,
            provider_message_id=message_id,
        )
        if outcome.kind == "accepted":
            if callback.message:
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
            await callback.answer(i18n.t("patient.reminder.action.accepted", _locale()), show_alert=False)
            return
        if outcome.kind == "stale":
            await callback.answer(i18n.t("patient.reminder.action.stale", _locale()), show_alert=True)
            return
        await callback.answer(i18n.t("patient.reminder.action.invalid", _locale()), show_alert=True)

    @router.callback_query(F.data.startswith("mybk:waitlist:"))
    async def join_waitlist(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        _, _, callback_session_id, booking_id = callback.data.split(":", 3)
        created = await booking_flow.join_earlier_slot_waitlist(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
            booking_id=booking_id,
        )
        if isinstance(created, OrchestrationSuccess):
            await _send_or_edit_panel(actor_id=callback.from_user.id, message=callback, session_id=session_by_user.get(callback.from_user.id, ""), text=i18n.t("patient.booking.waitlist.created", _locale()))
            return
        await callback.answer(i18n.t("patient.booking.finalize.invalid_state", _locale()), show_alert=True)

    @router.callback_query(F.data.startswith("mybk:cancel_prompt:"))
    async def cancel_prompt(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        _, _, callback_session_id, booking_id = callback.data.split(":", 3)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=i18n.t("common.yes", _locale()), callback_data=f"mybk:cancel_confirm:{callback_session_id}:{booking_id}")],
                [InlineKeyboardButton(text=i18n.t("common.no", _locale()), callback_data=f"mybk:cancel_abort:{callback_session_id}:{booking_id}")],
            ]
        )
        await _send_or_edit_panel(actor_id=callback.from_user.id, message=callback, session_id=session_by_user.get(callback.from_user.id, ""), text=i18n.t("patient.booking.cancel.confirm", _locale()), keyboard=keyboard)

    @router.callback_query(F.data.startswith("mybk:cancel_abort:"))
    async def cancel_abort(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        await callback.answer(i18n.t("patient.booking.cancel.aborted", _locale()), show_alert=True)

    @router.callback_query(F.data.startswith("mybk:cancel_confirm:"))
    async def cancel_confirm(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        clinic_id = _primary_clinic_id()
        if not clinic_id:
            return
        _, _, callback_session_id, booking_id = callback.data.split(":", 3)
        result = await booking_flow.cancel_booking(
            clinic_id=clinic_id,
            telegram_user_id=callback.from_user.id,
            callback_session_id=callback_session_id,
            booking_id=booking_id,
        )
        if isinstance(result, OrchestrationSuccess):
            card = booking_flow.build_booking_card(booking=result.entity)
            await _send_or_edit_panel(actor_id=callback.from_user.id, message=callback, session_id=session_by_user.get(callback.from_user.id, ""), text=_render_booking_card_text(card, locale=_locale()))
            return
        await callback.answer(i18n.t("patient.booking.finalize.invalid_state", _locale()), show_alert=True)

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
        mode = mode_by_user.get(actor_id, "new_booking_contact")
        if mode == "existing_lookup_contact":
            clinic_id = _primary_clinic_id()
            if not clinic_id:
                return
            result = await booking_flow.resolve_existing_booking_by_contact(clinic_id=clinic_id, telegram_user_id=actor_id, phone=phone)
            await _show_existing_booking_result(message, actor_id=actor_id, result=result)
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

    async def _render_resume_panel(message: Message | CallbackQuery, *, actor_id: int, session_id: str, clinic_id: str) -> None:
        resume = await booking_flow.determine_resume_panel(booking_session_id=session_id)
        if resume is None:
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=session_id, text=i18n.t("patient.booking.session.missing", _locale()))
            return
        if resume.panel_key == "service_selection":
            await _render_service_panel(message, actor_id=actor_id, session_id=session_id, clinic_id=clinic_id)
            return
        if resume.panel_key == "doctor_preference_selection":
            await _render_doctor_pref_panel(
                message,
                actor_id=actor_id,
                session_id=session_id,
                clinic_id=resume.booking_session.clinic_id,
                branch_id=resume.booking_session.branch_id,
            )
            return
        if resume.panel_key == "slot_selection":
            await _render_slot_panel(message, actor_id=actor_id, session_id=session_id)
            return
        if resume.panel_key == "contact_collection":
            mode_by_user[actor_id] = "new_booking_contact"
            contact_keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=i18n.t("patient.booking.contact.share", _locale()), request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await _send_or_edit_panel(
                actor_id=actor_id,
                message=message,
                session_id=session_id,
                text=i18n.t("patient.booking.contact.prompt", _locale()),
                reply_keyboard=contact_keyboard,
            )
            return
        if resume.panel_key == "review_finalize":
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=session_id, text=i18n.t("patient.booking.resume.review", _locale()))
            return
        await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=session_id, text=i18n.t("patient.booking.resume.terminal", _locale()))

    def _render_booking_card_text(card: BookingCardView, *, locale: str) -> str:
        return i18n.t("patient.booking.card", locale).format(
            booking_id=card.booking_id,
            doctor=card.doctor_label,
            service=card.service_label,
            datetime=card.datetime_label,
            branch=card.branch_label,
            status=i18n.t(card.status_label, locale),
            next_step=i18n.t(card.next_step_key, locale),
        )

    async def _show_existing_booking_result(message: Message, *, actor_id: int, result: BookingControlResolutionResult) -> None:
        locale = _locale()
        effective_session_id = result.booking_session.booking_session_id if result.booking_session else session_by_user.get(actor_id, "")
        if effective_session_id:
            session_by_user[actor_id] = effective_session_id
        if result.kind == "ambiguous_escalated":
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=effective_session_id, text=i18n.t("patient.booking.escalated", locale))
            return
        if result.kind == "no_match":
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=effective_session_id, text=i18n.t("patient.booking.my.no_match", locale))
            return
        if result.kind != "exact_match" or not result.bookings:
            await _send_or_edit_panel(actor_id=actor_id, message=message, session_id=effective_session_id, text=i18n.t("patient.booking.finalize.invalid_state", locale))
            return
        booking = result.bookings[0]
        card = booking_flow.build_booking_card(booking=booking)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=i18n.t("patient.booking.my.reschedule", locale), callback_data=f"mybk:reschedule:{effective_session_id}:{booking.booking_id}")],
                [InlineKeyboardButton(text=i18n.t("patient.booking.my.earlier_slot", locale), callback_data=f"mybk:waitlist:{effective_session_id}:{booking.booking_id}")],
                [InlineKeyboardButton(text=i18n.t("patient.booking.my.cancel", locale), callback_data=f"mybk:cancel_prompt:{effective_session_id}:{booking.booking_id}")],
            ]
        )
        await _send_or_edit_panel(
            actor_id=actor_id,
            message=message,
            session_id=effective_session_id,
            text=_render_booking_card_text(card, locale=locale),
            keyboard=keyboard,
        )

    return router
