from __future__ import annotations

from app.application.voice.models import SpeechToTextOutcome, SpeechToTextResult
from app.application.voice.provider import SpeechToTextInput, SpeechToTextProvider


class DisabledSpeechToTextProvider(SpeechToTextProvider):
    async def transcribe(self, payload: SpeechToTextInput, *, timeout_sec: float) -> SpeechToTextResult:
        return SpeechToTextResult(outcome=SpeechToTextOutcome.TRANSCRIPTION_FAILED)
