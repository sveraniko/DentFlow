from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.application.access import AccessResolver
from app.application.booking.telegram_flow import BookingPatientFlowService
from app.application.clinic_reference import ClinicReferenceService
from app.common.i18n import I18nService
from app.domain.access_identity.models import RoleCode
from app.interfaces.bots.common import guard_roles, resolve_locale


def _clinic_locale(reference_service: ClinicReferenceService, clinic_id: str) -> str | None:
    clinic = reference_service.get_clinic(clinic_id)
    return clinic.default_locale if clinic else None


def make_router(
    i18n: I18nService,
    access_resolver: AccessResolver,
    reference_service: ClinicReferenceService,
    booking_flow: BookingPatientFlowService,
    *,
    default_locale: str,
) -> Router:
    router = Router(name="admin_router")

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
        for booking in bookings:
            card = booking_flow.build_booking_card(booking=booking)
            lines.append(
                i18n.t("admin.booking.new.item", locale).format(
                    booking_id=booking.booking_id,
                    status=i18n.t(card.status_label, locale),
                    doctor=card.doctor_label,
                    service=card.service_label,
                    dt=card.datetime_label,
                )
            )
        await message.answer("\n".join(lines))

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
        card = await booking_flow.get_admin_booking_detail(booking_id=parts[1])
        if card is None:
            await message.answer(i18n.t("admin.booking.open.missing", locale))
            return
        await message.answer(
            i18n.t("admin.booking.open.panel", locale).format(
                booking_id=card.booking_id,
                doctor=card.doctor_label,
                service=card.service_label,
                datetime=card.datetime_label,
                branch=card.branch_label,
                status=i18n.t(card.status_label, locale),
                next_step=i18n.t(card.next_step_key, locale),
            )
        )

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
