from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.application.access import AccessDecision, ActorContext
from app.application.voice import SpeechToTextOutcome, SpeechToTextService, VoiceSearchMode, VoiceSearchModeStore
from app.application.voice.models import SpeechToTextResult
from app.application.voice.provider import SpeechToTextInput, SpeechToTextProvider
from app.common.i18n import I18nService
from app.domain.access_identity.models import RoleCode
from app.infrastructure.speech.fake_provider import FakeSpeechToTextProvider
from app.interfaces.bots.voice_search import VoiceSearchHandler


class _AccessResolverStub:
    def __init__(self, *, roles: set[RoleCode], locale: str = "en") -> None:
        self._roles = roles
        self._locale = locale

    def resolve_actor_context(self, telegram_user_id: int) -> ActorContext | None:
        return ActorContext(actor_id="a1", clinic_id="c1", role_codes=frozenset(self._roles), locale=self._locale)

    def check_roles(self, actor_context: ActorContext | None, allowed_roles: set[RoleCode]) -> AccessDecision:
        if actor_context and actor_context.role_codes.intersection(allowed_roles):
            return AccessDecision(allowed=True, reason="access.allowed")
        return AccessDecision(allowed=False, reason="access.denied.role")


class _SearchStub:
    def __init__(self) -> None:
        self.patient_queries: list[str] = []
        self.doctor_queries: list[str] = []
        self.service_queries: list[str] = []

    async def search_patients(self, query):
        self.patient_queries.append(query.query)
        return SimpleNamespace(exact_matches=[], suggestions=[])

    async def search_doctors(self, query):
        self.doctor_queries.append(query.query)
        return []

    async def search_services(self, query):
        self.service_queries.append(query.query)
        return []


class _BotStub:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.downloaded_to: list[str] = []

    async def get_file(self, file_id: str):
        return SimpleNamespace(file_path="voice/file.ogg")

    async def download_file(self, file_path: str, destination: str):
        self.downloaded_to.append(destination)
        Path(destination).write_bytes(self.payload)


class _GetFileFailingBot(_BotStub):
    async def get_file(self, file_id: str):
        raise RuntimeError("telegram_get_file_failed")


class _DownloadFailingBot(_BotStub):
    async def download_file(self, file_path: str, destination: str):
        self.downloaded_to.append(destination)
        raise RuntimeError("telegram_download_failed")


class _Message:
    def __init__(self, *, user_id: int = 11, bot: _BotStub | None = None, duration: int = 1, file_size: int = 16):
        self.from_user = SimpleNamespace(id=user_id)
        self.voice = SimpleNamespace(file_id="f1", duration=duration, file_size=file_size)
        self.bot = bot
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _ProviderRaises(SpeechToTextProvider):
    async def transcribe(self, payload: SpeechToTextInput, *, timeout_sec: float) -> SpeechToTextResult:
        raise RuntimeError("provider_failed")


class _ProviderTimeout(SpeechToTextProvider):
    async def transcribe(self, payload: SpeechToTextInput, *, timeout_sec: float) -> SpeechToTextResult:
        raise TimeoutError


class _ProviderMalformedSuccess(SpeechToTextProvider):
    async def transcribe(self, payload: SpeechToTextInput, *, timeout_sec: float) -> SpeechToTextResult:
        return SpeechToTextResult(outcome=SpeechToTextOutcome.SUCCESS, transcript="  ")


class _ProviderSuccess(SpeechToTextProvider):
    async def transcribe(self, payload: SpeechToTextInput, *, timeout_sec: float) -> SpeechToTextResult:
        return SpeechToTextResult(outcome=SpeechToTextOutcome.SUCCESS, transcript="john smith", confidence=0.99)


def _handler(
    *,
    roles: set[RoleCode],
    confidence_threshold: float = 0.7,
    provider: SpeechToTextProvider | None = None,
) -> VoiceSearchHandler:
    return VoiceSearchHandler(
        i18n=I18nService(locales_path=Path("locales"), default_locale="en"),
        access_resolver=_AccessResolverStub(roles=roles),
        search_service=_SearchStub(),
        stt_service=SpeechToTextService(
            provider=provider or FakeSpeechToTextProvider(),
            timeout_sec=2.0,
            confidence_threshold=confidence_threshold,
            language_hint="auto",
        ),
        mode_store=VoiceSearchModeStore(),
        default_locale="en",
        allowed_roles={RoleCode.ADMIN, RoleCode.DOCTOR},
        max_voice_duration_sec=30,
        max_voice_file_size_bytes=1000,
        mode_ttl_sec=60,
    )


def test_voice_mode_not_active_safe_fallback() -> None:
    h = _handler(roles={RoleCode.ADMIN})
    message = _Message(bot=_BotStub(b"0.9|john"))
    asyncio.run(h._handle_voice(message))
    assert message.answers and "not active" in message.answers[0].lower()


def test_voice_unauthorized_role_cannot_use_mode_or_search() -> None:
    h = _handler(roles={RoleCode.OWNER})
    message = _Message(bot=_BotStub(b"0.9|john"))
    asyncio.run(h._activate_mode(message, VoiceSearchMode.PATIENT))
    assert message.answers and "access denied" in message.answers[0].lower()


