import asyncio
from pathlib import Path

from aiogram import Dispatcher

from app.application.access import AccessResolver
from app.application.booking import (
    AdminEscalationService,
    AvailabilitySlotService,
    BookingPatientResolutionService,
    BookingService,
    BookingSessionService,
    SlotHoldService,
    WaitlistService,
)
from app.application.clinic_reference import ClinicReferenceService
from app.application.policy import PolicyResolver
from app.common.i18n import I18nService
from app.config.settings import Settings
from app.infrastructure.db.booking_repository import DbBookingRepository
from app.infrastructure.db.patient_repository import find_patients_by_exact_contact, find_patients_by_external_id
from app.infrastructure.db.repositories import DbAccessRepository, DbClinicReferenceRepository, DbPolicyRepository
from app.interfaces.bots.admin.router import make_router as make_admin_router
from app.interfaces.bots.doctor.router import make_router as make_doctor_router
from app.interfaces.bots.owner.router import make_router as make_owner_router
from app.interfaces.bots.patient.router import make_router as make_patient_router


class RuntimeRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.i18n = I18nService(Path("locales"), default_locale=settings.app.default_locale)

        self.clinic_reference_repository = asyncio.run(DbClinicReferenceRepository.load(settings.db))
        self.access_repository = asyncio.run(DbAccessRepository.load(settings.db))
        self.policy_repository = asyncio.run(DbPolicyRepository.load(settings.db))
        self.booking_repository = DbBookingRepository(settings.db)

        self.reference_service = ClinicReferenceService(self.clinic_reference_repository)
        self.access_resolver = AccessResolver(self.access_repository)
        self.policy_resolver = PolicyResolver(self.policy_repository)
        self.booking_session_service = BookingSessionService(self.booking_repository)
        self.availability_slot_service = AvailabilitySlotService(self.booking_repository)
        self.slot_hold_service = SlotHoldService(self.booking_repository)
        self.booking_service = BookingService(self.booking_repository)
        self.waitlist_service = WaitlistService(self.booking_repository)
        self.admin_escalation_service = AdminEscalationService(self.booking_repository)
        self.booking_patient_resolution_service = BookingPatientResolutionService(_RuntimePatientFinder(settings))

    def build_dispatcher(self) -> Dispatcher:
        dispatcher = Dispatcher()
        dispatcher.include_router(make_patient_router(self.i18n, default_locale=self.settings.app.default_locale))
        dispatcher.include_router(
            make_admin_router(
                self.i18n,
                self.access_resolver,
                self.reference_service,
                default_locale=self.settings.app.default_locale,
            )
        )
        dispatcher.include_router(make_doctor_router(self.i18n, self.access_resolver, default_locale=self.settings.app.default_locale))
        dispatcher.include_router(make_owner_router(self.i18n, self.access_resolver, default_locale=self.settings.app.default_locale))
        return dispatcher


class _RuntimePatientFinder:
    def __init__(self, settings: Settings) -> None:
        self._db = settings.db

    async def find_patients_by_exact_contact(self, *, contact_type: str, contact_value: str) -> list[dict]:
        return await find_patients_by_exact_contact(self._db, contact_type=contact_type, contact_value=contact_value)

    async def find_patients_by_external_id(self, *, external_system: str, external_id: str) -> list[dict]:
        return await find_patients_by_external_id(self._db, external_system=external_system, external_id=external_id)
