from __future__ import annotations

import asyncio
import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from uuid import uuid4

from app.application.voice.models import SpeechToTextOutcome, SpeechToTextResult
from app.application.voice.provider import SpeechToTextInput, SpeechToTextProvider


@dataclass(frozen=True)
class OpenAITranscriptionConfig:
    api_key: str
    model: str
    endpoint: str


class OpenAISpeechToTextProvider(SpeechToTextProvider):
    """Production-capable STT adapter using OpenAI Audio Transcriptions API."""

    def __init__(self, *, config: OpenAITranscriptionConfig) -> None:
        self._config = config

    async def transcribe(self, payload: SpeechToTextInput, *, timeout_sec: float) -> SpeechToTextResult:
        if not payload.audio_bytes:
            return SpeechToTextResult(outcome=SpeechToTextOutcome.TRANSCRIPTION_FAILED)

        try:
            response = await asyncio.to_thread(
                self._post_transcription,
                payload,
                timeout_sec,
            )
        except TimeoutError:
            return SpeechToTextResult(outcome=SpeechToTextOutcome.PROVIDER_TIMEOUT)
        except Exception:
            return SpeechToTextResult(outcome=SpeechToTextOutcome.PROVIDER_ERROR)

        transcript = (response.get("text") or "").strip()
        if not transcript:
            return SpeechToTextResult(outcome=SpeechToTextOutcome.TRANSCRIPTION_FAILED)

        confidence: float | None = None
        confidence_raw = response.get("confidence")
        if isinstance(confidence_raw, (int, float)):
            confidence = float(confidence_raw)

        return SpeechToTextResult(
            outcome=SpeechToTextOutcome.SUCCESS,
            transcript=transcript,
            confidence=confidence,
        )

    def _post_transcription(self, payload: SpeechToTextInput, timeout_sec: float) -> dict:
        fields: list[tuple[str, str]] = [("model", self._config.model)]
        if payload.language_hint and payload.language_hint != "auto":
            fields.append(("language", payload.language_hint))

        body, content_type = _encode_multipart_form_data(
            fields=fields,
            file_field="file",
            filename="voice.ogg",
            mime_type=payload.mime_type or "application/octet-stream",
            file_bytes=payload.audio_bytes,
        )

        request = urllib.request.Request(
            url=self._config.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": content_type,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=timeout_sec) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code in {408, 429, 500, 502, 503, 504}:
                raise TimeoutError from exc
            raise RuntimeError("stt_provider_http_error") from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
            raise TimeoutError from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("stt_provider_malformed_json") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("stt_provider_invalid_response")
        return parsed


def _encode_multipart_form_data(
    *,
    fields: list[tuple[str, str]],
    file_field: str,
    filename: str,
    mime_type: str,
    file_bytes: bytes,
) -> tuple[bytes, str]:
    boundary = f"----dentflow-{uuid4().hex}"
    chunks: list[bytes] = []

    for key, value in fields:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ]
        )

    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {mime_type}\r\n\r\n".encode(),
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"
