from __future__ import annotations

from app.bootstrap.runtime import build_speech_to_text_provider
from app.config.settings import SpeechToTextConfig
from app.infrastructure.speech.disabled_provider import DisabledSpeechToTextProvider
from app.infrastructure.speech.fake_provider import FakeSpeechToTextProvider
from app.infrastructure.speech.openai_provider import OpenAISpeechToTextProvider


def test_runtime_stt_provider_disabled_when_not_enabled() -> None:
    provider = build_speech_to_text_provider(SpeechToTextConfig(enabled=False, provider="fake"))
    assert isinstance(provider, DisabledSpeechToTextProvider)


def test_runtime_stt_provider_fake_selected() -> None:
    provider = build_speech_to_text_provider(SpeechToTextConfig(enabled=True, provider="fake"))
    assert isinstance(provider, FakeSpeechToTextProvider)


def test_runtime_stt_provider_openai_selected() -> None:
    provider = build_speech_to_text_provider(
        SpeechToTextConfig(
            enabled=True,
            provider="openai",
            openai_api_key="test-key",
        )
    )
    assert isinstance(provider, OpenAISpeechToTextProvider)


def test_runtime_stt_provider_openai_requires_api_key() -> None:
    try:
        build_speech_to_text_provider(SpeechToTextConfig(enabled=True, provider="openai", openai_api_key=None))
    except RuntimeError as exc:
        assert "STT_OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for missing OpenAI key")
