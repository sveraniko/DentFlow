from __future__ import annotations

import csv
import json
from pathlib import Path

from app.application.care_catalog_sync.parser import parse_catalog_workbook


ROOT = Path(__file__).resolve().parents[1]
CARE_DIR = ROOT / "docs/templates/google_sheets/care_catalog"
REF_PAT_DIR = ROOT / "docs/templates/google_sheets/reference_and_patients"
CAL_RUNBOOK = ROOT / "docs/runbooks/google_calendar_projection_runbook.md"
INTEGRATIONS_DOC = ROOT / "docs/80_integrations_and_infra.md"
SEED_DOC = ROOT / "docs/92_seed_data_and_demo_fixtures.md"
PRELIVE_RUNBOOK = ROOT / "docs/runbooks/pre_live_integration_checklist.md"
ENV_EXAMPLE = ROOT / ".env.example"
MAKEFILE = ROOT / "Makefile"

CARE_TABS = (
    "products",
    "product_i18n",
    "branch_availability",
    "recommendation_sets",
    "recommendation_set_items",
    "recommendation_links",
    "settings",
)

REF_PAT_TABS = (
    "branches",
    "doctors",
    "services",
    "doctor_access_codes",
    "patients",
    "patient_contacts",
    "patient_preferences",
)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_text(paths: list[Path]) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in paths if path.exists())


def test_p0_06e4_care_catalog_template_sync_readiness() -> None:
    assert (CARE_DIR / "README.md").exists()

    for tab in CARE_TABS:
        assert (CARE_DIR / f"{tab}.csv").exists(), f"missing blank care catalog csv: {tab}"
        assert (CARE_DIR / f"demo_{tab}.csv").exists(), f"missing demo care catalog csv: {tab}"

    readme = (CARE_DIR / "README.md").read_text(encoding="utf-8")
    required_phrases = [
        "Required Google Sheets tab names",
        "products",
        "product_i18n",
        "branch_availability",
        "python scripts/sync_care_catalog.py --clinic-id clinic_main json --path",
        "python scripts/sync_care_catalog.py --clinic-id clinic_main xlsx --path",
        "python scripts/sync_care_catalog.py --clinic-id clinic_main sheets --sheet",
        "/admin_catalog_sync sheets <url_or_id>",
        "accessible for export",
        "Validation rules",
    ]
    for phrase in required_phrases:
        assert phrase in readme


def test_p0_06e4_care_catalog_demo_csv_parses() -> None:
    workbook = {tab: _read_csv_rows(CARE_DIR / f"demo_{tab}.csv") for tab in CARE_TABS}
    parsed, result = parse_catalog_workbook(
        workbook=workbook,
        known_branch_ids={"branch_central"},
        source="csv_template",
    )

    assert parsed is not None
    assert not result.fatal_errors
    assert not result.validation_errors


def test_p0_06e4_reference_patient_template_readiness() -> None:
    assert (REF_PAT_DIR / "README.md").exists()
    assert (REF_PAT_DIR / "reference_patient_sheets_manifest.json").exists()

    for tab in REF_PAT_TABS:
        assert (REF_PAT_DIR / f"{tab}.csv").exists(), f"missing blank reference/patient csv: {tab}"
        assert (REF_PAT_DIR / f"demo_{tab}.csv").exists(), f"missing demo reference/patient csv: {tab}"

    manifest = json.loads((REF_PAT_DIR / "reference_patient_sheets_manifest.json").read_text(encoding="utf-8"))
    assert manifest["import_status"] == "template_only"

    boundary_text = _load_text([
        REF_PAT_DIR / "README.md",
        INTEGRATIONS_DOC,
        SEED_DOC,
    ])
    for required in (
        "not implemented",
        "template only",
        "seed_demo.py",
        "future",
    ):
        assert required in boundary_text

    assert "sync_reference_patient_sheets.py" in boundary_text


