from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VoiceSearchMode(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    SERVICE = "service"


class SpeechToTextOutcome(str, Enum):
    SUCCESS = "success"
    TRANSCRIPTION_FAILED = "transcription_failed"
    LOW_CONFIDENCE = "low_confidence"
    UNSUPPORTED_AUDIO = "unsupported_audio"
    TOO_LONG = "too_long"
    TOO_LARGE = "too_large"
    MODE_NOT_ACTIVE = "mode_not_active"
    DOWNLOAD_FAILED = "download_failed"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True)
class SpeechToTextResult:
    outcome: SpeechToTextOutcome
    transcript: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class VoiceModeState:
    mode: VoiceSearchMode
    expires_at_monotonic: float
