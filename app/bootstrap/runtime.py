from pathlib import Path

from aiogram import Dispatcher

from app.common.i18n import I18nService
from app.config.settings import Settings
from app.interfaces.bots.admin.router import make_router as make_admin_router
from app.interfaces.bots.doctor.router import make_router as make_doctor_router
from app.interfaces.bots.owner.router import make_router as make_owner_router
from app.interfaces.bots.patient.router import make_router as make_patient_router


class RuntimeRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.i18n = I18nService(Path("locales"), default_locale=settings.app.default_locale)

    def build_dispatcher(self) -> Dispatcher:
        dispatcher = Dispatcher()
        dispatcher.include_router(make_patient_router(self.i18n))
        dispatcher.include_router(make_admin_router(self.i18n))
        dispatcher.include_router(make_doctor_router(self.i18n))
        dispatcher.include_router(make_owner_router(self.i18n))
        return dispatcher
