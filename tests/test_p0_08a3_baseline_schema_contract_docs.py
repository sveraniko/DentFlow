from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DOC = ROOT / "docs/76_patient_profile_family_media_baseline_contract.md"
AUDIT_DOC = ROOT / "docs/75_patient_profile_family_media_gap_audit.md"
ARCH_DOC = ROOT / "docs/74_patient_profile_family_media_architecture.md"
REPORT_DOC = ROOT / "docs/report/P0_08A3_BASELINE_SCHEMA_CONTRACT_REPORT.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_contract_doc_exists() -> None:
    assert CONTRACT_DOC.exists(), "A3 baseline contract doc must exist"


def test_contract_contains_required_markers() -> None:
    text = _read(CONTRACT_DOC)
    required = [
        "baseline schema update",
        "No Alembic",
        "no migrations",
        "patient_profile_details",
        "patient_relationships",
        "patient_preferences",
        "pre_visit_questionnaires",
        "pre_visit_questionnaire_answers",
        "media_assets",
        "media_links",
        "PatientProfileService",
        "PatientFamilyService",
        "PatientPreferenceService",
        "BookingPatientSelectorService",
        "PreVisitQuestionnaireService",
        "PatientMediaService",
        "Кого записываем",
        "patient_avatar",
        "clinical_photo",
        "product_cover",
        "product_gallery",
        "telegram_file_id",
        "telegram_file_unique_id",
        "object_storage",
    ]
    for marker in required:
        assert marker in text, f"Missing marker: {marker}"


def test_gap_audit_links_to_contract() -> None:
    text = _read(AUDIT_DOC)
    assert "docs/76_patient_profile_family_media_baseline_contract.md" in text


def test_architecture_doc_links_to_contract() -> None:
    text = _read(ARCH_DOC)
    assert "docs/76_patient_profile_family_media_baseline_contract.md" in text


def test_report_exists() -> None:
    assert REPORT_DOC.exists(), "A3 report must exist"


def test_docs_do_not_claim_implementation() -> None:
    docs_text = "\n".join([
        _read(CONTRACT_DOC),
        _read(AUDIT_DOC),
        _read(ARCH_DOC),
        _read(REPORT_DOC),
    ]).lower()
    forbidden = [
        "schema implemented",
        "migrations created",
        "ui implemented",
        "media upload implemented",
    ]
    for marker in forbidden:
        assert marker not in docs_text, f"Forbidden claim found: {marker}"
