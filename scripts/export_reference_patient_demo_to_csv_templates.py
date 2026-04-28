from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs/templates/google_sheets/reference_and_patients"
STACK1 = ROOT / "seeds/stack1_seed.json"
STACK2 = ROOT / "seeds/stack2_patients.json"

COLUMNS: dict[str, list[str]] = {
    "branches": [
        "branch_id",
        "clinic_id",
        "display_name",
        "timezone",
        "locale",
        "address",
        "phone",
        "is_active",
    ],
    "doctors": [
        "doctor_id",
        "clinic_id",
        "display_name",
        "specialty",
        "public_booking_enabled",
        "is_active",
        "default_branch_id",
        "sort_order",
    ],
    "services": [
        "service_id",
        "clinic_id",
        "code",
        "title_key",
        "duration_minutes",
        "category",
        "is_active",
        "sort_order",
    ],
    "doctor_access_codes": [
        "code",
        "clinic_id",
        "doctor_id",
        "service_scope",
        "branch_scope",
        "starts_at",
        "expires_at",
        "is_active",
        "note",
    ],
    "patients": [
        "patient_id",
        "clinic_id",
        "full_name",
        "preferred_language",
        "birth_date",
        "sex",
        "notes",
        "is_active",
    ],
    "patient_contacts": [
        "patient_id",
        "clinic_id",
        "contact_type",
        "contact_value",
        "is_primary",
        "verified_at",
        "note",
    ],
    "patient_preferences": [
        "patient_id",
        "clinic_id",
        "preferred_language",
        "preferred_reminder_channel",
        "allow_telegram",
        "allow_sms",
        "contact_time_window",
        "timezone",
    ],
}


def _tf(value: bool) -> str:
    return "true" if value else "false"


def _status_to_active(status: str | None) -> str:
    return _tf((status or "").lower() == "active")


def _write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stack1 = json.loads(STACK1.read_text(encoding="utf-8"))
    stack2 = json.loads(STACK2.read_text(encoding="utf-8"))

    clinic_locale = {
        row["clinic_id"]: row.get("default_locale", "") for row in stack1.get("clinics", [])
    }
    clinic_timezone = {row["clinic_id"]: row.get("timezone", "") for row in stack1.get("clinics", [])}
    patient_pref_lang = {
        row["patient_id"]: row.get("preferred_language", "") for row in stack2.get("patient_preferences", [])
    }

    demo: dict[str, list[dict[str, str]]] = {
        "branches": [
            {
                "branch_id": row["branch_id"],
                "clinic_id": row["clinic_id"],
                "display_name": row.get("display_name", ""),
                "timezone": row.get("timezone", ""),
                "locale": clinic_locale.get(row["clinic_id"], ""),
                "address": row.get("address_text", ""),
                "phone": "",
                "is_active": _status_to_active(row.get("status")),
            }
            for row in stack1.get("branches", [])
        ],
        "doctors": [
            {
                "doctor_id": row["doctor_id"],
                "clinic_id": row["clinic_id"],
                "display_name": row.get("display_name", ""),
                "specialty": row.get("specialty_code", ""),
                "public_booking_enabled": _tf(bool(row.get("public_booking_enabled", False))),
                "is_active": _status_to_active(row.get("status")),
                "default_branch_id": row.get("branch_id", ""),
                "sort_order": str(idx + 1),
            }
            for idx, row in enumerate(stack1.get("doctors", []))
        ],
        "services": [
            {
                "service_id": row["service_id"],
                "clinic_id": row["clinic_id"],
                "code": row.get("code", ""),
                "title_key": row.get("title_key", ""),
                "duration_minutes": str(row.get("duration_minutes", "")),
                "category": row.get("specialty_required", ""),
                "is_active": _status_to_active(row.get("status")),
                "sort_order": str(idx + 1),
            }
            for idx, row in enumerate(stack1.get("services", []))
        ],
        "doctor_access_codes": [
            {
                "code": row.get("code", ""),
                "clinic_id": row["clinic_id"],
                "doctor_id": row["doctor_id"],
                "service_scope": ",".join(row.get("service_scope", [])),
                "branch_scope": ",".join(row.get("branch_scope", [])),
                "starts_at": "",
                "expires_at": row.get("expires_at", "") or "",
                "is_active": _status_to_active(row.get("status")),
                "note": "",
            }
            for row in stack1.get("doctor_access_codes", [])
        ],
        "patients": [
            {
                "patient_id": row["patient_id"],
                "clinic_id": row["clinic_id"],
                "full_name": row.get("display_name") or row.get("full_name_legal", ""),
                "preferred_language": patient_pref_lang.get(row["patient_id"], ""),
                "birth_date": row.get("birth_date", "") or "",
                "sex": row.get("sex_marker", "") or "",
                "notes": "",
                "is_active": _status_to_active(row.get("status", "active")),
            }
            for row in stack2.get("patients", [])
        ],
        "patient_contacts": [
            {
                "patient_id": row["patient_id"],
                "clinic_id": next(
                    (p["clinic_id"] for p in stack2.get("patients", []) if p["patient_id"] == row["patient_id"]),
                    "",
                ),
                "contact_type": row.get("contact_type", ""),
                "contact_value": str(row.get("contact_value", "")),
                "is_primary": _tf(bool(row.get("is_primary", False))),
                "verified_at": "",
                "note": row.get("notes", "") or "",
            }
            for row in stack2.get("patient_contacts", [])
        ],
        "patient_preferences": [
            {
                "patient_id": row["patient_id"],
                "clinic_id": next(
                    (p["clinic_id"] for p in stack2.get("patients", []) if p["patient_id"] == row["patient_id"]),
                    "",
                ),
                "preferred_language": row.get("preferred_language", "") or "",
                "preferred_reminder_channel": row.get("preferred_reminder_channel", "") or "",
                "allow_telegram": _tf(bool(row.get("allow_telegram", False))),
                "allow_sms": _tf(bool(row.get("allow_sms", False))),
                "contact_time_window": (
                    f"{row['contact_time_window'].get('from', '')}-{row['contact_time_window'].get('to', '')}"
                    if isinstance(row.get("contact_time_window"), dict)
                    else ""
                ),
                "timezone": clinic_timezone.get(
                    next((p["clinic_id"] for p in stack2.get("patients", []) if p["patient_id"] == row["patient_id"]), ""),
                    "",
                ),
            }
            for row in stack2.get("patient_preferences", [])
        ],
    }

    for tab, header in COLUMNS.items():
        _write_csv(OUT_DIR / f"{tab}.csv", header, [])
        _write_csv(OUT_DIR / f"demo_{tab}.csv", header, demo[tab])


if __name__ == "__main__":
    main()
