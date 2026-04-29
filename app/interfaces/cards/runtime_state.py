from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Protocol

from app.interfaces.cards.models import CardProfile, SourceContext


class RuntimeStateError(RuntimeError):
    pass


class PanelFamily(str, Enum):
    PATIENT_HOME = "patient_home"
    PATIENT_CATALOG = "patient_catalog"
    RECOMMENDATION_FLOW = "recommendation_flow"
    DOCTOR_QUEUE = "doctor_queue"
    ADMIN_TODAY = "admin_today"
    BOOKING_DETAIL = "booking_detail"
    CARE_ORDER_FLOW = "care_order_flow"
    SEARCH_RESULTS = "search_results"


@dataclass(slots=True, frozen=True)
class RuntimeTtlConfig:
    callback_ttl_sec: int = 30 * 60
    panel_ttl_sec: int = 2 * 60 * 60
    source_context_ttl_sec: int = 60 * 60
    session_ttl_sec: int = 2 * 60 * 60


@dataclass(slots=True, frozen=True)
class ActivePanelState:
    actor_id: int
    chat_id: int
    message_id: int
    panel_family: PanelFamily
    profile: CardProfile | None
    entity_id: str | None
    source_context: SourceContext
    source_ref: str
    page_or_index: str
    state_token: str
    updated_at: str


class RedisLike(Protocol):
    async def set(self, key: str, value: str, ex: int | None = None) -> object: ...

    async def get(self, key: str) -> str | bytes | None: ...

    async def delete(self, key: str) -> int: ...


class InMemoryRedis:
    def __init__(self) -> None:
        self._values: dict[str, tuple[str, datetime | None]] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> object:
        expires_at = datetime.now(timezone.utc) if ex == 0 else None
        if ex and ex > 0:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ex)
        self._values[key] = (value, expires_at)
        return True

    async def get(self, key: str) -> str | None:
        item = self._values.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at and expires_at <= datetime.now(timezone.utc):
            self._values.pop(key, None)
            return None
        return value

    async def delete(self, key: str) -> int:
        existed = key in self._values
        self._values.pop(key, None)
        return int(existed)


class CardRuntimeStateStore:
    def __init__(self, *, redis_client: RedisLike, ttl: RuntimeTtlConfig | None = None) -> None:
        self._redis = redis_client
        self._ttl = ttl or RuntimeTtlConfig()

    async def issue_callback_token(self, payload: dict[str, str]) -> str:
        token = secrets.token_urlsafe(8)
        key = f"card:cb:{token}"
        await self._redis.set(key, json.dumps(payload), ex=self._ttl.callback_ttl_sec)
        return token

    async def resolve_callback_token(self, token: str) -> dict[str, str] | None:
        raw = await self._redis.get(f"card:cb:{token}")
        if raw is None:
            return None
        return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)

    async def bind_active_panel(self, panel: ActivePanelState) -> None:
        key = self._panel_key(panel.actor_id, panel.panel_family)
        await self._redis.set(key, json.dumps(asdict(panel)), ex=self._ttl.panel_ttl_sec)

    async def resolve_active_panel(self, *, actor_id: int, panel_family: PanelFamily) -> ActivePanelState | None:
        raw = await self._redis.get(self._panel_key(actor_id, panel_family))
        if raw is None:
            return None
        data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        return ActivePanelState(
            actor_id=data["actor_id"],
            chat_id=data["chat_id"],
            message_id=data["message_id"],
            panel_family=PanelFamily(data["panel_family"]),
            profile=CardProfile(data["profile"]) if data["profile"] else None,
            entity_id=data["entity_id"],
            source_context=SourceContext(data["source_context"]),
            source_ref=data["source_ref"],
            page_or_index=data["page_or_index"],
            state_token=data["state_token"],
            updated_at=data["updated_at"],
        )

    async def invalidate_panel(self, *, actor_id: int, panel_family: PanelFamily) -> None:
        await self._redis.delete(self._panel_key(actor_id, panel_family))

    async def supersede_active_panel(self, panel: ActivePanelState) -> None:
        # Overwrite by family key provides explicit supersession semantics.
        await self.bind_active_panel(panel)

    async def bind_actor_session_state(self, *, scope: str, actor_id: int, payload: dict[str, Any]) -> None:
        key = self._session_key(scope=scope, actor_id=actor_id)
        await self._redis.set(key, json.dumps(payload), ex=self._ttl.session_ttl_sec)

    async def resolve_actor_session_state(self, *, scope: str, actor_id: int) -> dict[str, Any] | None:
        raw = await self._redis.get(self._session_key(scope=scope, actor_id=actor_id))
        if raw is None:
            return None
        return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)

    async def clear_actor_session_state(self, *, scope: str, actor_id: int) -> None:
        await self._redis.delete(self._session_key(scope=scope, actor_id=actor_id))

    @staticmethod
    def _panel_key(actor_id: int, panel_family: PanelFamily) -> str:
        return f"card:panel:{actor_id}:{panel_family.value}"

    @staticmethod
    def _session_key(*, scope: str, actor_id: int) -> str:
        return f"card:session:{scope}:{actor_id}"


class CardRuntimeCoordinator:
    def __init__(self, *, store: CardRuntimeStateStore) -> None:
        self._store = store

    async def store_callback(self, payload: dict[str, str]) -> str:
        return await self._store.issue_callback_token(payload)

    async def resolve_callback(self, token: str) -> dict[str, str]:
        payload = await self._store.resolve_callback_token(token)
        if payload is None:
            raise RuntimeStateError("stale_callback")
        return payload

    async def bind_panel(
        self,
        *,
        actor_id: int,
        chat_id: int,
        message_id: int,
        panel_family: PanelFamily,
        profile: CardProfile | None,
        entity_id: str | None,
        source_context: SourceContext,
        source_ref: str,
        page_or_index: str,
        state_token: str,
    ) -> ActivePanelState:
        panel = ActivePanelState(
            actor_id=actor_id,
            chat_id=chat_id,
            message_id=message_id,
            panel_family=panel_family,
            profile=profile,
            entity_id=entity_id,
            source_context=source_context,
            source_ref=source_ref,
            page_or_index=page_or_index,
            state_token=state_token,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        await self._store.supersede_active_panel(panel)
        return panel

    async def ensure_panel_is_active(self, *, actor_id: int, panel_family: PanelFamily, state_token: str) -> None:
        current = await self._store.resolve_active_panel(actor_id=actor_id, panel_family=panel_family)
        if current is None or current.state_token != state_token:
            raise RuntimeStateError("stale_panel")

    async def resolve_active_panel(self, *, actor_id: int, panel_family: PanelFamily) -> ActivePanelState | None:
        return await self._store.resolve_active_panel(actor_id=actor_id, panel_family=panel_family)

    async def bind_actor_session_state(self, *, scope: str, actor_id: int, payload: dict[str, Any]) -> None:
        await self._store.bind_actor_session_state(scope=scope, actor_id=actor_id, payload=payload)

    async def resolve_actor_session_state(self, *, scope: str, actor_id: int) -> dict[str, Any] | None:
        return await self._store.resolve_actor_session_state(scope=scope, actor_id=actor_id)

    async def clear_actor_session_state(self, *, scope: str, actor_id: int) -> None:
        await self._store.clear_actor_session_state(scope=scope, actor_id=actor_id)

    async def invalidate_panel(self, *, actor_id: int, panel_family: PanelFamily) -> None:
        await self._store.invalidate_panel(actor_id=actor_id, panel_family=panel_family)
