from types import SimpleNamespace

import pytest

pytest.importorskip("aiogram")

from app.application.access import ActorContext
from app.interfaces.bots.common import resolve_locale


class _Access:
    def __init__(self, context):
        self._context = context

    def resolve_actor_context(self, _):
        return self._context


@pytest.mark.asyncio
async def test_locale_fallback_chain_actor_then_clinic_then_default() -> None:
    msg = SimpleNamespace(from_user=SimpleNamespace(id=1))

    actor_locale = await resolve_locale(
        msg,
        access_resolver=_Access(ActorContext(actor_id="a", clinic_id="c", role_codes=frozenset(), locale="en")),
        fallback_locale="ru",
        clinic_locale_getter=lambda _: "ka",
    )
    assert actor_locale == "en"

    clinic_locale = await resolve_locale(
        msg,
        access_resolver=_Access(ActorContext(actor_id="a", clinic_id="c", role_codes=frozenset(), locale=None)),
        fallback_locale="ru",
        clinic_locale_getter=lambda _: "ka",
    )
    assert clinic_locale == "ka"

    default_locale = await resolve_locale(msg, access_resolver=_Access(None), fallback_locale="ru")
    assert default_locale == "ru"
