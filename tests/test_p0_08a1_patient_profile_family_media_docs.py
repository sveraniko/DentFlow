from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCH_DOC = ROOT / "docs/74_patient_profile_family_media_architecture.md"
SCOPE_DOC = ROOT / "docs/report/P0_08_PATIENT_PROFILE_FAMILY_SCOPE_PROPOSAL.md"
REPORT_DOC = ROOT / "docs/report/P0_08A1_PATIENT_PROFILE_FAMILY_MEDIA_FOUNDATION_REPORT.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_architecture_doc_exists() -> None:
    assert ARCH_DOC.exists(), "Architecture doc must exist"


def test_architecture_doc_contains_required_foundation_terms() -> None:
    text = _read(ARCH_DOC)
    required = [
        "Quick booking remains short",
        "minimal name",
        "Profile and family cabinet",
        "Telegram account manages multiple patient profiles",
        "Кого записываем?",
        "notification settings",
        "branch preference",
        "pre-visit questionnaire",
        "MediaAsset",
        "MediaLink",
        "telegram",
        "object_storage",
        "patient_avatar",
        "product_cover",
        "product_gallery",
        "clinical_photo",
        "optional and not forced",
        "TradeFlow media manager",
        "P0-08A2",
        "P0-08B",
        "P0-08C",
        "P0-08D",
        "P0-08E",
        "P0-08F",
        "P0-08G",
        "P0-08M0",
        "P0-08M1",
    ]
    for marker in required:
        assert marker in text, f"Missing marker: {marker}"


def test_scope_proposal_references_architecture_doc() -> None:
    text = _read(SCOPE_DOC)
    assert "docs/74_patient_profile_family_media_architecture.md" in text


def test_report_exists() -> None:
    assert REPORT_DOC.exists(), "A1 foundation report must exist"


def test_docs_do_not_claim_media_upload_already_implemented() -> None:
    docs_text = "\n".join([_read(ARCH_DOC), _read(SCOPE_DOC), _read(REPORT_DOC)])
    lowered = docs_text.lower()
    assert "media upload is implemented now" not in lowered
    assert "media upload already implemented" not in lowered


def test_docs_do_not_claim_profile_or_family_cabinet_implemented() -> None:
    docs_text = "\n".join([_read(ARCH_DOC), _read(SCOPE_DOC), _read(REPORT_DOC)])
    lowered = docs_text.lower()
    assert "profile cabinet is implemented now" not in lowered
    assert "family cabinet is implemented now" not in lowered
