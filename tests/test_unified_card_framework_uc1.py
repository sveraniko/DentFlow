from __future__ import annotations

import pytest

from app.domain.access_identity.models import RoleCode
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
    DoctorCardAdapter,
    DoctorCardSeed,
    EntityType,
    PatientCardAdapter,
    PatientCardSeed,
    ProductCardAdapter,
    ProductCardSeed,
    SourceContext,
    SourceRef,
    resolve_back_target,
    transition_mode,
    validate_stale_callback,
)


def test_product_compact_renders_core_fields() -> None:
    source = SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="cat:aftercare", page_or_index=1)
    shell = ProductCardAdapter.build(
        seed=ProductCardSeed(
            product_id="prod_1",
            title="Irrigator",
            short_label="Portable",
            price_label="120 GEL",
            availability_label="in stock",
            selected_branch_label="Central branch",
            state_token="rev-1",
        ),
        source=source,
    )

    panel = CardShellRenderer.to_panel(shell)

    assert shell.profile == CardProfile.PRODUCT
    assert shell.entity_type == EntityType.CARE_PRODUCT
    assert shell.mode == CardMode.COMPACT
    assert "label: Portable" in panel.text
    assert "price: 120 GEL" in panel.text
    assert "availability: in stock" in panel.text
    assert "branch: Central branch" in panel.text


def test_product_expanded_renders_synced_content_fields() -> None:
    source = SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="cat:aftercare")
    shell = ProductCardAdapter.build(
        seed=ProductCardSeed(
            product_id="prod_2",
            title="Nano Paste",
            short_label="Sensitive",
            price_label="30 GEL",
            availability_label="low stock",
            localized_description="Synced localized description from catalog DB",
            usage_hint="Use twice daily",
            category="aftercare",
            state_token="rev-2",
        ),
        source=source,
        mode=CardMode.EXPANDED,
    )

    assert any("Synced localized description" in line for line in shell.detail_lines)
    assert any("Usage: Use twice daily" == line for line in shell.detail_lines)
    assert any("Category: aftercare" == line for line in shell.detail_lines)


def test_product_source_context_differs_between_recommendation_and_category() -> None:
    recommendation_shell = ProductCardAdapter.build(
        seed=ProductCardSeed(
            product_id="prod_7",
            title="Night Guard",
            price_label="140 GEL",
            availability_label="in stock",
            recommendation_badge="Recommended",
            recommendation_rationale="Based on enamel sensitivity",
            category="night_care",
            state_token="rev-8",
        ),
        source=SourceRef(context=SourceContext.RECOMMENDATION_DETAIL, source_ref="rec_12"),
        mode=CardMode.EXPANDED,
    )
    category_shell = ProductCardAdapter.build(
        seed=ProductCardSeed(
            product_id="prod_7",
            title="Night Guard",
            price_label="140 GEL",
            availability_label="in stock",
            recommendation_badge="Recommended",
            recommendation_rationale="Based on enamel sensitivity",
            category="night_care",
            state_token="rev-8",
        ),
        source=SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="cat:night_care"),
        mode=CardMode.EXPANDED,
    )

    assert any("Recommendation:" in line for line in recommendation_shell.detail_lines)
    assert not any("Recommendation:" in line for line in category_shell.detail_lines)
    assert any("Opened from category" in line for line in category_shell.detail_lines)


def test_product_cover_gallery_actions_safe_and_no_media_safe() -> None:
    with_media = ProductCardAdapter.build(
        seed=ProductCardSeed(
            product_id="prod_media",
            title="Whitening Kit",
            price_label="80 GEL",
            availability_label="in stock",
            state_token="rev-4",
            media_count=3,
        ),
        source=SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="cat:kit"),
        mode=CardMode.EXPANDED,
    )
    media_actions = {action.action for action in with_media.actions}
    assert CardAction.COVER in media_actions
    assert CardAction.GALLERY in media_actions

    without_media = ProductCardAdapter.build(
        seed=ProductCardSeed(
            product_id="prod_nomedia",
            title="Basic Floss",
            price_label="10 GEL",
            availability_label="in stock",
            state_token="rev-5",
            media_count=0,
        ),
        source=SourceRef(context=SourceContext.CARE_CATALOG_CATEGORY, source_ref="cat:hygiene"),
        mode=CardMode.EXPANDED,
    )
    no_media_actions = {action.action for action in without_media.actions}
    assert CardAction.COVER not in no_media_actions
    assert CardAction.GALLERY not in no_media_actions


