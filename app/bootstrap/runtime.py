import asyncio
from pathlib import Path

from aiogram import Dispatcher

from app.application.access import AccessResolver
from app.application.admin.workdesk import AdminWorkdeskReadService
from app.application.booking import (
    AdminEscalationService,
    AvailabilitySlotService,
    BookingOrchestrationService,
    BookingPatientResolutionService,
    BookingSessionStateService,
    BookingService,
    BookingSessionService,
    BookingStateService,
    SlotHoldService,
    SlotHoldStateService,
    BookingPatientFlowService,
    WaitlistStateService,
    WaitlistService,
)
from app.application.clinic_reference import ClinicReferenceService
from app.application.care_commerce import CareCommerceService
from app.application.owner import OwnerAnalyticsService
from app.application.clinical import ClinicalChartService
from app.application.communication import BookingReminderPlanner, BookingReminderService, ReminderActionService
from app.application.policy import PolicyResolver
from app.application.recommendation import RecommendationService
from app.application.search.service import HybridSearchService
from app.application.voice import SpeechToTextService, VoiceSearchModeStore
from app.application.voice.provider import SpeechToTextProvider
from app.common.i18n import I18nService
from app.config.settings import Settings, SpeechToTextConfig
from app.infrastructure.db.booking_repository import DbBookingRepository
from app.infrastructure.db.communication_repository import DbReminderJobRepository
from app.infrastructure.db.care_commerce_repository import DbCareCommerceRepository
from app.infrastructure.db.clinical_repository import DbClinicalRepository
from app.infrastructure.db.patient_repository import (
    DbCanonicalPatientCreator,
    DbDoctorPatientReader,
    DbPatientRegistryRepository,
    DbPatientRegistryService,
    DbPatientPreferenceReader,
    find_patients_by_exact_contact,
    find_patients_by_external_id,
)
from app.infrastructure.db.repositories import DbAccessRepository, DbClinicReferenceRepository, DbPolicyRepository
from app.infrastructure.db.recommendation_repository import DbRecommendationRepository
from app.infrastructure.search.meili_backend import MeiliSearchBackend
from app.infrastructure.search.meili_client import HttpMeiliClient
from app.infrastructure.search.postgres_backend import PostgresSearchBackend
from app.infrastructure.cache import build_card_runtime_redis
from app.infrastructure.speech.disabled_provider import DisabledSpeechToTextProvider
from app.infrastructure.speech.fake_provider import FakeSpeechToTextProvider
from app.infrastructure.speech.openai_provider import OpenAITranscriptionConfig, OpenAISpeechToTextProvider
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
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
        self.reminder_repository = DbReminderJobRepository(settings.db)
        self.patient_preference_reader = DbPatientPreferenceReader(settings.db)
        self.doctor_patient_reader = DbDoctorPatientReader(settings.db)
        self.patient_registry_repository = asyncio.run(DbPatientRegistryRepository.load(settings.db))
        self.clinical_repository = DbClinicalRepository(settings.db)
        self.recommendation_repository = DbRecommendationRepository(settings.db)
        self.care_commerce_repository = DbCareCommerceRepository(settings.db)
        self.patient_registry_service = DbPatientRegistryService(self.patient_registry_repository)
        self.card_runtime_store = CardRuntimeStateStore(redis_client=build_card_runtime_redis(settings))
        self.card_runtime = CardRuntimeCoordinator(store=self.card_runtime_store)
        self.card_callback_codec = CardCallbackCodec(runtime=self.card_runtime)

        self.reference_service = ClinicReferenceService(self.clinic_reference_repository)
        self.clinical_chart_service = ClinicalChartService(self.clinical_repository)
        self.access_resolver = AccessResolver(self.access_repository)
        self.recommendation_service = RecommendationService(self.recommendation_repository)
        self.care_commerce_service = CareCommerceService(self.care_commerce_repository)
        self.policy_resolver = PolicyResolver(self.policy_repository)
        self.booking_session_service = BookingSessionService(self.booking_repository)
        self.availability_slot_service = AvailabilitySlotService(self.booking_repository)
        self.slot_hold_service = SlotHoldService(self.booking_repository)
        self.booking_service = BookingService(self.booking_repository)
        self.waitlist_service = WaitlistService(self.booking_repository)
        self.admin_escalation_service = AdminEscalationService(self.booking_repository)
        self.booking_patient_resolution_service = BookingPatientResolutionService(_RuntimePatientFinder(settings))
        self.booking_session_state_service = BookingSessionStateService(self.booking_repository)
        self.slot_hold_state_service = SlotHoldStateService(self.booking_repository)
        self.booking_state_service = BookingStateService(self.booking_repository)
        self.waitlist_state_service = WaitlistStateService(self.booking_repository)
        self.booking_reminder_service = BookingReminderService(
            repository=self.reminder_repository,
            planner=BookingReminderPlanner(self.policy_resolver),
            policy_resolver=self.policy_resolver,
            patient_preference_reader=self.patient_preference_reader,
        )
        self.booking_orchestration_service = BookingOrchestrationService(
            repository=self.booking_repository,
            booking_session_state_service=self.booking_session_state_service,
            slot_hold_state_service=self.slot_hold_state_service,
            booking_state_service=self.booking_state_service,
            waitlist_state_service=self.waitlist_state_service,
            patient_resolution_service=self.booking_patient_resolution_service,
            policy_resolver=self.policy_resolver,
            reminder_service=self.booking_reminder_service,
        )
        self.booking_patient_flow_service = BookingPatientFlowService(
            orchestration=self.booking_orchestration_service,
            reads=self.booking_repository,
            reference=self.reference_service,
            patient_creator=DbCanonicalPatientCreator(settings.db),
        )
        self.reminder_action_service = ReminderActionService(
            repository=self.reminder_repository,
            transaction_repository=self.booking_repository,
            booking_orchestration=self.booking_orchestration_service,
        )
        self.voice_mode_store = VoiceSearchModeStore(runtime=self.card_runtime)
        self.owner_analytics_service = OwnerAnalyticsService(settings.db)
        self.admin_workdesk_service = AdminWorkdeskReadService(settings.db, app_default_timezone=settings.app.default_timezone)
        stt_provider = build_speech_to_text_provider(settings.stt)
        self.speech_to_text_service = SpeechToTextService(
            provider=stt_provider,
            timeout_sec=settings.stt.timeout_sec,
            confidence_threshold=settings.stt.confidence_threshold,
            language_hint=settings.stt.language_hint,
        )

        self.postgres_search_backend = PostgresSearchBackend(settings.db)
        self.meili_search_backend = None
        if settings.search.enabled:
            meili_client = HttpMeiliClient(
                endpoint=settings.search.meili_endpoint,
                api_key=settings.search.meili_api_key,
                timeout_sec=settings.search.meili_timeout_sec,
            )
            self.meili_search_backend = MeiliSearchBackend(
                client=meili_client,
                patient_index=f"{settings.search.meili_index_prefix}_patients",
                doctor_index=f"{settings.search.meili_index_prefix}_doctors",
                service_index=f"{settings.search.meili_index_prefix}_services",
            )
        self.search_service = HybridSearchService(
            strict_backend=self.postgres_search_backend,
            meili_backend=self.meili_search_backend,
            postgres_backend=self.postgres_search_backend,
        )

    def build_dispatcher(self) -> Dispatcher:
        dispatcher = Dispatcher()
        dispatcher.include_router(
            make_patient_router(
                self.i18n,
                self.booking_patient_flow_service,
                self.reference_service,
                reminder_actions=self.reminder_action_service,
                recommendation_service=self.recommendation_service,
                care_commerce_service=self.care_commerce_service,
                recommendation_repository=self.recommendation_repository,
                default_locale=self.settings.app.default_locale,
                card_runtime=self.card_runtime,
                card_callback_codec=self.card_callback_codec,
            )
        )
        dispatcher.include_router(
            make_admin_router(
                self.i18n,
                self.access_resolver,
                self.reference_service,
                self.booking_patient_flow_service,
                search_service=self.search_service,
                stt_service=self.speech_to_text_service,
                voice_mode_store=self.voice_mode_store,
                care_commerce_service=self.care_commerce_service,
                admin_workdesk=self.admin_workdesk_service,
                default_locale=self.settings.app.default_locale,
                max_voice_duration_sec=self.settings.stt.max_voice_duration_sec,
                max_voice_file_size_bytes=self.settings.stt.max_voice_file_size_bytes,
                voice_mode_ttl_sec=self.settings.stt.mode_ttl_sec,
                card_runtime=self.card_runtime,
                card_callback_codec=self.card_callback_codec,
            )
        )
        dispatcher.include_router(
            make_doctor_router(
                self.i18n,
                self.access_resolver,
                search_service=self.search_service,
                stt_service=self.speech_to_text_service,
                voice_mode_store=self.voice_mode_store,
                booking_service=self.booking_service,
                booking_state_service=self.booking_state_service,
                booking_orchestration=self.booking_orchestration_service,
                reference_service=self.reference_service,
                patient_reader=self.doctor_patient_reader,
                clinical_service=self.clinical_chart_service,
                recommendation_service=self.recommendation_service,
                i18n=self.i18n,
                default_locale=self.settings.app.default_locale,
                max_voice_duration_sec=self.settings.stt.max_voice_duration_sec,
                max_voice_file_size_bytes=self.settings.stt.max_voice_file_size_bytes,
                voice_mode_ttl_sec=self.settings.stt.mode_ttl_sec,
                card_runtime=self.card_runtime,
                card_callback_codec=self.card_callback_codec,
            )
        )
        dispatcher.include_router(
            make_owner_router(
                self.i18n,
                self.access_resolver,
                analytics=self.owner_analytics_service,
                default_locale=self.settings.app.default_locale,
            )
        )
        return dispatcher


