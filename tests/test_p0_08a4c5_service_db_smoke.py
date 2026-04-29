from __future__ import annotations

import asyncio

import pytest

from app.application.patient.family import BookingPatientSelectorService, PatientFamilyService
from app.application.patient.media import PatientMediaService
from app.application.patient.profile import PatientPreferenceService, PatientProfileService
from app.application.patient.questionnaire import PreVisitQuestionnaireService
from app.domain.patient_registry.models import PatientRelationship
from app.infrastructure.db.media_repository import DbMediaRepository
from app.infrastructure.db.patient_repository import DbPatientRegistryRepository
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.domain.clinic_reference.models import Branch, RecordStatus
from tests.helpers.seed_demo_db_harness import run_seed_demo_bootstrap_for_tests, safe_test_db_config, reset_test_db


def test_p0_08a4c5_service_db_smoke() -> None:
    async def _run() -> None:
        db_config = safe_test_db_config()
        await reset_test_db(db_config)
        await run_seed_demo_bootstrap_for_tests(db_config)

        patient_repo = DbPatientRegistryRepository(db_config)
        media_repo = DbMediaRepository(db_config)
        ref_repo = InMemoryClinicReferenceRepository()
        ref_repo.upsert_branch(
            Branch(
                branch_id="branch_central",
                clinic_id="clinic_main",
                name="Central",
                timezone="Europe/Moscow",
                status=RecordStatus.ACTIVE,
            )
        )
        reference_service = ClinicReferenceService(ref_repo)

        profile_service = PatientProfileService(patient_repo)
        preference_service = PatientPreferenceService(patient_repo, reference_service=reference_service)
        family_service = PatientFamilyService(patient_repo)

        class _PatientLookup:
            async def find_by_phone(self, *, clinic_id: str, phone: str):
                profiles = await patient_repo.find_profiles_by_phone(clinic_id=clinic_id, phone=phone)
                return [{"patient_id": p.patient_id, "display_name": p.display_name} for p in profiles]

        selector_service = BookingPatientSelectorService(family_service, patient_registry_service=_PatientLookup())
        questionnaire_service = PreVisitQuestionnaireService(patient_repo)
        media_service = PatientMediaService(media_repo)

        clinic_id = "clinic_main"
        patient_id = "patient_sergey_ivanov"
        related_id = "patient_maria_petrova"
        booking_id = "bkg_sergey_confirmed"

        # 2) PatientProfileService
        initial = await profile_service.get_profile_details(clinic_id=clinic_id, patient_id=patient_id)
        saved = await profile_service.save_profile_details(
            clinic_id=clinic_id,
            patient_id=patient_id,
            email="sergey@example.test",
            city="Moscow",
            country_code="de",
            emergency_contact_name="Elena",
            emergency_contact_phone="+79990001122",
            profile_completion_state="partial",
        )
        assert saved.country_code == "DE"
        assert saved.email == "sergey@example.test"
        assert saved.profile_completion_state == "partial"

        updated = await profile_service.save_profile_details(
            clinic_id=clinic_id,
            patient_id=patient_id,
            email="sergey.updated@example.test",
            profile_completion_state="completed",
        )
        assert updated.email == "sergey.updated@example.test"
        assert updated.profile_completion_state == "completed"
        assert updated.created_at == saved.created_at
        assert updated.updated_at is not None
        assert updated.city == "Moscow"

        with pytest.raises(ValueError):
            await profile_service.save_profile_details(clinic_id=clinic_id, patient_id=patient_id, email="bad-email")
        if initial is not None:
            assert initial.patient_id == patient_id

        # 3) PatientPreferenceService
        pref = await preference_service.update_notification_settings(
            patient_id=patient_id,
            preferred_reminder_channel="telegram",
            allow_sms=False,
            allow_telegram=True,
            allow_call=True,
            notification_recipient_strategy="guardian_or_self",
            quiet_hours_start="21:00",
            quiet_hours_end="09:00",
            quiet_hours_timezone="Europe/Moscow",
        )
        assert pref.preferred_reminder_channel == "telegram"
        assert pref.allow_sms is False and pref.allow_telegram is True and pref.allow_call is True
        assert pref.quiet_hours_timezone == "Europe/Moscow"

        branch_pref = await preference_service.update_branch_preference(
            clinic_id=clinic_id,
            patient_id=patient_id,
            default_branch_id="branch_central",
            allow_any_branch=False,
        )
        assert branch_pref.default_branch_id == "branch_central"
        assert branch_pref.allow_any_branch is False

        with pytest.raises(ValueError):
            await preference_service.update_branch_preference(
                clinic_id=clinic_id,
                patient_id=patient_id,
                default_branch_id="branch_missing",
                allow_any_branch=False,
            )

        # 4) Family + selector telegram
        rel = await family_service.add_relationship(
            PatientRelationship(
                relationship_id="rel_c5_sergey_maria",
                clinic_id=clinic_id,
                manager_patient_id=patient_id,
                related_patient_id=related_id,
                relationship_type="child",
                is_default_for_booking=True,
                is_default_notification_recipient=True,
                consent_status="active",
            )
        )
        options = await family_service.list_linked_profiles_for_telegram(clinic_id=clinic_id, telegram_user_id=3001)
        by_id = {o.patient_id: o for o in options}
        assert patient_id in by_id and related_id in by_id
        assert by_id[patient_id].is_self is True
        assert by_id[related_id].relationship_type == "child"
        assert by_id[related_id].is_default_for_booking is True
        assert any(o.phone for o in options)

        resolved = await selector_service.resolve_for_telegram(clinic_id=clinic_id, telegram_user_id=3001)
        assert resolved.mode == "multiple_profiles"
        assert {o.patient_id for o in resolved.options} >= {patient_id, related_id}
        selected = await selector_service.select_patient(clinic_id=clinic_id, telegram_user_id=3001, patient_id=related_id)
        assert selected.mode == "single_match"
        no_match = await selector_service.select_patient(clinic_id=clinic_id, telegram_user_id=3001, patient_id="patient_unlinked")
        assert no_match.mode == "no_match"

        await family_service.deactivate_relationship(clinic_id=clinic_id, relationship_id=rel.relationship_id)
        after = await selector_service.resolve_for_telegram(clinic_id=clinic_id, telegram_user_id=3001)
        assert related_id not in {o.patient_id for o in after.options}

        # 5) selector phone
        phone_single = await selector_service.resolve_for_phone(clinic_id=clinic_id, phone="+995555000111")
        assert phone_single.mode == "single_match"
        assert phone_single.selected_patient_id == "patient_giorgi_beridze"
        phone_missing = await selector_service.resolve_for_phone(clinic_id=clinic_id, phone="+10000000000")
        assert phone_missing.mode == "minimal_name_required"

        # 6) Questionnaire
        q = await questionnaire_service.start_questionnaire(
            clinic_id=clinic_id,
            patient_id=patient_id,
            booking_id=booking_id,
            questionnaire_type="pre_visit",
            version=1,
        )
        await questionnaire_service.save_answer(questionnaire_id=q.questionnaire_id, question_key="allergies", answer_value={"value": "latex"}, answer_type="json")
        await questionnaire_service.save_answer(questionnaire_id=q.questionnaire_id, question_key="medications", answer_value=["ibuprofen"], answer_type="json")
        await questionnaire_service.save_answer(questionnaire_id=q.questionnaire_id, question_key="pain_level", answer_value=3, answer_type="json")
        await questionnaire_service.save_answer(questionnaire_id=q.questionnaire_id, question_key="consent", answer_value=True, answer_type="json")
        await questionnaire_service.save_answer(questionnaire_id=q.questionnaire_id, question_key="comment", answer_value="test", answer_type="json")

        answers = await questionnaire_service.list_answers(questionnaire_id=q.questionnaire_id)
        by_key = {a.question_key: a for a in answers}
        assert by_key["allergies"].answer_value == {"value": "latex"}
        assert by_key["medications"].answer_value == ["ibuprofen"]
        assert by_key["pain_level"].answer_value == 3
        assert by_key["consent"].answer_value is True
        assert by_key["comment"].answer_value == "test"

        pain2 = await questionnaire_service.save_answer(questionnaire_id=q.questionnaire_id, question_key="pain_level", answer_value=4, answer_type="json")
        assert pain2.answer_id.startswith("pvqa_")
        answers2 = await questionnaire_service.list_answers(questionnaire_id=q.questionnaire_id)
        assert len([a for a in answers2 if a.question_key == "pain_level"]) == 1

        assert await questionnaire_service.delete_answer(questionnaire_id=q.questionnaire_id, question_key="consent") is True
        completed = await questionnaire_service.complete_questionnaire(clinic_id=clinic_id, questionnaire_id=q.questionnaire_id)
        assert completed is not None and completed.status == "completed"
        assert (await questionnaire_service.get_latest_for_booking(clinic_id=clinic_id, booking_id=booking_id)).questionnaire_id == q.questionnaire_id
        assert (await questionnaire_service.get_latest_for_patient(clinic_id=clinic_id, patient_id=patient_id)).questionnaire_id == q.questionnaire_id

        # 7) Media
        a1 = await media_service.register_telegram_asset(
            clinic_id=clinic_id,
            telegram_file_id="file_avatar_smoke",
            telegram_file_unique_id="unique_avatar_smoke",
            media_type="photo",
            mime_type="image/jpeg",
            size_bytes=12345,
        )
        assert a1.telegram_file_unique_id == "unique_avatar_smoke"
        a1u = await media_service.register_telegram_asset(
            clinic_id=clinic_id,
            telegram_file_id="file_avatar_smoke_v2",
            telegram_file_unique_id="unique_avatar_smoke",
            media_type="photo",
            mime_type="image/webp",
            size_bytes=23456,
        )
        assert a1u.media_asset_id == a1.media_asset_id
        assert a1u.mime_type == "image/webp"

        l1 = await media_service.attach_media_to_owner(
            clinic_id=clinic_id,
            media_asset_id=a1.media_asset_id,
            owner_type="patient_profile",
            owner_id=patient_id,
            role="patient_avatar",
        )
        assert l1.visibility == "staff_only" and l1.is_primary is True
        assert (await media_service.get_patient_avatar(clinic_id=clinic_id, patient_id=patient_id)).media_asset_id == a1.media_asset_id

        pa = await media_service.register_telegram_asset(
            clinic_id=clinic_id,
            telegram_file_id="file_product_smoke",
            telegram_file_unique_id="unique_product_smoke",
            media_type="photo",
            mime_type="image/jpeg",
            size_bytes=7654,
        )
        await media_service.attach_media_to_owner(
            clinic_id=clinic_id,
            media_asset_id=pa.media_asset_id,
            owner_type="care_product",
            owner_id="SKU-BRUSH-SOFT",
            role="product_cover",
        )
        assert (await media_service.get_product_cover(clinic_id=clinic_id, product_id="SKU-BRUSH-SOFT")).media_asset_id == pa.media_asset_id

        a2 = await media_service.register_telegram_asset(
            clinic_id=clinic_id,
            telegram_file_id="file_avatar_smoke_2",
            telegram_file_unique_id="unique_avatar_smoke_2",
            media_type="photo",
        )
        l2 = await media_service.attach_media_to_owner(
            clinic_id=clinic_id,
            media_asset_id=a2.media_asset_id,
            owner_type="patient_profile",
            owner_id=patient_id,
            role="patient_avatar",
            is_primary=True,
        )
        all_avatars = await media_service.list_owner_media(clinic_id=clinic_id, owner_type="patient_profile", owner_id=patient_id, role="patient_avatar")
        assert len([link for link, _ in all_avatars if link.is_primary]) == 1
        assert any(link.link_id == l2.link_id and link.is_primary for link, _ in all_avatars)
        assert await media_service.remove_owner_media_link(clinic_id=clinic_id, link_id=l1.link_id) is True
        assert await media_repo.get_media_asset(clinic_id=clinic_id, media_asset_id=a1.media_asset_id) is not None

        # 8) Cross-service compatibility checks
        assert (await selector_service.resolve_for_telegram(clinic_id=clinic_id, telegram_user_id=3001)).mode in {"single_match", "multiple_profiles"}
        assert (await preference_service.get_preferences(patient_id=patient_id)).default_branch_id == "branch_central"
        assert (await questionnaire_service.get_latest_for_patient(clinic_id=clinic_id, patient_id=patient_id)).status == "completed"
        assert await media_service.get_patient_avatar(clinic_id=clinic_id, patient_id=patient_id) is not None

    asyncio.run(_run())
