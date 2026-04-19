from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b

from app.interfaces.cards.models import CardAction, CardMode, CardProfile, EntityType, SourceContext

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


@dataclass(slots=True)
class _CompactCallbackRegistry:
    _counter: int = 0
    _values: dict[str, CardCallback] | None = None

    def __post_init__(self) -> None:
        if self._values is None:
            self._values = {}

    def issue(self, payload: CardCallback) -> str:
        self._counter += 1
        base = _to_base36(self._counter)
        digest = blake2b(
            f"{payload.profile.value}|{payload.entity_type.value}|{payload.entity_id}|{payload.action.value}|{payload.state_token}".encode(
                "utf-8"
            ),
            digest_size=2,
        ).hexdigest()
        token = f"{base}{digest}"
        self._values[token] = payload
        return token

    def resolve(self, token: str) -> CardCallback | None:
        return self._values.get(token)


def _to_base36(value: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    out: list[str] = []
    current = value
    while current:
        current, rem = divmod(current, 36)
        out.append(alphabet[rem])
    return "".join(reversed(out))


class CardCallbackCodec:
    _registry = _CompactCallbackRegistry()

    @staticmethod
    def encode(payload: CardCallback) -> str:
        token = CardCallbackCodec._registry.issue(payload)
        compact = f"{_COMPACT_CALLBACK_VERSION}|{token}"
        if len(compact.encode("utf-8")) > _TELEGRAM_CALLBACK_MAX_BYTES:
            raise CardCallbackError("callback_payload_too_large")
        return compact

    @staticmethod
    def decode(raw: str) -> CardCallback:
        parts = raw.split("|")
        if parts[0] == _COMPACT_CALLBACK_VERSION:
            if len(parts) != 2 or not parts[1]:
                raise CardCallbackError("invalid_callback_format")
            payload = CardCallbackCodec._registry.resolve(parts[1])
            if payload is None:
                raise CardCallbackError("invalid_callback_token")
            return payload
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
