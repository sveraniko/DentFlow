from __future__ import annotations

import os
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.application.access import AccessResolver
from app.application.search.service import HybridSearchService
from app.application.voice import SpeechToTextOutcome, SpeechToTextService, VoiceSearchMode, VoiceSearchModeStore
from app.common.i18n import I18nService
from app.domain.access_identity.models import RoleCode
from app.interfaces.bots.common import guard_roles, resolve_locale
from app.interfaces.bots.search_handlers import run_doctor_search, run_patient_search, run_service_search


class VoiceSearchHandler:
    def __init__(
        self,
        *,
        i18n: I18nService,
        access_resolver: AccessResolver,
        search_service: HybridSearchService,
        stt_service: SpeechToTextService,
        mode_store: VoiceSearchModeStore,
        default_locale: str,
        allowed_roles: set[RoleCode],
        max_voice_duration_sec: int,
        max_voice_file_size_bytes: int,
        mode_ttl_sec: int,
    ) -> None:
        self._i18n = i18n
        self._access_resolver = access_resolver
        self._search_service = search_service
        self._stt_service = stt_service
        self._mode_store = mode_store
        self._default_locale = default_locale
        self._allowed_roles = allowed_roles
        self._max_voice_duration_sec = max_voice_duration_sec
        self._max_voice_file_size_bytes = max_voice_file_size_bytes
        self._mode_ttl_sec = mode_ttl_sec

    def register(self, router: Router) -> None:
        @router.message(Command("voice_find_patient"))
        async def voice_find_patient(message: Message) -> None:
            await self._activate_mode(message, VoiceSearchMode.PATIENT)

        @router.message(Command("voice_find_doctor"))
        async def voice_find_doctor(message: Message) -> None:
            await self._activate_mode(message, VoiceSearchMode.DOCTOR)

        @router.message(Command("voice_find_service"))
        async def voice_find_service(message: Message) -> None:
            await self._activate_mode(message, VoiceSearchMode.SERVICE)

        @router.message(F.voice)
        async def handle_voice(message: Message) -> None:
            await self._handle_voice(message)

    async def _activate_mode(self, message: Message, mode: VoiceSearchMode) -> None:
        allowed = await guard_roles(
            message,
            i18n=self._i18n,
            access_resolver=self._access_resolver,
            allowed_roles=self._allowed_roles,
            fallback_locale=self._default_locale,
        )
        if not allowed or not message.from_user:
            return
        locale = await resolve_locale(message, access_resolver=self._access_resolver, fallback_locale=self._default_locale)
        self._mode_store.activate(actor_telegram_id=message.from_user.id, mode=mode, ttl_sec=self._mode_ttl_sec)
        await message.answer(self._i18n.t(f"voice.mode.{mode.value}.activated", locale).format(ttl=self._mode_ttl_sec))

    async def _handle_voice(self, message: Message) -> None:
        allowed = await guard_roles(
            message,
            i18n=self._i18n,
            access_resolver=self._access_resolver,
            allowed_roles=self._allowed_roles,
            fallback_locale=self._default_locale,
        )
        if not allowed or not message.from_user or not message.voice or not message.bot:
            return
        locale = await resolve_locale(message, access_resolver=self._access_resolver, fallback_locale=self._default_locale)
        actor = self._access_resolver.resolve_actor_context(message.from_user.id)
        if not actor:
            return

        mode = self._mode_store.get_active_mode(actor_telegram_id=message.from_user.id)
        if mode is None:
            await self._reply_fallback(message, locale=locale, outcome=SpeechToTextOutcome.MODE_NOT_ACTIVE)
            return

        if message.voice.duration and message.voice.duration > self._max_voice_duration_sec:
            await self._reply_fallback(message, locale=locale, outcome=SpeechToTextOutcome.TOO_LONG)
            return
        if message.voice.file_size and message.voice.file_size > self._max_voice_file_size_bytes:
            await self._reply_fallback(message, locale=locale, outcome=SpeechToTextOutcome.TOO_LARGE)
            return

        temp_path: Path | None = None
        audio_bytes: bytes | None = None
        try:
            file = await message.bot.get_file(message.voice.file_id)
            with tempfile.NamedTemporaryFile(prefix="dentflow_voice_", suffix=".ogg", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
            await message.bot.download_file(file.file_path, destination=str(temp_path))
            audio_bytes = temp_path.read_bytes()
        except Exception:
            await self._reply_fallback(message, locale=locale, outcome=SpeechToTextOutcome.DOWNLOAD_FAILED)
            return
        finally:
            if temp_path and temp_path.exists():
                os.unlink(temp_path)

        if not audio_bytes:
            await self._reply_fallback(message, locale=locale, outcome=SpeechToTextOutcome.DOWNLOAD_FAILED)
            return

        stt = await self._stt_service.transcribe_voice(audio_bytes=audio_bytes, mime_type="audio/ogg")
        if stt.outcome != SpeechToTextOutcome.SUCCESS or not stt.transcript:
            await self._reply_fallback(message, locale=locale, outcome=stt.outcome)
            return

        self._mode_store.clear(actor_telegram_id=message.from_user.id)
        transcript = stt.transcript.strip()
        await message.answer(self._i18n.t("voice.transcript.echo", locale).format(transcript=transcript))

        if mode == VoiceSearchMode.PATIENT:
            result = await run_patient_search(
                service=self._search_service,
                i18n=self._i18n,
                locale=locale,
                clinic_id=actor.clinic_id,
                query=transcript,
            )
        elif mode == VoiceSearchMode.DOCTOR:
            result = await run_doctor_search(
                service=self._search_service,
                i18n=self._i18n,
                locale=locale,
                clinic_id=actor.clinic_id,
                query=transcript,
            )
        else:
            result = await run_service_search(
                service=self._search_service,
                i18n=self._i18n,
                locale=locale,
                clinic_id=actor.clinic_id,
                query=transcript,
            )
        await message.answer(result)

    async def _reply_fallback(self, message: Message, *, locale: str, outcome: SpeechToTextOutcome) -> None:
        key = f"voice.fallback.{outcome.value}"
        await message.answer(self._i18n.t(key, locale))


def attach_voice_search_handlers(
    router: Router,
    *,
    i18n: I18nService,
    access_resolver: AccessResolver,
    search_service: HybridSearchService,
    stt_service: SpeechToTextService,
    mode_store: VoiceSearchModeStore,
    default_locale: str,
    allowed_roles: set[RoleCode],
    max_voice_duration_sec: int,
    max_voice_file_size_bytes: int,
    mode_ttl_sec: int,
) -> None:
    VoiceSearchHandler(
        i18n=i18n,
        access_resolver=access_resolver,
        search_service=search_service,
        stt_service=stt_service,
        mode_store=mode_store,
        default_locale=default_locale,
        allowed_roles=allowed_roles,
        max_voice_duration_sec=max_voice_duration_sec,
        max_voice_file_size_bytes=max_voice_file_size_bytes,
        mode_ttl_sec=mode_ttl_sec,
    ).register(router)
