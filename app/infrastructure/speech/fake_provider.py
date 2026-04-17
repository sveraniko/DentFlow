from __future__ import annotations

from app.application.voice.models import SpeechToTextOutcome, SpeechToTextResult
from app.application.voice.provider import SpeechToTextInput, SpeechToTextProvider


class FakeSpeechToTextProvider(SpeechToTextProvider):
    """Deterministic provider for local/dev/tests.

    Input bytes are interpreted as UTF-8 text in the form:
    - "<confidence>|<transcript>" e.g. "0.94|john smith"
    - "fail" for transcription failure
    - "unsupported" for unsupported audio
    """

    async def transcribe(self, payload: SpeechToTextInput, *, timeout_sec: float) -> SpeechToTextResult:
        raw = payload.audio_bytes.decode("utf-8", errors="ignore").strip()
        if raw == "unsupported":
            return SpeechToTextResult(outcome=SpeechToTextOutcome.UNSUPPORTED_AUDIO)
        if raw == "fail":
            return SpeechToTextResult(outcome=SpeechToTextOutcome.TRANSCRIPTION_FAILED)
        if "|" in raw:
            conf_raw, transcript = raw.split("|", 1)
            try:
                confidence = float(conf_raw)
            except ValueError:
                confidence = None
            return SpeechToTextResult(
                outcome=SpeechToTextOutcome.SUCCESS,
                transcript=transcript,
                confidence=confidence,
            )
        return SpeechToTextResult(outcome=SpeechToTextOutcome.SUCCESS, transcript=raw, confidence=1.0)
