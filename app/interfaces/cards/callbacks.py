from __future__ import annotations

from dataclasses import dataclass

from app.interfaces.cards.models import CardAction, CardMode, CardProfile, EntityType, SourceContext
from app.interfaces.cards.runtime_state import CardRuntimeCoordinator, RuntimeStateError

_CALLBACK_VERSION = "c1"
_COMPACT_CALLBACK_VERSION = "c2"
_PARTS_COUNT = 10
_TELEGRAM_CALLBACK_MAX_BYTES = 64


class CardCallbackError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class CardCallback:
    profile: CardProfile
    entity_type: EntityType
    entity_id: str
    action: CardAction
    mode: CardMode
    source_context: SourceContext
    source_ref: str
    page_or_index: str
    state_token: str


class CardCallbackCodec:
    def __init__(self, *, runtime: CardRuntimeCoordinator) -> None:
        self._runtime = runtime

    async def encode(self, payload: CardCallback) -> str:
        token = await self._runtime.store_callback(
            {
                "profile": payload.profile.value,
                "entity_type": payload.entity_type.value,
                "entity_id": payload.entity_id,
                "action": payload.action.value,
                "mode": payload.mode.value,
                "source_context": payload.source_context.value,
                "source_ref": payload.source_ref,
                "page_or_index": payload.page_or_index,
                "state_token": payload.state_token,
            }
        )
        compact = f"{_COMPACT_CALLBACK_VERSION}|{token}"
        if len(compact.encode("utf-8")) > _TELEGRAM_CALLBACK_MAX_BYTES:
            raise CardCallbackError("callback_payload_too_large")
        return compact

    async def decode(self, raw: str) -> CardCallback:
        parts = raw.split("|")
        if parts[0] == _COMPACT_CALLBACK_VERSION:
            if len(parts) != 2 or not parts[1]:
                raise CardCallbackError("invalid_callback_format")
            try:
                payload = await self._runtime.resolve_callback(parts[1])
                return CardCallback(
                    profile=CardProfile(payload["profile"]),
                    entity_type=EntityType(payload["entity_type"]),
                    entity_id=payload["entity_id"],
                    action=CardAction(payload["action"]),
                    mode=CardMode(payload["mode"]),
                    source_context=SourceContext(payload["source_context"]),
                    source_ref=payload["source_ref"],
                    page_or_index=payload["page_or_index"],
                    state_token=payload["state_token"],
                )
            except RuntimeStateError as exc:
                raise CardCallbackError("invalid_callback_token") from exc
        return _decode_legacy(raw)


def _decode_legacy(raw: str) -> CardCallback:
    parts = raw.split("|")
    if len(parts) != _PARTS_COUNT:
        raise CardCallbackError("invalid_callback_format")
    if parts[0] != _CALLBACK_VERSION:
        raise CardCallbackError("invalid_callback_version")
    try:
        return CardCallback(
            profile=CardProfile(parts[1]),
            entity_type=EntityType(parts[2]),
            entity_id=parts[3],
            action=CardAction(parts[4]),
            mode=CardMode(parts[5]),
            source_context=SourceContext(parts[6]),
            source_ref=parts[7],
            page_or_index=parts[8],
            state_token=parts[9],
        )
    except ValueError as exc:
        raise CardCallbackError("invalid_callback_semantics") from exc


@dataclass(slots=True, frozen=True)
class CallbackValidationResult:
    ok: bool
    reason_key: str | None = None


def validate_stale_callback(
    callback: CardCallback,
    *,
    expected_entity_id: str,
    expected_source_context: SourceContext,
    expected_state_token: str,
    expected_source_ref: str | None = None,
    expected_page_or_index: str | None = None,
    require_source_ref_match: bool = False,
    require_page_or_index_match: bool = False,
) -> CallbackValidationResult:
    if callback.entity_id != expected_entity_id:
        return CallbackValidationResult(ok=False, reason_key="common.card.callback.invalid_entity")
    if callback.source_context != expected_source_context:
        return CallbackValidationResult(ok=False, reason_key="common.card.callback.invalid_context")
    if require_source_ref_match and callback.source_ref != (expected_source_ref or ""):
        return CallbackValidationResult(ok=False, reason_key="common.card.callback.invalid_source_ref")
    if require_page_or_index_match and callback.page_or_index != (expected_page_or_index or ""):
        return CallbackValidationResult(ok=False, reason_key="common.card.callback.invalid_page")
    if callback.state_token != expected_state_token:
        return CallbackValidationResult(ok=False, reason_key="common.card.callback.stale")
    return CallbackValidationResult(ok=True)
