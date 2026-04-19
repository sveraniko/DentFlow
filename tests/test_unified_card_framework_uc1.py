from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.common.i18n import I18nService
from app.domain.access_identity.models import RoleCode
from app.interfaces.cards import (
    ActivePanelRegistry,
    BookingCardAdapter,
    BookingCardSeed,
    BookingRuntimeSnapshot,
    BookingRuntimeViewBuilder,
    CardAction,
    CardCallback,
    CardCallbackCodec,
    CardCallbackError,
    CardMode,
    CardProfile,
    CardRuntimeCoordinator,
    CardRuntimeStateStore,
    CardShellRenderer,
    DoctorCardAdapter,
    DoctorCardSeed,
    DoctorRuntimeSnapshot,
    DoctorRuntimeViewBuilder,
    EntityType,
    InMemoryRedis,
    PanelFamily,
    PatientCardAdapter,
    PatientCardSeed,
    PatientRuntimeSnapshot,
    PatientRuntimeViewBuilder,
    ProductCardAdapter,
    ProductCardSeed,
    ProductRuntimeSnapshot,
    ProductRuntimeViewBuilder,
    RuntimeTtlConfig,
    SourceContext,
    SourceRef,
    RuntimeStateError,
    resolve_back_target,
    transition_mode,
    validate_stale_callback,
)


@pytest.fixture
def i18n() -> I18nService:
    return I18nService(Path("locales"), default_locale="en")


def test_callback_token_uses_shared_runtime_store_and_expires_safely() -> None:
    async def _run() -> None:
        redis = InMemoryRedis()
        store = CardRuntimeStateStore(redis_client=redis, ttl=RuntimeTtlConfig(callback_ttl_sec=1))
        codec_a = CardCallbackCodec(runtime=CardRuntimeCoordinator(store=store))
        codec_b = CardCallbackCodec(runtime=CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=redis, ttl=RuntimeTtlConfig(callback_ttl_sec=1))))

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
        packed = await codec_a.encode(callback)
        assert packed.startswith("c2|")
        assert await codec_b.decode(packed) == callback

        short_store = CardRuntimeStateStore(redis_client=InMemoryRedis(), ttl=RuntimeTtlConfig(callback_ttl_sec=0))
        expired_codec = CardCallbackCodec(runtime=CardRuntimeCoordinator(store=short_store))
        expired_payload = await expired_codec.encode(callback)
        with pytest.raises(CardCallbackError):
            await expired_codec.decode(expired_payload)

    asyncio.run(_run())


def test_active_panel_registry_is_family_aware_and_supersedes() -> None:
    async def _run() -> None:
        runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
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
            i18n=I18nService(Path("locales"), default_locale="en"),
            locale="en",
        )

        patient_catalog = ActivePanelRegistry(runtime=runtime, panel_family=PanelFamily.PATIENT_CATALOG)
        booking_detail = ActivePanelRegistry(runtime=runtime, panel_family=PanelFamily.BOOKING_DETAIL)

        first = await patient_catalog.render_or_replace(actor_id=10, shell=shell)
        await patient_catalog.bind_message(actor_id=10, chat_id=100, message_id=700, shell=shell)
        second = await patient_catalog.render_or_replace(actor_id=10, shell=shell)
        await booking_detail.bind_message(actor_id=10, chat_id=100, message_id=800, shell=shell)

        assert first.operation == "send"
        assert second.operation == "edit"
        assert second.message_id == 700
        assert (await runtime.resolve_active_panel(actor_id=10, panel_family=PanelFamily.BOOKING_DETAIL)).message_id == 800

    asyncio.run(_run())


def test_actor_session_state_is_shared_and_restart_safe_within_ttl() -> None:
    async def _run() -> None:
        redis = InMemoryRedis()
        runtime_a = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=redis))
        runtime_b = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=redis))

        await runtime_a.bind_actor_session_state(
            scope="patient_flow",
            actor_id=42,
            payload={
                "booking_session_id": "sess-1",
                "booking_mode": "existing_lookup_contact",
                "care": {"selected_category": "paste"},
            },
        )
        loaded = await runtime_b.resolve_actor_session_state(scope="patient_flow", actor_id=42)
        assert loaded is not None
        assert loaded["booking_session_id"] == "sess-1"
        assert loaded["booking_mode"] == "existing_lookup_contact"
        assert loaded["care"]["selected_category"] == "paste"

    asyncio.run(_run())


