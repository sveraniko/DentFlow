from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "docs/templates/google_sheets/reference_and_patients"
STACK1 = ROOT / "seeds/stack1_seed.json"
STACK2 = ROOT / "seeds/stack2_patients.json"
MANIFEST_PATH = TEMPLATE_DIR / "reference_patient_sheets_manifest.json"
README_PATH = TEMPLATE_DIR / "README.md"

TABS = (
    "branches",
    "doctors",
    "services",
    "doctor_access_codes",
    "patients",
    "patient_contacts",
    "patient_preferences",
)


def _read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return next(csv.reader(handle))


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_p0_06e3_template_files_exist() -> None:
    for tab in TABS:
        assert (TEMPLATE_DIR / f"{tab}.csv").exists()
        assert (TEMPLATE_DIR / f"demo_{tab}.csv").exists()
    assert README_PATH.exists()
    assert MANIFEST_PATH.exists()


def test_p0_06e3_headers_match_manifest() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for tab in TABS:
        assert _read_header(TEMPLATE_DIR / f"{tab}.csv") == manifest["columns"][tab]


def test_p0_06e3_demo_contains_d2a2_ids() -> None:
    doctor_ids = {row["doctor_id"] for row in _read_rows(TEMPLATE_DIR / "demo_doctors.csv")}
    assert {"doctor_anna", "doctor_boris", "doctor_irina"}.issubset(doctor_ids)

    service_ids = {row["service_id"] for row in _read_rows(TEMPLATE_DIR / "demo_services.csv")}
    assert {"service_consult", "service_cleaning", "service_treatment", "service_urgent"}.issubset(service_ids)

    code_ids = {row["code"] for row in _read_rows(TEMPLATE_DIR / "demo_doctor_access_codes.csv")}
    assert {"ANNA-001", "BORIS-HYG", "IRINA-TREAT"}.issubset(code_ids)

    contacts = _read_rows(TEMPLATE_DIR / "demo_patient_contacts.csv")
    assert any(row["contact_type"] == "telegram" and row["contact_value"] == "3001" for row in contacts)
    assert any(row["contact_type"] == "telegram" and row["contact_value"] == "3002" for row in contacts)
    assert any(row["contact_type"] == "telegram" and row["contact_value"] == "3004" for row in contacts)


def test_p0_06e3_demo_references_valid() -> None:
    branches = {row["branch_id"] for row in _read_rows(TEMPLATE_DIR / "demo_branches.csv")}
    doctors = _read_rows(TEMPLATE_DIR / "demo_doctors.csv")
    doctor_ids = {row["doctor_id"] for row in doctors}
    services = {row["service_id"] for row in _read_rows(TEMPLATE_DIR / "demo_services.csv")}
    patients = {row["patient_id"] for row in _read_rows(TEMPLATE_DIR / "demo_patients.csv")}

    for doctor in doctors:
        assert doctor["default_branch_id"] in branches

    for row in _read_rows(TEMPLATE_DIR / "demo_doctor_access_codes.csv"):
        assert row["doctor_id"] in doctor_ids
        for svc in [item.strip() for item in row["service_scope"].split(",") if item.strip()]:
            assert svc in services

    for row in _read_rows(TEMPLATE_DIR / "demo_patient_contacts.csv"):
        assert row["patient_id"] in patients

    for row in _read_rows(TEMPLATE_DIR / "demo_patient_preferences.csv"):
        assert row["patient_id"] in patients


def test_p0_06e3_demo_counts_match_seed_json() -> None:
    stack1 = json.loads(STACK1.read_text(encoding="utf-8"))
    stack2 = json.loads(STACK2.read_text(encoding="utf-8"))

    assert len(_read_rows(TEMPLATE_DIR / "demo_branches.csv")) == len(stack1["branches"])
    assert len(_read_rows(TEMPLATE_DIR / "demo_doctors.csv")) == len(stack1["doctors"])
    assert len(_read_rows(TEMPLATE_DIR / "demo_services.csv")) == len(stack1["services"])
    assert len(_read_rows(TEMPLATE_DIR / "demo_doctor_access_codes.csv")) == len(stack1["doctor_access_codes"])
    assert len(_read_rows(TEMPLATE_DIR / "demo_patients.csv")) == len(stack2["patients"])
    assert len(_read_rows(TEMPLATE_DIR / "demo_patient_contacts.csv")) == len(stack2["patient_contacts"])

    pref_rows = _read_rows(TEMPLATE_DIR / "demo_patient_preferences.csv")
    pref_ids = {row["patient_id"] for row in pref_rows}
    seed_pref_ids = {row["patient_id"] for row in stack2["patient_preferences"]}
    assert pref_ids == seed_pref_ids


def test_p0_06e3_readme_truth_boundary() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    required = [
        "not implemented",
        "template only",
        "Care catalog Sheets sync exists",
        "Reference/patient Sheets sync is not implemented",
        "seed_demo.py",
    ]
    for phrase in required:
        assert phrase in readme


def test_p0_06e3_docs_truth_boundary() -> None:
    docs = [
        ROOT / "docs/92_seed_data_and_demo_fixtures.md",
        ROOT / "docs/80_integrations_and_infra.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    assert "reference_and_patients" in text

    bad_claims = [
        "Reference/patient Sheets sync is active",
        "patients/doctors/services Sheets sync is active",
    ]
    for phrase in bad_claims:
        assert phrase not in text


def test_p0_06e3_manifest_validity() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["import_status"] == "template_only"
    assert set(manifest["tabs"]) == set(TABS)
