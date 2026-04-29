from app.domain.media import MediaAsset, MediaLink
from app.domain.patient_registry import (
    PatientPreference,
    PatientProfileDetails,
    PatientRelationship,
    PreVisitQuestionnaire,
    PreVisitQuestionnaireAnswer,
)
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "app/infrastructure/db/bootstrap.py"
A3_DOC_TEST = ROOT / "tests/test_p0_08a3_baseline_schema_contract_docs.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_bootstrap_contains_a4a_schema_markers() -> None:
    text = _read(BOOTSTRAP)
    for marker in [
        "core_patient.patient_profile_details",
        "core_patient.patient_relationships",
        "core_patient.pre_visit_questionnaires",
        "core_patient.pre_visit_questionnaire_answers",
        "media_docs.media_links",
        "notification_recipient_strategy",
        "quiet_hours_start",
        "default_branch_id",
        "allow_any_branch",
        "telegram_file_id",
        "telegram_file_unique_id",
        "object_key",
        "uploaded_by_actor_id",
    ]:
        assert marker in text


def test_single_media_assets_create_definition() -> None:
    text = _read(BOOTSTRAP)
    assert text.count("CREATE TABLE IF NOT EXISTS media_docs.media_assets") == 1


def test_patient_domain_models_instantiate() -> None:
    assert PatientProfileDetails(patient_id="p1", clinic_id="c1")
    assert PatientRelationship(
        relationship_id="r1",
        clinic_id="c1",
        manager_patient_id="p1",
        related_patient_id="p2",
        relationship_type="guardian",
    )
    assert PatientPreference(
        patient_preference_id="pref1",
        patient_id="p1",
        notification_recipient_strategy="manager",
        quiet_hours_start="22:00",
        quiet_hours_end="08:00",
        quiet_hours_timezone="UTC",
        default_branch_id="b1",
        allow_any_branch=False,
    )
    assert PreVisitQuestionnaire(
        questionnaire_id="q1",
        clinic_id="c1",
        patient_id="p1",
        questionnaire_type="intake",
        status="completed",
    )
    assert PreVisitQuestionnaireAnswer(
        answer_id="a1",
        questionnaire_id="q1",
        question_key="allergy",
        answer_value={"value": "none"},
        answer_type="text",
    )


def test_media_domain_models_instantiate() -> None:
    assert MediaAsset(
        media_asset_id="m1",
        clinic_id="c1",
        asset_kind="patient_avatar",
        storage_provider="telegram",
        storage_ref="ref",
    )
    assert MediaLink(
        link_id="l1",
        clinic_id="c1",
        media_asset_id="m1",
        owner_type="patient",
        owner_id="p1",
        role="avatar",
        visibility="staff",
    )


def test_no_alembic_versions_added() -> None:
    assert not (ROOT / "alembic/versions").exists()


def test_a3_doc_tests_still_present() -> None:
    assert A3_DOC_TEST.exists()
