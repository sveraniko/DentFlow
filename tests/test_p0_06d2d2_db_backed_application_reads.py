from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

from app.application.booking.telegram_flow import BookingPatientFlowService
from app.application.care_commerce.service import CareCommerceService
from app.application.clinic_reference import ClinicReferenceService
from app.application.recommendation.services import RecommendationService
from app.infrastructure.db.booking_repository import DbBookingRepository
from app.infrastructure.db.care_commerce_repository import DbCareCommerceRepository
from app.infrastructure.db.patient_repository import find_patient_by_exact_contact
from app.infrastructure.db.recommendation_repository import DbRecommendationRepository
from app.infrastructure.db.repositories import DbClinicReferenceRepository
sys.path.append(str(Path(__file__).resolve().parent / "helpers"))
from seed_demo_db_harness import reset_test_db, run_seed_demo_bootstrap_for_tests, safe_test_db_config


class _NoopOrchestration:
    pass


class _NoopPatientCreator:
    async def create_minimal_patient(self, *, clinic_id: str, display_name: str, phone: str) -> str:
        raise RuntimeError("not used in read smoke")

    async def upsert_telegram_contact(self, *, patient_id: str, telegram_user_id: int) -> None:
        raise RuntimeError("not used in read smoke")


def test_p0_06d2d2_db_backed_application_reads_smoke() -> None:
    db_config = safe_test_db_config()

    async def _run() -> None:
        await reset_test_db(db_config)
        stage_counts = await run_seed_demo_bootstrap_for_tests(db_config)
        assert set(stage_counts) == {"stack1", "stack2", "stack3", "care_catalog", "recommendations_care_orders"}

        reference_repo = await DbClinicReferenceRepository.load(db_config)
        reference_service = ClinicReferenceService(reference_repo)
        booking_repo = DbBookingRepository(db_config)
        booking_flow = BookingPatientFlowService(
            orchestration=_NoopOrchestration(),
            reads=booking_repo,
            reference=reference_service,
            patient_creator=_NoopPatientCreator(),
        )

        care_repo = DbCareCommerceRepository(db_config)
        care_service = CareCommerceService(care_repo)
        recommendation_repo = DbRecommendationRepository(db_config)
        recommendation_service = RecommendationService(recommendation_repo)

        clinic = reference_service.get_clinic("clinic_main")
        assert clinic is not None
        assert any(branch.branch_id == "branch_central" for branch in reference_service.list_branches("clinic_main"))
        assert len(reference_service.list_services("clinic_main")) >= 4
        assert len(reference_service.list_doctors("clinic_main")) >= 3
        public_doctors = booking_flow.list_doctors(clinic_id="clinic_main")
        assert len(public_doctors) >= 2
        assert reference_service.resolve_doctor_access_code(clinic_id="clinic_main", code="ANNA-001") is not None
        assert reference_service.resolve_doctor_access_code(clinic_id="clinic_main", code="BORIS-HYG") is not None
        assert reference_service.resolve_doctor_access_code(
            clinic_id="clinic_main",
            code="IRINA-TREAT",
            service_id="svc_implant_consult",
        ) is not None
        assert (
            reference_service.resolve_doctor_access_code(
                clinic_id="clinic_main",
                code="IRINA-TREAT",
                service_id="svc_hygiene_standard",
            )
            is None
        )

        booking_session = await booking_flow.get_booking_session(booking_session_id="bks_001")
        assert booking_session is not None
        assert booking_session.clinic_id == "clinic_main"
        assert booking_session.telegram_user_id == 3001
        assert booking_session.resolved_patient_id == "patient_sergey_ivanov"
        assert booking_session.status == "review_ready"
        assert booking_session.contact_phone_snapshot

        slots = await booking_flow.list_slots_for_session(booking_session_id="bks_001", limit=20)
        assert slots
        assert slots == sorted(slots, key=lambda row: row.start_at)
        assert all(slot.start_at > datetime.now(timezone.utc) for slot in slots)
        assert any(slot.service_scope and "svc_hygiene_standard" in slot.service_scope for slot in slots)

        booking = await booking_flow.get_booking(booking_id="bkg_sergey_confirmed")
        assert booking is not None
        assert booking.patient_id == "patient_sergey_ivanov"
        assert booking.status == "confirmed"
        assert booking.scheduled_start_at > datetime.now(timezone.utc)

        prefill = await booking_flow.get_recent_booking_prefill(clinic_id="clinic_main", patient_id="patient_sergey_ivanov")
        assert prefill is not None
        assert prefill.service_id
        assert prefill.doctor_id
        assert prefill.branch_id
        assert prefill.doctor_label
        assert prefill.service_label
        assert prefill.branch_label

        assert (await find_patient_by_exact_contact(db_config, contact_type="telegram", contact_value="3001"))["patient_id"] == "patient_sergey_ivanov"
        assert (await find_patient_by_exact_contact(db_config, contact_type="telegram", contact_value="3002"))["patient_id"] == "patient_elena_ivanova"
        assert (
            await find_patient_by_exact_contact(db_config, contact_type="phone", contact_value="+995598123456")
        )["patient_id"] == "patient_giorgi_beridze"
        assert await find_patient_by_exact_contact(db_config, contact_type="telegram", contact_value="999999") is None

        categories = set(await care_service.list_catalog_categories(clinic_id="clinic_main"))
        assert {"toothbrush", "toothpaste", "floss", "rinse", "irrigator"}.issubset(categories)
        assert any("remin" in category for category in categories)

        toothbrush_products = await care_service.list_catalog_products_by_category(clinic_id="clinic_main", category="toothbrush")
        brush = next((row for row in toothbrush_products if row.sku == "SKU-BRUSH-SOFT"), None)
        assert brush is not None
        assert brush.status == "active"
        assert brush.price_amount is not None
        assert brush.currency_code

        hygiene_resolution = await care_service.resolve_recommendation_target_result(
            clinic_id="clinic_main",
            recommendation_id="rec_sergey_hygiene_issued",
            recommendation_type="hygiene_support",
        )
        assert hygiene_resolution.status in {"manual_target_resolved", "rule_links_resolved", "direct_links_resolved"}
        assert any(row.product.sku == "SKU-BRUSH-SOFT" for row in hygiene_resolution.products)

        sensitive_resolution = await care_service.resolve_recommendation_target_result(
            clinic_id="clinic_main",
            recommendation_id="rec_sergey_sensitive_ack",
            recommendation_type="general_guidance",
        )
        assert any(row.product.sku == "SKU-PASTE-SENSITIVE" for row in sensitive_resolution.products)

        accepted_resolution = await care_service.resolve_recommendation_target_result(
            clinic_id="clinic_main",
            recommendation_id="rec_sergey_monitoring_accepted",
            recommendation_type="monitoring",
        )
        assert any(row.product.sku == "SKU-FLOSS-WAXED" for row in accepted_resolution.products)

        invalid_manual_resolution = await care_service.resolve_recommendation_target_result(
            clinic_id="clinic_main",
            recommendation_id="rec_sergey_manual_invalid",
            recommendation_type="general_guidance",
        )
        assert invalid_manual_resolution.status == "manual_target_invalid"
        assert invalid_manual_resolution.products == []

        patient_orders = await care_service.list_patient_orders(clinic_id="clinic_main", patient_id="patient_sergey_ivanov")
        assert any(order.status in {"confirmed", "ready_for_pickup"} for order in patient_orders)
        confirmed_order = await care_service.get_order("co_sergey_confirmed_brush")
        assert confirmed_order is not None
        order_items = await care_repo.list_order_items("co_sergey_confirmed_brush")
        brush_product = await care_repo.get_product_by_code(clinic_id="clinic_main", target_code="SKU-BRUSH-SOFT")
        assert brush_product is not None
        assert any(item.care_product_id == brush_product.care_product_id for item in order_items)
        reservations = await care_repo.list_reservations_for_order(care_order_id="co_sergey_confirmed_brush")
        assert any(
            reservation.status == "active" and reservation.care_product_id == brush_product.care_product_id
            for reservation in reservations
        )

        all_recommendations = await recommendation_service.list_for_patient(
            patient_id="patient_sergey_ivanov",
            include_terminal=True,
        )
        assert len(all_recommendations) >= 4
        all_statuses = {item.status for item in all_recommendations}
        assert all_statuses & {"issued", "viewed"}
        assert "acknowledged" in all_statuses
        assert "accepted" in all_statuses
        assert all_statuses & {"expired", "declined", "withdrawn"}

        non_terminal = await recommendation_service.list_for_patient(
            patient_id="patient_sergey_ivanov",
            include_terminal=False,
        )
        assert non_terminal
        assert all(item.status not in {"accepted", "declined", "expired", "withdrawn"} for item in non_terminal)

        recommendation = await recommendation_service.get("rec_sergey_hygiene_issued")
        assert recommendation is not None
        assert recommendation.recommendation_type
        assert recommendation.title
        assert recommendation.body_text

        acknowledged = await recommendation_service.acknowledge(recommendation_id="rec_sergey_hygiene_issued")
        assert acknowledged is not None
        assert acknowledged.status == "acknowledged"
        assert acknowledged.acknowledged_at is not None
        persisted = await recommendation_service.get("rec_sergey_hygiene_issued")
        assert persisted is not None
        assert persisted.status == "acknowledged"

        with pytest.raises(ValueError):
            await recommendation_service.accept(recommendation_id="rec_giorgi_expired")

        # Cross-service UI readiness
        sergey = await find_patient_by_exact_contact(db_config, contact_type="telegram", contact_value="3001")
        assert sergey and sergey["patient_id"] == "patient_sergey_ivanov"
        assert await booking_flow.get_booking(booking_id="bkg_sergey_confirmed") is not None
        assert await recommendation_service.list_for_patient(patient_id="patient_sergey_ivanov", include_terminal=True)
        assert await care_service.list_patient_orders(clinic_id="clinic_main", patient_id="patient_sergey_ivanov")
        assert hygiene_resolution.products

        elena = await find_patient_by_exact_contact(db_config, contact_type="telegram", contact_value="3002")
        assert elena and elena["patient_id"] == "patient_elena_ivanova"
        elena_bookings = await booking_repo.list_bookings_by_patient(patient_id="patient_elena_ivanova")
        assert any(row.status == "reschedule_requested" for row in elena_bookings)
        assert (
            await recommendation_service.list_for_patient(patient_id="patient_elena_ivanova", include_terminal=True)
            or await care_service.list_patient_orders(clinic_id="clinic_main", patient_id="patient_elena_ivanova")
        )

        maria = await find_patient_by_exact_contact(db_config, contact_type="telegram", contact_value="3004")
        assert maria and maria["patient_id"] == "patient_maria_kim"
        assert (
            await recommendation_service.list_for_patient(patient_id="patient_maria_kim", include_terminal=True)
            or await care_service.list_patient_orders(clinic_id="clinic_main", patient_id="patient_maria_kim")
        )

    asyncio.run(_run())
