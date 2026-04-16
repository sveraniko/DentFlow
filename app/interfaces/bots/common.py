from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.common.i18n import I18nService
from app.common.panels import Panel, PanelRenderer


def build_role_router(*, role_key: str, i18n: I18nService, locale: str = "ru") -> Router:
    router = Router(name=f"{role_key}_router")

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        panel = Panel(
            panel_id=f"{role_key}:home",
            text=f"{i18n.t(f'role.{role_key}.home', locale)}\n{i18n.t('common.placeholder', locale)}",
        )
        await message.answer(PanelRenderer.render(panel))

    return router
