from aiogram import Router

from app.application.access import AccessResolver
from app.common.i18n import I18nService
from app.domain.access_identity.models import RoleCode
from app.interfaces.bots.common import build_role_router


def make_router(i18n: I18nService, access_resolver: AccessResolver) -> Router:
    return build_role_router(role_key="doctor", i18n=i18n, access_resolver=access_resolver, required_role=RoleCode.DOCTOR)
