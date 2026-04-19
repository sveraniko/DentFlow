from __future__ import annotations

import pytest

from app.interfaces.cards import (
    ActivePanelRegistry,
    BookingCardAdapter,
    BookingCardSeed,
    CardAction,
    CardCallback,
    CardCallbackCodec,
    CardCallbackError,
    CardMode,
    CardProfile,
    CardShellRenderer,
    EntityType,
    ProductCardAdapter,
    ProductCardSeed,
    SourceContext,
    SourceRef,
    resolve_back_target,
    transition_mode,
    validate_stale_callback,
)


def test_card_shell_builds_with_shared_model() -> None:
    source = SourceRef(context=SourceContext.SEARCH_RESULTS, source_ref="q:ivanov", page_or_index=2)
    shell = ProductCardAdapter.build(
        seed=ProductCardSeed(
            product_id="prod_1",
            title="Irrigator",
            price_label="120 GEL",
            availability_label="in stock",
            state_token="rev-1",
        ),
        source=source,
    )

    panel = CardShellRenderer.to_panel(shell)

    assert shell.profile == CardProfile.PRODUCT
    assert shell.entity_type == EntityType.CARE_PRODUCT
    assert shell.mode == CardMode.COMPACT
    assert shell.source.context == SourceContext.SEARCH_RESULTS
    assert "price: 120 GEL" in panel.text


def test_mode_transition_preserves_entity_and_context() -> None:
    source = SourceRef(context=SourceContext.BOOKING_LIST, source_ref="bookings:today", page_or_index=1)
    shell = BookingCardAdapter.build(
        seed=BookingCardSeed(
            booking_id="bk_77",
            title="Booking #77",
            status_label="pending_confirmation",
            datetime_label="2026-04-20 09:00",
            state_token="rev-22",
        ),
        source=source,
    )

    expanded = transition_mode(shell, target_mode=CardMode.EXPANDED)

    assert expanded.entity_id == shell.entity_id
    assert expanded.source == shell.source
    assert expanded.mode == CardMode.EXPANDED


def test_back_from_expanded_returns_same_object_compact_target() -> None:
    source = SourceRef(context=SourceContext.ADMIN_CONFIRMATIONS, source_ref="admin:confirmations")
    shell = BookingCardAdapter.build(
        seed=BookingCardSeed(
            booking_id="bk_88",
            title="Booking #88",
            status_label="confirmed",
            datetime_label="2026-04-21 15:30",
            state_token="rev-4",
        ),
        source=source,
        mode=CardMode.EXPANDED,
    )

    back_target = resolve_back_target(shell)

    assert back_target.mode == CardMode.COMPACT
    assert back_target.entity_id == "bk_88"
    assert back_target.source.context == SourceContext.ADMIN_CONFIRMATIONS


def test_callback_contract_roundtrip() -> None:
    callback = CardCallback(
        profile=CardProfile.PRODUCT,
        entity_type=EntityType.CARE_PRODUCT,
        entity_id="prod_123",
        action=CardAction.COVER,
        mode=CardMode.EXPANDED,
        source_context=SourceContext.RECOMMENDATION_DETAIL,
        source_ref="rec_19",
        page_or_index="0",
        state_token="rev-9",
    )

    packed = CardCallbackCodec.encode(callback)
    resolved = CardCallbackCodec.decode(packed)

    assert resolved == callback


def test_invalid_callback_is_rejected() -> None:
    with pytest.raises(CardCallbackError):
        CardCallbackCodec.decode("broken")


def test_stale_validation_blocks_mutation() -> None:
    callback = CardCallback(
        profile=CardProfile.BOOKING,
        entity_type=EntityType.BOOKING,
        entity_id="bk_1",
        action=CardAction.OPEN,
        mode=CardMode.COMPACT,
        source_context=SourceContext.BOOKING_LIST,
        source_ref="today",
        page_or_index="1",
        state_token="old",
    )

    result = validate_stale_callback(
        callback,
        expected_entity_id="bk_1",
        expected_source_context=SourceContext.BOOKING_LIST,
        expected_state_token="new",
    )

    assert not result.ok
    assert result.reason_key == "common.card.callback.stale"


def test_context_mismatch_blocks_mutation() -> None:
    callback = CardCallback(
        profile=CardProfile.BOOKING,
        entity_type=EntityType.BOOKING,
        entity_id="bk_2",
        action=CardAction.OPEN,
        mode=CardMode.COMPACT,
        source_context=SourceContext.BOOKING_LIST,
        source_ref="today",
        page_or_index="1",
        state_token="rev-1",
    )

    result = validate_stale_callback(
        callback,
        expected_entity_id="bk_2",
        expected_source_context=SourceContext.ADMIN_TODAY,
        expected_state_token="rev-1",
    )

    assert not result.ok
    assert result.reason_key == "common.card.callback.invalid_context"


def test_active_panel_registry_prefers_replace_update() -> None:
    source = SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="cat:brushes")
    shell = ProductCardAdapter.build(
        seed=ProductCardSeed(
            product_id="prod_9",
            title="Brush",
            price_label="20 GEL",
            availability_label="in stock",
            state_token="rev-1",
        ),
        source=source,
    )
    registry = ActivePanelRegistry()

    first = registry.render_or_replace(actor_id=10, shell=shell)
    registry.bind_message(actor_id=10, message_id=700)
    second = registry.render_or_replace(actor_id=10, shell=shell)

    assert first.operation == "send"
    assert second.operation == "edit"
    assert second.message_id == 700