def test_missing_active_panel_is_rejected_as_stale() -> None:
    async def _run() -> None:
        runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
        with pytest.raises(RuntimeStateError):
            await runtime.ensure_panel_is_active(actor_id=11, panel_family=PanelFamily.PATIENT_CATALOG, state_token="rev-1")

    asyncio.run(_run())


def test_product_patient_doctor_localization_and_runtime_builders(i18n: I18nService) -> None:
    product_seed = ProductRuntimeViewBuilder().build_seed(
        snapshot=ProductRuntimeSnapshot(
            product_id="prod_2",
            sku="Sensitive",
            price_amount=30,
            currency_code="GEL",
            status="active",
            available_qty=2,
            title_by_locale={"en": "Nano Paste", "ru": "Нано паста"},
            description_by_locale={"en": "Synced localized description from catalog DB"},
            usage_hint="Use twice daily",
            category="aftercare",
            recommendation_rationale="Based on enamel sensitivity",
            selected_branch_label="Main branch",
            state_token="rev-2",
        ),
        i18n=i18n,
        locale="en",
    )
    product = ProductCardAdapter.build(
        seed=product_seed,
        source=SourceRef(context=SourceContext.RECOMMENDATION_DETAIL, source_ref="rec_11"),
        i18n=i18n,
        locale="en",
        mode=CardMode.EXPANDED,
    )
    assert any("Usage:" in line for line in product.detail_lines)
    assert any("Recommendation:" in line for line in product.detail_lines)
    assert any(meta.key == "branch" for meta in product.meta_lines)
    assert any(action.action == CardAction.RESERVE for action in product.actions)
    assert any(action.action == CardAction.CHANGE_BRANCH for action in product.actions)

    compact = ProductCardAdapter.build(
        seed=product_seed,
        source=SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="cat_aftercare"),
        i18n=i18n,
        locale="en",
        mode=CardMode.COMPACT,
    )
    assert any(action.action == CardAction.EXPAND for action in compact.actions)
    assert not any(action.action == CardAction.RESERVE for action in compact.actions)

    patient_seed = PatientRuntimeViewBuilder().build_seed(
        snapshot=PatientRuntimeSnapshot(
            patient_id="pat_2",
            first_name="Nina",
            last_name="D.",
            state_token="rev-6",
            primary_contact="phone:+9955990099",
            active_flags=("needs follow-up", "allergy"),
            upcoming_booking_label="Today 16:00",
            recommendation_summary="2 active",
            care_order_summary="1 ready pickup",
            chart_summary_entry="Last visit: hygiene",
        )
    )
    patient = PatientCardAdapter.build(
        seed=patient_seed,
        source=SourceRef(context=SourceContext.BOOKING_LIST, source_ref="today"),
        actor_roles={RoleCode.DOCTOR},
        i18n=i18n,
        locale="en",
        mode=CardMode.EXPANDED,
    )
    assert any("Chart:" in line for line in patient.detail_lines)
    assert any(meta.key == "contact" and meta.value.endswith("0099") for meta in patient.meta_lines)

    doctor_seed = DoctorRuntimeViewBuilder().build_seed(
        snapshot=DoctorRuntimeSnapshot(
            doctor_id="doc_1",
            display_name="Dr. Smith",
            specialty="orthodontist",
            today_bookings=8,
            schedule_summary="09:00-17:00",
            today_queue_size=5,
            service_tags=("ortho",),
            state_token="rev-3",
        )
    )
    doctor = DoctorCardAdapter.build(
        seed=doctor_seed,
        source=SourceRef(context=SourceContext.ADMIN_TODAY, source_ref="today"),
        actor_roles={RoleCode.ADMIN},
        i18n=i18n,
        locale="en",
        mode=CardMode.EXPANDED,
    )
    assert any("Schedule:" in line for line in doctor.detail_lines)
    assert any("Queue:" in line for line in doctor.detail_lines)


