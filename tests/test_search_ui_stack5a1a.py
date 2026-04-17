from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.application.access import AccessDecision, ActorContext
from app.common.i18n import I18nService
from app.domain.access_identity.models import RoleCode
from app.interfaces.bots.admin.router import make_router as make_admin_router
from app.interfaces.bots.doctor.router import make_router as make_doctor_router


class _Message:
    def __init__(self, text: str, user_id: int = 10):
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _AccessResolverStub:
    def __init__(self, *, allowed_roles: set[RoleCode], locale: str = "en") -> None:
        self._allowed_roles = allowed_roles
        self._locale = locale

    def resolve_actor_context(self, telegram_user_id: int) -> ActorContext | None:
        return ActorContext(actor_id="a1", clinic_id="c1", role_codes=frozenset(self._allowed_roles), locale=self._locale)

    def check_roles(self, actor_context: ActorContext | None, allowed_roles: set[RoleCode]) -> AccessDecision:
        if actor_context and actor_context.role_codes.intersection(allowed_roles):
            return AccessDecision(allowed=True, reason="access.allowed")
        return AccessDecision(allowed=False, reason="access.denied.role")


class _SearchStub:
    def __init__(self) -> None:
        self.calls = 0

    async def search_patients(self, query):
        self.calls += 1
        return SimpleNamespace(exact_matches=[], suggestions=[])

    async def search_doctors(self, query):
        self.calls += 1
        return []

    async def search_services(self, query):
        self.calls += 1
        return []


class _ClinicReferenceStub:
    def get_clinic(self, clinic_id):
        return None


class _BookingFlowStub:
    pass


def _handler(router, name: str):
    return next(h.callback for h in router.message.handlers if h.callback.__name__ == name)


def test_admin_search_patient_stops_after_failed_guard() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    search = _SearchStub()
    router = make_admin_router(
        i18n=i18n,
        access_resolver=_AccessResolverStub(allowed_roles={RoleCode.DOCTOR}),
        reference_service=_ClinicReferenceStub(),
        booking_flow=_BookingFlowStub(),
        search_service=search,
        default_locale="en",
    )
    cb = _handler(router, "search_patient")
    message = _Message("/search_patient ivan")
    asyncio.run(cb(message))
    assert search.calls == 0
    assert message.answers and message.answers[0] == i18n.t("access.denied.role", "en")


def test_admin_search_doctor_and_service_stop_after_failed_guard() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    search = _SearchStub()
    router = make_admin_router(
        i18n=i18n,
        access_resolver=_AccessResolverStub(allowed_roles={RoleCode.DOCTOR}),
        reference_service=_ClinicReferenceStub(),
        booking_flow=_BookingFlowStub(),
        search_service=search,
        default_locale="en",
    )
    for command_name, text in [("search_doctor", "/search_doctor ortho"), ("search_service", "/search_service clean")]:
        cb = _handler(router, command_name)
        message = _Message(text)
        asyncio.run(cb(message))
        assert message.answers and message.answers[0] == i18n.t("access.denied.role", "en")
    assert search.calls == 0


def test_doctor_search_commands_are_guarded_and_localized() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    search = _SearchStub()
    router = make_doctor_router(
        i18n=i18n,
        access_resolver=_AccessResolverStub(allowed_roles={RoleCode.ADMIN}, locale="ru"),
        search_service=search,
        default_locale="en",
    )
    for command_name, text in [("search_patient", "/search_patient ivan"), ("search_doctor", "/search_doctor ortho"), ("search_service", "/search_service clean")]:
        cb = _handler(router, command_name)
        message = _Message(text)
        asyncio.run(cb(message))
        assert message.answers and message.answers[0] == i18n.t("access.denied.role", "ru")
    assert search.calls == 0
