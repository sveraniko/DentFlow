from __future__ import annotations

from datetime import datetime, timezone

from app.domain.media import MediaAsset, MediaLink
from app.domain.patient_registry import (
    PatientProfileDetails,
    PatientRelationship,
    PreVisitQuestionnaire,
    PreVisitQuestionnaireAnswer,
)
from app.infrastructure.db.media_repository import DbMediaRepository
from app.infrastructure.db.patient_repository import DbPatientRegistryRepository
from tests.helpers.seed_demo_db_harness import (
    run_seed_demo_bootstrap_for_tests,
    safe_test_db_config,
    reset_test_db,
)


def test_p0_08a4b4_repository_db_smoke() -> None:
    import asyncio

    async def _run() -> None:
        db_config = safe_test_db_config()
        await reset_test_db(db_config)
        await run_seed_demo_bootstrap_for_tests(db_config)

        patient_repo = DbPatientRegistryRepository(db_config)
        media_repo = DbMediaRepository(db_config)

        clinic_id = "clinic_main"
        patient_id = "patient_sergey_ivanov"
        related_id = "patient_maria_petrova"

        # 1) Profile details
        initial_profile = await patient_repo.get_profile_details(clinic_id=clinic_id, patient_id=patient_id)
        profile = PatientProfileDetails(
            patient_id=patient_id,
            clinic_id=clinic_id,
            email="sergey.initial@example.test",
            city="Moscow",
            country_code="RU",
            emergency_contact_name="Maria Petrova",
            emergency_contact_phone="+79991234567",
            profile_completion_state="partial",
        )
        created_profile = await patient_repo.upsert_profile_details(profile)
        fetched_profile = await patient_repo.get_profile_details(clinic_id=clinic_id, patient_id=patient_id)
        assert fetched_profile is not None
        assert fetched_profile.email == "sergey.initial@example.test"
        assert fetched_profile.profile_completion_state == "partial"

        completed_at = datetime.now(timezone.utc)
        updated_profile = await patient_repo.upsert_profile_details(
            PatientProfileDetails(
                patient_id=patient_id,
                clinic_id=clinic_id,
                email="sergey.completed@example.test",
                city="Moscow",
                country_code="RU",
                emergency_contact_name="Maria Petrova",
                emergency_contact_phone="+79991234567",
                profile_completion_state="completed",
                profile_completed_at=completed_at,
                created_at=created_profile.created_at,
            )
        )
        state = await patient_repo.get_profile_completion_state(clinic_id=clinic_id, patient_id=patient_id)
        assert updated_profile.email == "sergey.completed@example.test"
        assert updated_profile.created_at == created_profile.created_at
        assert updated_profile.updated_at is not None
        assert state == "completed"
        if initial_profile is not None:
            assert initial_profile.patient_id == patient_id

        # 2) Relationships / linked profiles
        relationship = await patient_repo.upsert_relationship(
            PatientRelationship(
                relationship_id="rel_smoke_sergey_maria",
                clinic_id=clinic_id,
                manager_patient_id=patient_id,
                related_patient_id=related_id,
                relationship_type="child",
                consent_status="active",
                is_default_for_booking=True,
                is_default_notification_recipient=True,
            )
        )
        active_relationships = await patient_repo.list_relationships(clinic_id=clinic_id, manager_patient_id=patient_id)
        assert any(r.relationship_id == relationship.relationship_id for r in active_relationships)

        linked_active = await patient_repo.list_linked_profiles_for_telegram(
            clinic_id=clinic_id,
            telegram_user_id=3001,
        )
        linked_active_ids = [p.patient_id for p in linked_active]
        assert patient_id in linked_active_ids and related_id in linked_active_ids

        deactivated = await patient_repo.deactivate_relationship(clinic_id=clinic_id, relationship_id=relationship.relationship_id)
        assert deactivated is not None
        assert deactivated.consent_status == "revoked"
        active_after = await patient_repo.list_relationships(clinic_id=clinic_id, manager_patient_id=patient_id)
        all_after = await patient_repo.list_relationships(
            clinic_id=clinic_id, manager_patient_id=patient_id, include_inactive=True
        )
        assert all(r.relationship_id != relationship.relationship_id for r in active_after)
        assert any(r.relationship_id == relationship.relationship_id for r in all_after)

        linked_after = await patient_repo.list_linked_profiles_for_telegram(clinic_id=clinic_id, telegram_user_id=3001)
        linked_after_inactive = await patient_repo.list_linked_profiles_for_telegram(
            clinic_id=clinic_id,
            telegram_user_id=3001,
            include_inactive=True,
        )
        assert related_id not in [p.patient_id for p in linked_after]
        assert related_id in [p.patient_id for p in linked_after_inactive]

        # 3) Preferences
        before_pref = await patient_repo.get_patient_preferences(patient_id=patient_id)
        assert before_pref is not None
        await patient_repo.update_notification_preferences(
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
        await patient_repo.update_branch_preferences(
            patient_id=patient_id,
            default_branch_id="branch_central",
            allow_any_branch=False,
        )
        after_pref = await patient_repo.get_patient_preferences(patient_id=patient_id)
        assert after_pref is not None
        assert after_pref.preferred_reminder_channel == "telegram"
        assert after_pref.allow_sms is False and after_pref.allow_telegram is True and after_pref.allow_call is True
        assert after_pref.default_branch_id == "branch_central"
        assert after_pref.preferred_language == before_pref.preferred_language

        # 4) Questionnaire
        questionnaire = await patient_repo.upsert_pre_visit_questionnaire(
            PreVisitQuestionnaire(
                questionnaire_id="pvq_smoke_sergey",
                clinic_id=clinic_id,
                patient_id=patient_id,
                booking_id="bkg_sergey_confirmed",
                questionnaire_type="pre_visit",
                status="in_progress",
                version=1,
            )
        )
        fetched_q = await patient_repo.get_pre_visit_questionnaire(clinic_id=clinic_id, questionnaire_id=questionnaire.questionnaire_id)
        by_patient = await patient_repo.list_pre_visit_questionnaires(clinic_id=clinic_id, patient_id=patient_id)
        by_booking = await patient_repo.list_pre_visit_questionnaires(
            clinic_id=clinic_id,
            patient_id=patient_id,
            booking_id="bkg_sergey_confirmed",
        )
        assert fetched_q is not None
        assert any(q.questionnaire_id == "pvq_smoke_sergey" for q in by_patient)
        assert any(q.questionnaire_id == "pvq_smoke_sergey" for q in by_booking)

        await patient_repo.upsert_pre_visit_questionnaire_answers([
            PreVisitQuestionnaireAnswer("ans_allergies", "pvq_smoke_sergey", "allergies", {"value": "latex"}, "json"),
            PreVisitQuestionnaireAnswer("ans_meds", "pvq_smoke_sergey", "medications", ["ibuprofen"], "json"),
            PreVisitQuestionnaireAnswer("ans_pain", "pvq_smoke_sergey", "pain_level", 3, "json"),
            PreVisitQuestionnaireAnswer("ans_consent", "pvq_smoke_sergey", "consent", True, "json"),
        ])
        answers = await patient_repo.list_pre_visit_questionnaire_answers(questionnaire_id="pvq_smoke_sergey")
        by_key = {a.question_key: a.answer_value for a in answers}
        assert by_key["allergies"] == {"value": "latex"}
        assert by_key["medications"] == ["ibuprofen"]
        assert by_key["pain_level"] == 3
        assert by_key["consent"] is True

        await patient_repo.upsert_pre_visit_questionnaire_answer(
            PreVisitQuestionnaireAnswer("ans_pain", "pvq_smoke_sergey", "pain_level", 5, "json")
        )
        deleted = await patient_repo.delete_pre_visit_questionnaire_answer(
            questionnaire_id="pvq_smoke_sergey", question_key="consent"
        )
        assert deleted is True

        completed = await patient_repo.complete_pre_visit_questionnaire(clinic_id=clinic_id, questionnaire_id="pvq_smoke_sergey")
        assert completed is not None and completed.status == "completed" and completed.completed_at is not None
        latest_booking = await patient_repo.get_latest_pre_visit_questionnaire_for_booking(
            clinic_id=clinic_id, booking_id="bkg_sergey_confirmed"
        )
        latest_patient = await patient_repo.get_latest_pre_visit_questionnaire_for_patient(
            clinic_id=clinic_id, patient_id=patient_id
        )
        assert latest_booking is not None and latest_booking.questionnaire_id == "pvq_smoke_sergey"
        assert latest_patient is not None and latest_patient.questionnaire_id == "pvq_smoke_sergey"

        # 5) Media assets
        now = datetime.now(timezone.utc)
        asset = await media_repo.upsert_media_asset(
            MediaAsset(
                media_asset_id="media_smoke_avatar_1",
                clinic_id=clinic_id,
                asset_kind="photo",
                storage_provider="telegram",
                storage_ref="file_avatar_1",
                content_type="image/jpeg",
                byte_size=12345,
                media_type="photo",
                mime_type="image/jpeg",
                size_bytes=12345,
                telegram_file_id="file_avatar_1",
                telegram_file_unique_id="unique_avatar_1",
                uploaded_by_actor_id=None,
                created_at=now,
                updated_at=now,
            )
        )
        fetched_asset = await media_repo.get_media_asset(clinic_id=clinic_id, media_asset_id="media_smoke_avatar_1")
        by_unique = await media_repo.find_media_asset_by_telegram_file_unique_id(
            clinic_id=clinic_id, telegram_file_unique_id="unique_avatar_1"
        )
        updated_asset = await media_repo.upsert_media_asset(
            MediaAsset(
                media_asset_id="media_smoke_avatar_1",
                clinic_id=clinic_id,
                asset_kind="photo",
                storage_provider="telegram",
                storage_ref="file_avatar_1_v2",
                content_type="image/jpeg",
                byte_size=12345,
                media_type="photo",
                mime_type="image/webp",
                size_bytes=12345,
                telegram_file_id="file_avatar_1",
                telegram_file_unique_id="unique_avatar_1",
                object_key="avatars/sergey-1",
                created_at=asset.created_at,
                updated_at=datetime.now(timezone.utc),
            )
        )
        listed_assets = await media_repo.list_media_assets_by_ids(clinic_id=clinic_id, media_asset_ids=["media_smoke_avatar_1"])
        assert fetched_asset is not None and by_unique is not None
        assert updated_asset.mime_type == "image/webp"
        assert listed_assets and listed_assets[0].media_asset_id == "media_smoke_avatar_1"

        compat_asset = await media_repo.upsert_media_asset(
            MediaAsset(
                media_asset_id="media_smoke_legacy_1",
                clinic_id=clinic_id,
                asset_kind="photo",
                storage_provider="telegram",
                storage_ref="legacy_ref",
                content_type="image/png",
                byte_size=222,
            )
        )
        assert compat_asset.media_type in {"photo", "image"}
        assert compat_asset.mime_type == "image/png"
        assert compat_asset.size_bytes == 222

        # 6) Media links
        await media_repo.upsert_media_asset(MediaAsset("media_smoke_avatar_2", clinic_id, "photo", "telegram", "file_avatar_2", media_type="photo", mime_type="image/jpeg"))
        await media_repo.attach_media(MediaLink("link_avatar_1", clinic_id, "media_smoke_avatar_1", "patient_profile", patient_id, "patient_avatar", "staff_only", 0, True))
        await media_repo.attach_media(MediaLink("link_avatar_2", clinic_id, "media_smoke_avatar_2", "patient_profile", patient_id, "patient_avatar", "staff_only", 1, False))

        selected = await media_repo.set_primary_media(clinic_id=clinic_id, owner_type="patient_profile", owner_id=patient_id, role="patient_avatar", link_id="link_avatar_2")
        links = await media_repo.list_media_links(clinic_id=clinic_id, owner_type="patient_profile", owner_id=patient_id, role="patient_avatar")
        joined = await media_repo.list_media_for_owner(clinic_id=clinic_id, owner_type="patient_profile", owner_id=patient_id, role="patient_avatar")
        assert selected is not None and selected.link_id == "link_avatar_2"
        assert sum(1 for link in links if link.is_primary) == 1
        assert links[0].is_primary is True
        assert len(joined) == 2

        missing_primary = await media_repo.set_primary_media(
            clinic_id=clinic_id, owner_type="patient_profile", owner_id=patient_id, role="patient_avatar", link_id="missing-link-id"
        )
        links_after_missing = await media_repo.list_media_links(clinic_id=clinic_id, owner_type="patient_profile", owner_id=patient_id, role="patient_avatar")
        assert missing_primary is None
        assert [l.link_id for l in links] == [l.link_id for l in links_after_missing]
        assert [l.is_primary for l in links] == [l.is_primary for l in links_after_missing]

        removed = await media_repo.remove_media_link(clinic_id=clinic_id, link_id="link_avatar_1")
        assert removed is True
        asset_still = await media_repo.get_media_asset(clinic_id=clinic_id, media_asset_id="media_smoke_avatar_1")
        assert asset_still is not None

        await media_repo.upsert_media_asset(MediaAsset("media_product_cover", clinic_id, "photo", "telegram", "prd_cover", media_type="photo", mime_type="image/jpeg"))
        await media_repo.upsert_media_asset(MediaAsset("media_product_gallery", clinic_id, "photo", "telegram", "prd_gallery", media_type="photo", mime_type="image/jpeg"))
        await media_repo.attach_media(MediaLink("link_product_cover", clinic_id, "media_product_cover", "care_product", "SKU-BRUSH-SOFT", "product_cover", "public", 0, True))
        await media_repo.attach_media(MediaLink("link_product_gallery", clinic_id, "media_product_gallery", "care_product", "SKU-BRUSH-SOFT", "product_gallery", "public", 0, True))
        cover = await media_repo.list_media_links(clinic_id=clinic_id, owner_type="care_product", owner_id="SKU-BRUSH-SOFT", role="product_cover")
        gallery = await media_repo.list_media_links(clinic_id=clinic_id, owner_type="care_product", owner_id="SKU-BRUSH-SOFT", role="product_gallery")
        assert len(cover) == 1 and len(gallery) == 1

        # 7) Cross-repo compatibility checks
        assert await patient_repo.list_linked_profiles_for_telegram(clinic_id=clinic_id, telegram_user_id=3001)
        assert await patient_repo.get_patient_preferences(patient_id=patient_id)
        assert await patient_repo.get_latest_pre_visit_questionnaire_for_patient(clinic_id=clinic_id, patient_id=patient_id)
        assert await media_repo.list_media_for_owner(clinic_id=clinic_id, owner_type="patient_profile", owner_id=patient_id, role="patient_avatar")

    asyncio.run(_run())