class _RuntimePatientFinder:
    def __init__(self, settings: Settings) -> None:
        self._db = settings.db

    async def find_patients_by_exact_contact(self, *, contact_type: str, contact_value: str) -> list[dict]:
        return await find_patients_by_exact_contact(self._db, contact_type=contact_type, contact_value=contact_value)

    async def find_patients_by_external_id(self, *, external_system: str, external_id: str) -> list[dict]:
        return await find_patients_by_external_id(self._db, external_system=external_system, external_id=external_id)


def build_speech_to_text_provider(stt: SpeechToTextConfig) -> SpeechToTextProvider:
    if not stt.enabled:
        return DisabledSpeechToTextProvider()
    if stt.provider == "disabled":
        return DisabledSpeechToTextProvider()
    if stt.provider == "fake":
        return FakeSpeechToTextProvider()
    if stt.provider == "openai":
        if not stt.openai_api_key:
            raise RuntimeError("STT_OPENAI_API_KEY must be configured when STT_PROVIDER=openai")
        return OpenAISpeechToTextProvider(
            config=OpenAITranscriptionConfig(
                api_key=stt.openai_api_key,
                model=stt.openai_model,
                endpoint=stt.openai_endpoint,
            )
        )
    raise RuntimeError(f"Unsupported STT provider: {stt.provider}")
