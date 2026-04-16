from aiogram import Router

from app.common.i18n import I18nService
from app.interfaces.bots.common import build_role_router


def make_router(i18n: I18nService) -> Router:
    return build_role_router(role_key="doctor", i18n=i18n)