def test_p0_06e4_google_calendar_readiness() -> None:
    assert CAL_RUNBOOK.exists()
    text = CAL_RUNBOOK.read_text(encoding="utf-8")

    for phrase in (
        "DentFlow is the booking truth",
        "one-way",
        "mirror",
        "No Calendar-to-DentFlow sync",
        "/admin_calendar",
        "/admin_integrations",
        "process_outbox_events.py",
        "retry_google_calendar_projection.py",
    ):
        assert phrase in text

    env_text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for key in (
        "INTEGRATIONS_GOOGLE_CALENDAR_ENABLED",
        "INTEGRATIONS_GOOGLE_CALENDAR_CREDENTIALS_PATH",
        "INTEGRATIONS_GOOGLE_CALENDAR_SUBJECT_EMAIL",
        "INTEGRATIONS_GOOGLE_CALENDAR_APPLICATION_NAME",
        "INTEGRATIONS_GOOGLE_CALENDAR_TIMEOUT_SEC",
        "INTEGRATIONS_DENTFLOW_BASE_URL",
    ):
        assert f"{key}=" in env_text


def test_p0_06e4_seed_demo_readiness_boundary() -> None:
    make_text = MAKEFILE.read_text(encoding="utf-8")
    assert "seed-demo:" in make_text
    assert "python scripts/seed_demo.py --relative-dates" in make_text

    docs_text = _load_text([SEED_DOC, PRELIVE_RUNBOOK])
    for phrase in (
        "make seed-demo",
        "scripts/seed_demo.py --relative-dates",
        "stack1",
        "stack2",
        "stack3",
        "care catalog",
        "recommendations + care orders",
        "do not call Google Calendar",
        "do not import Reference/Patient Google Sheets templates",
    ):
        assert phrase in docs_text


def test_p0_06e4_false_claim_guard() -> None:
    docs_to_scan = [
        REF_PAT_DIR / "README.md",
        INTEGRATIONS_DOC,
        SEED_DOC,
        CAL_RUNBOOK,
    ]
    if PRELIVE_RUNBOOK.exists():
        docs_to_scan.append(PRELIVE_RUNBOOK)

    joined = _load_text(docs_to_scan)

    forbidden_claims = [
        "Calendar edits update DentFlow",
        "Calendar is source of truth",
        "two-way sync is enabled",
        "patients Google Sheets sync is active",
        "doctors Google Sheets sync is active",
        "services Google Sheets sync is active",
        "sync_reference_patient_sheets.py is available",
        "reference patient sheets are automatically imported",
    ]

    for phrase in forbidden_claims:
        assert phrase not in joined


def test_p0_06e4_report_files_exist_and_prereq_tests_present() -> None:
    for report_path in (
        ROOT / "docs/report/P0_06E1_CARE_CATALOG_GOOGLE_SHEETS_TEMPLATE_REPORT.md",
        ROOT / "docs/report/P0_06E2_GOOGLE_CALENDAR_RUNBOOK_CONFIG_REPORT.md",
        ROOT / "docs/report/P0_06E3_REFERENCE_PATIENT_SHEETS_TEMPLATES_REPORT.md",
    ):
        assert report_path.exists()

    for matrix in (
        ROOT / "docs/p0-06e1-matrix.md",
        ROOT / "docs/p0-06e2-matrix.md",
        ROOT / "docs/p0-06e3-matrix.md",
    ):
        if matrix.exists():
            assert matrix.read_text(encoding="utf-8").strip()

    for test_path in (
        ROOT / "tests/test_p0_06e1_care_catalog_sheets_template.py",
        ROOT / "tests/test_p0_06e2_google_calendar_runbook_config.py",
        ROOT / "tests/test_p0_06e3_reference_patient_sheets_templates.py",
        ROOT / "tests/test_p0_06d2c_seed_demo_bootstrap.py",
    ):
        assert test_path.exists()