def test_voice_patient_search_success_uses_patient_search_path_and_cleans_temp_file() -> None:
    h = _handler(roles={RoleCode.ADMIN}, provider=_ProviderSuccess())
    search = h._search_service
    bot = _BotStub(b"ignored")
    message = _Message(bot=bot)
    h._mode_store.activate(actor_telegram_id=message.from_user.id, mode=VoiceSearchMode.PATIENT, ttl_sec=60)

    asyncio.run(h._handle_voice(message))

    assert search.patient_queries == ["john smith"]
    assert len(message.answers) >= 2
    assert "Heard" in message.answers[0]
    assert not search.doctor_queries and not search.service_queries
    assert bot.downloaded_to
    assert all(not Path(path).exists() for path in bot.downloaded_to)


def test_voice_doctor_and_service_modes_call_canonical_services() -> None:
    h = _handler(roles={RoleCode.DOCTOR})
    search = h._search_service

    doctor_message = _Message(bot=_BotStub(b"0.95|ortho"), user_id=21)
    h._mode_store.activate(actor_telegram_id=21, mode=VoiceSearchMode.DOCTOR, ttl_sec=60)
    asyncio.run(h._handle_voice(doctor_message))

    service_message = _Message(bot=_BotStub(b"0.95|clean"), user_id=22)
    h._mode_store.activate(actor_telegram_id=22, mode=VoiceSearchMode.SERVICE, ttl_sec=60)
    asyncio.run(h._handle_voice(service_message))

    assert search.doctor_queries == ["ortho"]
    assert search.service_queries == ["clean"]


def test_voice_low_confidence_and_transcription_failures_fallback_safely() -> None:
    low = _handler(roles={RoleCode.ADMIN}, confidence_threshold=0.8)
    low_message = _Message(bot=_BotStub(b"0.5|john"), user_id=31)
    low._mode_store.activate(actor_telegram_id=31, mode=VoiceSearchMode.PATIENT, ttl_sec=60)
    asyncio.run(low._handle_voice(low_message))
    assert "confidence" in low_message.answers[0].lower()

    failed = _handler(roles={RoleCode.ADMIN})
    fail_message = _Message(bot=_BotStub(b"fail"), user_id=32)
    failed._mode_store.activate(actor_telegram_id=32, mode=VoiceSearchMode.PATIENT, ttl_sec=60)
    asyncio.run(failed._handle_voice(fail_message))
    assert "transcribe" in fail_message.answers[0].lower()

    unsupported = _handler(roles={RoleCode.ADMIN})
    unsupported_message = _Message(bot=_BotStub(b"unsupported"), user_id=33)
    unsupported._mode_store.activate(actor_telegram_id=33, mode=VoiceSearchMode.PATIENT, ttl_sec=60)
    asyncio.run(unsupported._handle_voice(unsupported_message))
    assert "unsupported" in unsupported_message.answers[0].lower()


def test_voice_stale_mode_rejected_safely() -> None:
    h = _handler(roles={RoleCode.ADMIN})
    message = _Message(bot=_BotStub(b"0.9|john"), user_id=41)
    h._mode_store.activate(actor_telegram_id=41, mode=VoiceSearchMode.PATIENT, ttl_sec=-1)
    asyncio.run(h._handle_voice(message))
    assert "not active" in message.answers[0].lower()


def test_voice_get_file_failure_becomes_safe_fallback() -> None:
    h = _handler(roles={RoleCode.ADMIN})
    message = _Message(bot=_GetFileFailingBot(b"irrelevant"), user_id=51)
    h._mode_store.activate(actor_telegram_id=51, mode=VoiceSearchMode.PATIENT, ttl_sec=60)

    asyncio.run(h._handle_voice(message))

    assert message.answers
    assert "could not process the telegram voice file" in message.answers[0].lower()


def test_voice_download_failure_becomes_safe_fallback_and_cleans_temp_file() -> None:
    h = _handler(roles={RoleCode.ADMIN})
    bot = _DownloadFailingBot(b"irrelevant")
    message = _Message(bot=bot, user_id=52)
    h._mode_store.activate(actor_telegram_id=52, mode=VoiceSearchMode.PATIENT, ttl_sec=60)

    asyncio.run(h._handle_voice(message))

    assert message.answers
    assert "could not process the telegram voice file" in message.answers[0].lower()
    assert bot.downloaded_to
    assert all(not Path(path).exists() for path in bot.downloaded_to)


def test_voice_provider_exception_becomes_safe_fallback() -> None:
    h = _handler(roles={RoleCode.ADMIN}, provider=_ProviderRaises())
    message = _Message(bot=_BotStub(b"whatever"), user_id=53)
    h._mode_store.activate(actor_telegram_id=53, mode=VoiceSearchMode.PATIENT, ttl_sec=60)

    asyncio.run(h._handle_voice(message))

    assert message.answers
    assert "provider failed" in message.answers[0].lower()


def test_voice_provider_timeout_becomes_safe_fallback() -> None:
    h = _handler(roles={RoleCode.ADMIN}, provider=_ProviderTimeout())
    message = _Message(bot=_BotStub(b"whatever"), user_id=54)
    h._mode_store.activate(actor_telegram_id=54, mode=VoiceSearchMode.PATIENT, ttl_sec=60)

    asyncio.run(h._handle_voice(message))

    assert message.answers
    assert "timed out" in message.answers[0].lower()


def test_voice_malformed_provider_success_becomes_safe_fallback() -> None:
    h = _handler(roles={RoleCode.ADMIN}, provider=_ProviderMalformedSuccess())
    message = _Message(bot=_BotStub(b"whatever"), user_id=55)
    h._mode_store.activate(actor_telegram_id=55, mode=VoiceSearchMode.PATIENT, ttl_sec=60)

    asyncio.run(h._handle_voice(message))

    assert message.answers
    assert "transcribe" in message.answers[0].lower()
