from __future__ import annotations

from app.application.voice.models import SpeechToTextOutcome, SpeechToTextResult
from app.application.voice.provider import SpeechToTextInput, SpeechToTextProvider


class SpeechToTextService:
    def __init__(
        self,
        *,
        provider: SpeechToTextProvider,
        timeout_sec: float,
        confidence_threshold: float,
        language_hint: str | None,
    ) -> None:
        self._provider = provider
        self._timeout_sec = timeout_sec
        self._confidence_threshold = confidence_threshold
        self._language_hint = language_hint

    async def transcribe_voice(self, *, audio_bytes: bytes, mime_type: str | None) -> SpeechToTextResult:
        result = await self._provider.transcribe(
            SpeechToTextInput(
                audio_bytes=audio_bytes,
                mime_type=mime_type,
                language_hint=self._language_hint,
            ),
            timeout_sec=self._timeout_sec,
        )
        if result.outcome != SpeechToTextOutcome.SUCCESS:
            return result

        transcript = (result.transcript or "").strip()
        if not transcript:
            return SpeechToTextResult(outcome=SpeechToTextOutcome.TRANSCRIPTION_FAILED)
        if result.confidence is not None and result.confidence < self._confidence_threshold:
            return SpeechToTextResult(
                outcome=SpeechToTextOutcome.LOW_CONFIDENCE,
                confidence=result.confidence,
            )
        return SpeechToTextResult(
            outcome=SpeechToTextOutcome.SUCCESS,
            transcript=transcript,
            confidence=result.confidence,
        )
