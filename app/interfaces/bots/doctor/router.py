from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.application.access import AccessResolver
from app.application.search.service import HybridSearchService
from app.common.i18n import I18nService
from app.domain.access_identity.models import RoleCode
from app.interfaces.bots.common import build_role_router, guard_roles
from app.interfaces.bots.search_handlers import run_doctor_search, run_patient_search, run_service_search


def make_router(i18n: I18nService, access_resolver: AccessResolver, search_service: HybridSearchService, *, default_locale: str) -> Router:
    router = build_role_router(
        role_key="doctor",
        i18n=i18n,
        locale=default_locale,
        access_resolver=access_resolver,
        required_role=RoleCode.DOCTOR,
    )

    @router.message(Command("search_patient"))
    async def search_patient(message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.DOCTOR},
            fallback_locale=default_locale,
        )
        if not allowed or not message.from_user or not message.text:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor:
            return
        query = message.text.replace("/search_patient", "", 1).strip()
        if not query:
            await message.answer("Usage: /search_patient <query>")
            return
        await message.answer(await run_patient_search(service=search_service, clinic_id=actor.clinic_id, query=query))

    @router.message(Command("search_doctor"))
    async def search_doctor(message: Message) -> None:
        if not message.from_user or not message.text:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor:
            return
        query = message.text.replace("/search_doctor", "", 1).strip()
        if not query:
            await message.answer("Usage: /search_doctor <query>")
            return
        await message.answer(await run_doctor_search(service=search_service, clinic_id=actor.clinic_id, query=query))

    @router.message(Command("search_service"))
    async def search_service(message: Message) -> None:
        if not message.from_user or not message.text:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor:
            return
        query = message.text.replace("/search_service", "", 1).strip()
        if not query:
            await message.answer("Usage: /search_service <query>")
            return
        await message.answer(
            await run_service_search(service=search_service, clinic_id=actor.clinic_id, query=query, locale=default_locale)
        )

    return router