def test_patient_compact_renders_identity_safely() -> None:
    shell = PatientCardAdapter.build(
        seed=PatientCardSeed(
            patient_id="pat_1",
            display_name="Ivan Petrov",
            patient_number="P-100",
            contact_hint="+995***12",
            photo_present=True,
            active_flags_summary="allergy",
            booking_snippet="Tomorrow 10:00",
            state_token="rev-1",
        ),
        source=SourceRef(context=SourceContext.SEARCH_RESULTS, source_ref="q:ivan"),
        actor_roles={RoleCode.ADMIN},
    )
    text = CardShellRenderer.to_panel(shell).text
    assert "patient_no: P-100" in text
    assert "contact: +995***12" in text
    assert "flags: allergy" in text


def test_patient_expanded_bounded_context_and_unauthorized_blocked() -> None:
    expanded = PatientCardAdapter.build(
        seed=PatientCardSeed(
            patient_id="pat_2",
            display_name="Nina D.",
            state_token="rev-6",
            contact_block="phone:+995***99",
            active_flags_summary="needs follow-up",
            booking_snippet="Today 16:00",
            recommendation_summary="2 active",
            care_order_summary="1 ready pickup",
            chart_summary_entry="Last visit: hygiene",
        ),
        source=SourceRef(context=SourceContext.BOOKING_LIST, source_ref="today"),
        actor_roles={RoleCode.DOCTOR},
        mode=CardMode.EXPANDED,
    )
    assert any("Chart:" in line for line in expanded.detail_lines)
    assert all("diagnosis" not in line.lower() for line in expanded.detail_lines)

    blocked = PatientCardAdapter.build(
        seed=PatientCardSeed(patient_id="pat_2", display_name="Nina D.", state_token="rev-6"),
        source=SourceRef(context=SourceContext.BOOKING_LIST, source_ref="today"),
        actor_roles={RoleCode.OWNER},
    )
    assert blocked.subtitle == "Limited access"
    assert blocked.actions == (blocked.actions[0],)


def test_doctor_compact_and_expanded_are_operational_and_bounded() -> None:
    compact = DoctorCardAdapter.build(
        seed=DoctorCardSeed(
            doctor_id="doc_1",
            display_name="Dr. Smith",
            specialty="orthodontist",
            branch_label="Central",
            operational_hint="Queue active",
            state_token="rev-3",
        ),
        source=SourceRef(context=SourceContext.ADMIN_TODAY, source_ref="today"),
        actor_roles={RoleCode.ADMIN},
    )
    compact_text = CardShellRenderer.to_panel(compact).text
    assert "specialty: orthodontist" in compact_text

    expanded = DoctorCardAdapter.build(
        seed=DoctorCardSeed(
            doctor_id="doc_1",
            display_name="Dr. Smith",
            specialty="orthodontist",
            branch_label="Central",
            operational_hint="Queue active",
            schedule_summary="09:00-17:00",
            queue_summary="5 waiting",
            service_tags=("ortho", "aligners"),
            state_token="rev-3",
        ),
        source=SourceRef(context=SourceContext.ADMIN_TODAY, source_ref="today"),
        actor_roles={RoleCode.DOCTOR},
        mode=CardMode.EXPANDED,
    )
    assert any("Schedule:" in line for line in expanded.detail_lines)
    assert any(action.action == CardAction.TODAY for action in expanded.actions)


def test_mode_transition_back_and_stale_protection_in_profile_flow() -> None:
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
    back_target = resolve_back_target(expanded)
    assert back_target.mode == CardMode.COMPACT

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
    assert packed.startswith("c2|")
    assert resolved == callback

    stale_result = validate_stale_callback(
        resolved,
        expected_entity_id="prod_123",
        expected_source_context=SourceContext.RECOMMENDATION_DETAIL,
        expected_state_token="rev-10",
    )
    assert not stale_result.ok


def test_invalid_callback_is_rejected() -> None:
    with pytest.raises(CardCallbackError):
        CardCallbackCodec.decode("broken")


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
