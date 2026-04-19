from __future__ import annotations

from dataclasses import dataclass

from app.interfaces.cards.models import CardAction, CardMode, CardProfile, EntityType, SourceContext

_CALLBACK_VERSION = "c1"
_PARTS_COUNT = 10


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
    @staticmethod
    def encode(payload: CardCallback) -> str:
        return "|".join(
            (
                _CALLBACK_VERSION,
                payload.profile.value,
                payload.entity_type.value,
                payload.entity_id,
                payload.action.value,
                payload.mode.value,
                payload.source_context.value,
                payload.source_ref,
                payload.page_or_index,
                payload.state_token,
            )
        )

    @staticmethod
    def decode(raw: str) -> CardCallback:
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
) -> CallbackValidationResult:
    if callback.entity_id != expected_entity_id:
        return CallbackValidationResult(ok=False, reason_key="common.card.callback.invalid_entity")
    if callback.source_context != expected_source_context:
        return CallbackValidationResult(ok=False, reason_key="common.card.callback.invalid_context")
    if callback.state_token != expected_state_token:
        return CallbackValidationResult(ok=False, reason_key="common.card.callback.stale")
    return CallbackValidationResult(ok=True)
