from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.application.access import AccessResolver
from app.common.i18n import I18nService
from app.common.panels import Panel, PanelRenderer
from app.domain.access_identity.models import RoleCode


async def resolve_locale(
    message: Message,
    *,
    access_resolver: AccessResolver | None,
    fallback_locale: str,
) -> str:
    if access_resolver and message.from_user:
        actor_context = access_resolver.resolve_actor_context(message.from_user.id)
        if actor_context and actor_context.locale:
            return actor_context.locale
    return fallback_locale


async def guard_roles(
    message: Message,
    *,
    i18n: I18nService,
    access_resolver: AccessResolver,
    allowed_roles: set[RoleCode],
    fallback_locale: str,
) -> bool:
    if not message.from_user:
        return False
    actor_context = access_resolver.resolve_actor_context(message.from_user.id)
    decision = access_resolver.check_roles(actor_context, allowed_roles)
    locale = actor_context.locale if actor_context and actor_context.locale else fallback_locale
    if decision.allowed:
        return True
    await message.answer(i18n.t(decision.reason, locale))
    return False


def build_role_router(
    *,
    role_key: str,
    i18n: I18nService,
    locale: str = "ru",
    access_resolver: AccessResolver | None = None,
    required_role: RoleCode | None = None,
) -> Router:
    router = Router(name=f"{role_key}_router")

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        if required_role and access_resolver:
            allowed = await guard_roles(
                message,
                i18n=i18n,
                access_resolver=access_resolver,
                allowed_roles={required_role},
                fallback_locale=locale,
            )
            if not allowed:
                return
        resolved_locale = await resolve_locale(message, access_resolver=access_resolver, fallback_locale=locale)
        panel = Panel(
            panel_id=f"{role_key}:home",
            text=f"{i18n.t(f'role.{role_key}.home', resolved_locale)}\n{i18n.t('common.placeholder', resolved_locale)}",
        )
        await message.answer(PanelRenderer.render(panel))

    return router