def test_mode_transition_back_and_stale_protection_in_profile_flow(i18n: I18nService) -> None:
    source = SourceRef(context=SourceContext.BOOKING_LIST, source_ref="bookings:today", page_or_index=1)
    shell = BookingCardAdapter.build(
        seed=BookingCardSeed(
            booking_id="bk_77",
            role_variant="patient",
            patient_label="Nina D.",
            doctor_label="Dr. Smith",
            service_label="Consultation",
            branch_label="Main",
            datetime_label="2026-04-20 09:00",
            local_time_hint="UTC",
            status_label="Pending confirmation",
            state_token="rev-22",
            can_confirm=True,
            can_reschedule=True,
            can_cancel=True,
        ),
        source=source,
        i18n=i18n,
        locale="en",
    )
    expanded = transition_mode(shell, target_mode=CardMode.EXPANDED)
    back_target = resolve_back_target(expanded)
    assert back_target.mode == CardMode.COMPACT

    stale_result = validate_stale_callback(
        CardCallback(
            profile=CardProfile.PRODUCT,
            entity_type=EntityType.CARE_PRODUCT,
            entity_id="prod_123",
            action=CardAction.COVER,
            mode=CardMode.EXPANDED,
            source_context=SourceContext.RECOMMENDATION_DETAIL,
            source_ref="rec_19",
            page_or_index="0",
            state_token="rev-9",
        ),
        expected_entity_id="prod_123",
        expected_source_context=SourceContext.RECOMMENDATION_DETAIL,
        expected_state_token="rev-10",
    )
    assert not stale_result.ok


def test_booking_runtime_builder_and_role_variants(i18n: I18nService) -> None:
    snapshot = BookingRuntimeSnapshot(
        booking_id="bk_1",
        role_variant="admin",
        scheduled_start_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
        timezone_name="UTC",
        patient_label="Nina D.",
        doctor_label="Dr. Smith",
        service_label="Consultation",
        branch_label="Main",
        status="confirmed",
        compact_flags=("reminder",),
        reminder_summary="sent",
        reschedule_summary="none",
        source_channel="telegram",
        patient_contact="phone:+9955990099",
        recommendation_summary="1 active",
        care_order_summary="ready pickup",
        chart_summary_entry="last note",
        state_token="rev-booking",
    )
    seed = BookingRuntimeViewBuilder().build_seed(snapshot=snapshot, i18n=i18n, locale="en")
    admin = BookingCardAdapter.build(seed=seed, source=SourceRef(context=SourceContext.ADMIN_TODAY, source_ref="today"), i18n=i18n, locale="en", mode=CardMode.EXPANDED)
    labels = [a.label for a in admin.actions]
    assert "Arrived" in labels
    assert "Patient" in labels
    assert any("Reminder:" in line for line in admin.detail_lines)

    doctor_seed = BookingRuntimeViewBuilder().build_seed(
        snapshot=replace(snapshot, role_variant="doctor", status="checked_in", state_token="rev-doc"),
        i18n=i18n,
        locale="en",
    )
    doctor = BookingCardAdapter.build(seed=doctor_seed, source=SourceRef(context=SourceContext.DOCTOR_QUEUE, source_ref="queue"), i18n=i18n, locale="en")
    assert any(a.action == CardAction.IN_SERVICE for a in doctor.actions)
    assert all(a.action != CardAction.CANCEL for a in doctor.actions)

    owner_seed = BookingRuntimeViewBuilder().build_seed(
        snapshot=replace(snapshot, role_variant="owner", status="confirmed", state_token="rev-own"),
        i18n=i18n,
        locale="en",
    )
    owner = BookingCardAdapter.build(seed=owner_seed, source=SourceRef(context=SourceContext.OWNER_ALERT, source_ref="alert"), i18n=i18n, locale="en")
    assert all(a.action not in {CardAction.CONFIRM, CardAction.CANCEL, CardAction.RESCHEDULE} for a in owner.actions)


def test_patient_unauthorized_is_localized(i18n: I18nService) -> None:
    blocked = PatientCardAdapter.build(
        seed=PatientCardSeed(patient_id="pat_2", display_name="Nina D.", state_token="rev-6"),
        source=SourceRef(context=SourceContext.BOOKING_LIST, source_ref="today"),
        actor_roles={RoleCode.OWNER},
        i18n=i18n,
        locale="en",
    )
    assert blocked.subtitle == "Limited access"
    assert blocked.detail_lines[0] == "Access denied for this profile."
