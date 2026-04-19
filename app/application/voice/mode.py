from __future__ import annotations

import time
from typing import Protocol

from app.application.voice.models import VoiceModeState, VoiceSearchMode


class VoiceModeRuntime(Protocol):
    async def bind_actor_session_state(self, *, scope: str, actor_id: int, payload: dict[str, str]) -> None: ...

    async def resolve_actor_session_state(self, *, scope: str, actor_id: int) -> dict[str, str] | None: ...

    async def clear_actor_session_state(self, *, scope: str, actor_id: int) -> None: ...


class VoiceSearchModeStore:
    def __init__(self, *, runtime: VoiceModeRuntime | None = None, scope: str = "voice_mode") -> None:
        self._states: dict[int, VoiceModeState] = {}
        self._runtime = runtime
        self._scope = scope

    async def activate(self, *, actor_telegram_id: int, mode: VoiceSearchMode, ttl_sec: int) -> None:
        if self._runtime is not None:
            await self._runtime.bind_actor_session_state(
                scope=self._scope,
                actor_id=actor_telegram_id,
                payload={"mode": mode.value},
            )
            return
        self._states[actor_telegram_id] = VoiceModeState(
            mode=mode,
            expires_at_monotonic=time.monotonic() + ttl_sec,
        )

    async def get_active_mode(self, *, actor_telegram_id: int) -> VoiceSearchMode | None:
        if self._runtime is not None:
            payload = await self._runtime.resolve_actor_session_state(scope=self._scope, actor_id=actor_telegram_id)
            if payload is None:
                return None
            mode_value = payload.get("mode")
            if not mode_value:
                return None
            try:
                return VoiceSearchMode(mode_value)
            except ValueError:
                return None
        state = self._states.get(actor_telegram_id)
        if state is None:
            return None
        if state.expires_at_monotonic <= time.monotonic():
            self._states.pop(actor_telegram_id, None)
            return None
        return state.mode

    async def clear(self, *, actor_telegram_id: int) -> None:
        if self._runtime is not None:
            await self._runtime.clear_actor_session_state(scope=self._scope, actor_id=actor_telegram_id)
            return
        self._states.pop(actor_telegram_id, None)
