from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DOC = ROOT / "docs/75_patient_profile_family_media_gap_audit.md"
REPORT_DOC = ROOT / "docs/report/P0_08A2_DB_SERVICE_GAP_BASELINE_PLAN_REPORT.md"
ARCH_DOC = ROOT / "docs/74_patient_profile_family_media_architecture.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_gap_audit_doc_exists() -> None:
    assert AUDIT_DOC.exists(), "Gap audit doc must exist"


def test_gap_audit_doc_has_required_sections_and_no_migration_statement() -> None:
    text = _read(AUDIT_DOC)
    required = [
        "Current DB/service inventory",
        "Profile support gap",
        "Family/dependents support gap",
        "Booking patient selector gap",
        "Notification settings support gap",
        "Branch preference support gap",
        "Documents/questionnaire support gap",
        "Media support gap",
        "Baseline schema update proposal",
        "Service implementation plan",
        "No Alembic and no migrations were created in A2",
    ]
    for marker in required:
        assert marker in text, f"Missing marker: {marker}"


def test_report_exists() -> None:
    assert REPORT_DOC.exists(), "A2 report must exist"


def test_architecture_doc_links_gap_audit() -> None:
    text = _read(ARCH_DOC)
    assert "docs/75_patient_profile_family_media_gap_audit.md" in text


def test_docs_use_baseline_schema_update_phrase() -> None:
    docs_text = "\n".join([_read(AUDIT_DOC), _read(REPORT_DOC), _read(ARCH_DOC)])
    assert "baseline schema update" in docs_text


def test_docs_do_not_claim_implementation_or_migration_creation() -> None:
    docs_text = "\n".join([_read(AUDIT_DOC), _read(REPORT_DOC), _read(ARCH_DOC)]).lower()
    forbidden = [
        "alembic migration exists",
        "profile ui is implemented",
        "media upload is implemented",
        "family cabinet is implemented",
    ]
    for marker in forbidden:
        assert marker not in docs_text, f"Forbidden claim found: {marker}"
