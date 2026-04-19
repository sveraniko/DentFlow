from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from app.common.i18n import I18nService
from app.interfaces.cards import (
    BookingCardAdapter,
    BookingRuntimeSnapshot,
    BookingRuntimeViewBuilder,
    CardAction,
    CardCallback,
    CardCallbackCodec,
    CardMode,
    CardProfile,
    CardRuntimeCoordinator,
    CardRuntimeStateStore,
    EntityType,
    InMemoryRedis,
    SourceContext,
    SourceRef,
)


def _i18n() -> I18nService:
    return I18nService(locales_path=Path("locales"), default_locale="en")


def _seed(role: str, status: str = "confirmed"):
    i18n = _i18n()
    builder = BookingRuntimeViewBuilder()
    return builder.build_seed(
        snapshot=BookingRuntimeSnapshot(
            booking_id="b1",
            state_token="token1",
            role_variant=role,
            scheduled_start_at=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
            patient_label="John",
            doctor_label="Dr One",
            service_label="CONS",
            branch_label="Main",
            status=status,
            recommendation_summary="rec-1",
            care_order_summary="order-1",
            chart_summary_entry="chart-1",
        ),
        i18n=i18n,
        locale="en",
    )


def test_booking_card_actions_by_role_runtime_seed() -> None:
    i18n = _i18n()
    admin_shell = BookingCardAdapter.build(
        seed=_seed("admin", "pending_confirmation"),
        source=SourceRef(context=SourceContext.BOOKING_LIST, source_ref="admin"),
        i18n=i18n,
        locale="en",
        mode=CardMode.EXPANDED,
    )
    doctor_shell = BookingCardAdapter.build(
        seed=_seed("doctor", "checked_in"),
        source=SourceRef(context=SourceContext.DOCTOR_QUEUE, source_ref="doctor"),
        i18n=i18n,
        locale="en",
        mode=CardMode.EXPANDED,
    )
    patient_shell = BookingCardAdapter.build(
        seed=_seed("patient", "pending_confirmation"),
        source=SourceRef(context=SourceContext.BOOKING_LIST, source_ref="patient"),
        i18n=i18n,
        locale="en",
        mode=CardMode.EXPANDED,
    )

    assert CardAction.CONFIRM in {a.action for a in admin_shell.actions}
    assert CardAction.OPEN_PATIENT in {a.action for a in admin_shell.actions}
    assert CardAction.IN_SERVICE in {a.action for a in doctor_shell.actions}
    assert CardAction.OPEN_CHART in {a.action for a in doctor_shell.actions}
    assert CardAction.CANCEL in {a.action for a in patient_shell.actions}
    assert CardAction.OPEN_PATIENT not in {a.action for a in patient_shell.actions}


def test_booking_card_callback_runtime_roundtrip() -> None:
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    payload = CardCallback(
        profile=CardProfile.BOOKING,
        entity_type=EntityType.BOOKING,
        entity_id="b9",
        action=CardAction.OPEN_CHART,
        mode=CardMode.EXPANDED,
        source_context=SourceContext.DOCTOR_QUEUE,
        source_ref="doctor.booking.card",
        page_or_index="open_chart",
        state_token="b9",
    )
    encoded = asyncio.run(codec.encode(payload))
    decoded = asyncio.run(codec.decode(encoded))

    assert encoded.startswith("c2|")
    assert decoded == payload
