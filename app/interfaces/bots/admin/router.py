from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.application.access import AccessResolver
from app.application.care_commerce import CareCommerceService
from app.application.booking.telegram_flow import BookingPatientFlowService
from app.application.clinic_reference import ClinicReferenceService
from app.application.search.service import HybridSearchService
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

    async def _encode_booking_callback(*, booking_id: str, action: CardAction, page_or_index: str) -> str:
        if card_callback_codec is None:
            return f"adminbk:{page_or_index}:{booking_id}"
        return await card_callback_codec.encode(
            CardCallback(
                profile=CardProfile.BOOKING,
                entity_type=EntityType.BOOKING,
                entity_id=booking_id,
                action=action,
                mode=CardMode.EXPANDED,
                source_context=SourceContext.BOOKING_LIST,
                source_ref="admin.booking.card",
                page_or_index=page_or_index,
                state_token=booking_id,
            )
        )

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

    async def _admin_booking_keyboard(*, booking, locale: str) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        if booking.status == "pending_confirmation":
            rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.confirm", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.CONFIRM, page_or_index="confirm"))])
        if booking.status in {"confirmed", "reschedule_requested"}:
            rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.arrived", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.CHECKED_IN, page_or_index="checked_in"))])
        if booking.status not in {"completed", "canceled", "no_show"}:
            rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.reschedule", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.RESCHEDULE, page_or_index="reschedule"))])
            rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.cancel", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.CANCEL, page_or_index="cancel"))])
        rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.patient", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.OPEN_PATIENT, page_or_index="open_patient"))])
        rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.chart", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.OPEN_CHART, page_or_index="open_chart"))])
        rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.recommendation", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.OPEN_RECOMMENDATION, page_or_index="open_recommendation"))])
        rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.care_order", locale), callback_data=await _encode_booking_callback(booking_id=booking.booking_id, action=CardAction.OPEN_CARE_ORDER, page_or_index="open_care_order"))])
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
    async def search_service(message: Message) -> None:
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
        await message.answer(_render_admin_booking_panel(booking=booking, locale=locale), reply_markup=await _admin_booking_keyboard(booking=booking, locale=locale))

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
        if decoded.source_context != SourceContext.BOOKING_LIST or decoded.profile != CardProfile.BOOKING:
            return
        booking = await booking_flow.reads.get_booking(decoded.entity_id)
        if booking is None:
            await callback.answer(i18n.t("admin.booking.open.missing", locale), show_alert=True)
            return
        if decoded.page_or_index == "open_booking":
            await callback.message.edit_text(_render_admin_booking_panel(booking=booking, locale=locale), reply_markup=await _admin_booking_keyboard(booking=booking, locale=locale))
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
            await callback.message.edit_text(
                i18n.t("doctor.patient.quick.card", locale).format(
                    patient_id=booking.patient_id,
                    display_name=booking.patient_id,
                    patient_number="-",
                    phone_hint="-",
                    has_photo=i18n.t("common.no", locale),
                    flags="-",
                    next_booking=booking.booking_id,
                ),
                reply_markup=await _admin_linked_back_keyboard(booking_id=booking.booking_id, locale=locale),
            )
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
        await callback.message.edit_text(_render_admin_booking_panel(booking=booking, locale=locale), reply_markup=await _admin_booking_keyboard(booking=booking, locale=locale))

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
