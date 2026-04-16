from pathlib import Path

from aiogram import Dispatcher

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.application.policy import InMemoryPolicyRepository, PolicyResolver
from app.bootstrap.seed import SeedBootstrap
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

        self.clinic_reference_repository = InMemoryClinicReferenceRepository()
        self.access_repository = InMemoryAccessRepository()
        self.policy_repository = InMemoryPolicyRepository()

        SeedBootstrap(
            clinic_reference_repository=self.clinic_reference_repository,
            access_repository=self.access_repository,
            policy_repository=self.policy_repository,
        ).load_from_file(Path("seeds/stack1_seed.json"))

        self.reference_service = ClinicReferenceService(self.clinic_reference_repository)
        self.access_resolver = AccessResolver(self.access_repository)
        self.policy_resolver = PolicyResolver(self.policy_repository)

    def build_dispatcher(self) -> Dispatcher:
        dispatcher = Dispatcher()
        dispatcher.include_router(make_patient_router(self.i18n))
        dispatcher.include_router(make_admin_router(self.i18n, self.access_resolver, self.reference_service))
        dispatcher.include_router(make_doctor_router(self.i18n, self.access_resolver))
        dispatcher.include_router(make_owner_router(self.i18n, self.access_resolver))
        return dispatcher
