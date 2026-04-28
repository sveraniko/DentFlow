from pathlib import Path


CHECKLIST = Path("docs/runbooks/P0_07C_PATIENT_PRE_LIVE_MANUAL_CHECKLIST.md")
REPORT = Path("docs/report/P0_07C_FINAL_PATIENT_PRE_LIVE_CHECKLIST_REPORT.md")


def _text(path: Path) -> str:
    assert path.exists(), f"Missing required file: {path}"
    return path.read_text(encoding="utf-8")


def test_checklist_exists() -> None:
    assert CHECKLIST.exists()


def test_checklist_contains_required_topics() -> None:
    text = _text(CHECKLIST)
    required = [
        "make seed-demo",
        "DENTFLOW_TEST_DB_DSN",
        "3001",
        "3002",
        "3004",
        "patient_sergey_ivanov",
        "Моя запись",
        "New Booking",
        "IRINA-TREAT",
        "Recommendations",
        "Care catalog",
        "SKU-GEL-REMIN",
        "Repeat/reorder",
        "Blockers",
        "GO/NO-GO",
    ]
    for token in required:
        assert token in text, f"Checklist is missing required token: {token}"


def test_checklist_states_template_only_sheets_boundary() -> None:
    text = _text(CHECKLIST)
    assert "template-only" in text
    assert "not active sync" in text


def test_checklist_states_google_calendar_mirror_boundary() -> None:
    text = _text(CHECKLIST)
    assert "Google Calendar" in text
    assert "one-way mirror" in text


def test_checklist_includes_evidence_collection() -> None:
    text = _text(CHECKLIST)
    assert "Evidence collection" in text
    assert "Screenshots" in text
    assert "log" in text.lower()


def test_report_exists() -> None:
    assert REPORT.exists()
