from __future__ import annotations

import csv
import json
from pathlib import Path

from app.application.care_catalog_sync.parser import _HEADERS, parse_catalog_workbook


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "docs/templates/google_sheets/care_catalog"
SEED_PATH = ROOT / "seeds/care_catalog_demo.json"

TABS = (
    "products",
    "product_i18n",
    "branch_availability",
    "recommendation_sets",
    "recommendation_set_items",
    "recommendation_links",
    "settings",
)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader)


def _load_demo_workbook() -> dict[str, list[dict[str, str]]]:
    return {tab: _read_csv_rows(TEMPLATE_DIR / f"demo_{tab}.csv") for tab in TABS}


def test_p0_06e1_template_files_exist() -> None:
    for tab in TABS:
        assert (TEMPLATE_DIR / f"{tab}.csv").exists(), f"missing blank template for {tab}"
        assert (TEMPLATE_DIR / f"demo_{tab}.csv").exists(), f"missing demo template for {tab}"
    assert (TEMPLATE_DIR / "README.md").exists()


def test_p0_06e1_headers_match_parser_and_seed_shape() -> None:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))

    for tab in TABS:
        assert tab in seed, f"missing tab in seed json: {tab}"
        header = _read_csv_header(TEMPLATE_DIR / f"{tab}.csv")
        assert header == list(_HEADERS[tab]), f"header mismatch for {tab}"

        if seed[tab]:
            seed_keys = list(seed[tab][0].keys())
            assert header == seed_keys, f"header mismatch with seed row keys for {tab}"


def test_p0_06e1_demo_csv_round_trip_parses_without_errors() -> None:
    workbook = _load_demo_workbook()
    parsed, result = parse_catalog_workbook(
        workbook=workbook,
        known_branch_ids={"branch_central"},
        source="csv_template",
    )

    assert parsed is not None
    assert not result.fatal_errors
    assert not result.validation_errors
    assert len(parsed.products) >= 6
    assert parsed.branch_availability
    assert parsed.recommendation_links


def test_p0_06e1_demo_csv_counts_match_seed_json() -> None:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    workbook = _load_demo_workbook()

    for tab in TABS:
        assert len(workbook[tab]) == len(seed[tab]), f"count mismatch for {tab}"


def test_p0_06e1_readme_has_required_sync_coverage() -> None:
    readme = (TEMPLATE_DIR / "README.md").read_text(encoding="utf-8")

    for phrase in (
        "products",
        "product_i18n",
        "branch_availability",
        "/admin_catalog_sync sheets",
        "scripts/sync_care_catalog.py",
        "clinic_main",
        "accessible for export",
        "Google Sheet",
    ):
        assert phrase in readme
