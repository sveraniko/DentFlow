from __future__ import annotations

import time

from app.application.voice.models import VoiceModeState, VoiceSearchMode


class VoiceSearchModeStore:
    def __init__(self) -> None:
        self._states: dict[int, VoiceModeState] = {}

    def activate(self, *, actor_telegram_id: int, mode: VoiceSearchMode, ttl_sec: int) -> None:
        self._states[actor_telegram_id] = VoiceModeState(
            mode=mode,
            expires_at_monotonic=time.monotonic() + ttl_sec,
        )

    def get_active_mode(self, *, actor_telegram_id: int) -> VoiceSearchMode | None:
        state = self._states.get(actor_telegram_id)
        if state is None:
            return None
        if state.expires_at_monotonic <= time.monotonic():
            self._states.pop(actor_telegram_id, None)
            return None
        return state.mode

    def clear(self, *, actor_telegram_id: int) -> None:
        self._states.pop(actor_telegram_id, None)
