from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.application.voice.models import SpeechToTextResult


@dataclass(frozen=True)
class SpeechToTextInput:
    audio_bytes: bytes
    mime_type: str | None
    language_hint: str | None


class SpeechToTextProvider(Protocol):
    async def transcribe(self, payload: SpeechToTextInput, *, timeout_sec: float) -> SpeechToTextResult: ...
