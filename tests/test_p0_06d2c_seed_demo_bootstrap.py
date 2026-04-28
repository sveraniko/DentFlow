from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from scripts import seed_demo


def test_dry_run_defaults_and_planned_steps(capsys) -> None:
    exit_code = seed_demo.main(["--relative-dates", "--dry-run"])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "[1/5] stack1 reference... planned" in captured
    assert "[2/5] stack2 patients... planned" in captured
    assert "[3/5] stack3 booking... planned" in captured
    assert "[4/5] care catalog... planned" in captured
    assert "[5/5] recommendations + care orders... planned" in captured
    assert "relative_dates: True" in captured
    assert "stack1 path: seeds/stack1_seed.json" in captured
    assert "stack2 path: seeds/stack2_patients.json" in captured
    assert "stack3 path: seeds/stack3_booking.json" in captured
    assert "care catalog path: seeds/care_catalog_demo.json" in captured
    assert "recommendations/care orders path: seeds/demo_recommendations_care_orders.json" in captured


def test_dry_run_missing_file_fails(capsys) -> None:
    exit_code = seed_demo.main(["--dry-run", "--care-catalog-path", "seeds/missing_care_catalog_demo.json"])

    captured = capsys.readouterr().out
    assert exit_code != 0
    assert "Missing required care catalog file" in captured


def test_dry_run_validates_care_catalog(capsys) -> None:
    exit_code = seed_demo.main(["--dry-run", "--care-catalog-path", "seeds/care_catalog_demo.json"])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Dry-run validation complete." in captured


def test_dry_run_validates_recommendations_and_keeps_expected_warning(capsys) -> None:
    exit_code = seed_demo.main(
        [
            "--dry-run",
            "--recommendations-care-orders-path",
            "seeds/demo_recommendations_care_orders.json",
        ]
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "SKU-NOT-EXISTS" in captured


def test_dry_run_skip_care_and_recommendations_allows_missing_optional_files(capsys) -> None:
    exit_code = seed_demo.main(
        [
            "--dry-run",
            "--skip-care",
            "--skip-recommendations",
            "--care-catalog-path",
            "seeds/missing_care_catalog_demo.json",
            "--recommendations-care-orders-path",
            "seeds/missing_demo_recommendations_care_orders.json",
        ]
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "[4/5] care catalog... skipped" in captured
    assert "[5/5] recommendations + care orders... skipped" in captured


def test_dry_run_skip_care_without_skip_recommendations_fails(capsys) -> None:
    exit_code = seed_demo.main(["--dry-run", "--skip-care"])
    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "--skip-recommendations must be used when --skip-care is enabled in dry-run mode" in captured


def test_step_order_non_dry_run(monkeypatch) -> None:
    calls: list[str] = []

    async def _fake_stack1(_db, _path):
        calls.append("stack1")
        return {"clinics": 1}

    async def _fake_stack2(_db, _payload):
        calls.append("stack2")
        return {"patients": 1}

    async def _fake_stack3(_db, _path, **_kwargs):
        calls.append("stack3")
        return {"bookings": 1}

    async def _fake_rec(_db, _path, **_kwargs):
        calls.append("recommendations_care_orders")
        return {"recommendations": 1}

    class _FakeService:
        def __init__(self, _repo) -> None:
            pass

        async def import_json(self, *, clinic_id: str, path: Path):
            calls.append("care_catalog")
            return SimpleNamespace(ok=True, tabs_processed=["products"], warnings=[], validation_errors=[], fatal_errors=[])

    monkeypatch.setattr(seed_demo, "get_settings", lambda: SimpleNamespace(db=object()))
    monkeypatch.setattr(seed_demo, "seed_stack_data", _fake_stack1)
    monkeypatch.setattr(seed_demo, "seed_stack2_patients", _fake_stack2)
    monkeypatch.setattr(seed_demo, "seed_stack3_booking", _fake_stack3)
    monkeypatch.setattr(seed_demo, "seed_demo_recommendations_care_orders", _fake_rec)
    monkeypatch.setattr(seed_demo, "DbCareCommerceRepository", lambda _db: object())
    monkeypatch.setattr(seed_demo, "CareCatalogSyncService", _FakeService)

    exit_code = seed_demo.main([])

    assert exit_code == 0
    assert calls == ["stack1", "stack2", "stack3", "care_catalog", "recommendations_care_orders"]


def test_relative_date_propagation(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def _fake_stack1(_db, _path):
        return {"clinics": 1}

    async def _fake_stack2(_db, _payload):
        return {"patients": 1}

    async def _fake_stack3(_db, _path, **kwargs):
        captured["stack3"] = kwargs
        return {"bookings": 1}

    async def _fake_rec(_db, _path, **kwargs):
        captured["recommendations"] = kwargs
        return {"recommendations": 1}

    class _FakeService:
        def __init__(self, _repo) -> None:
            pass

        async def import_json(self, *, clinic_id: str, path: Path):
            return SimpleNamespace(ok=True, tabs_processed=["products"], warnings=[], validation_errors=[], fatal_errors=[])

    monkeypatch.setattr(seed_demo, "get_settings", lambda: SimpleNamespace(db=object()))
    monkeypatch.setattr(seed_demo, "seed_stack_data", _fake_stack1)
    monkeypatch.setattr(seed_demo, "seed_stack2_patients", _fake_stack2)
    monkeypatch.setattr(seed_demo, "seed_stack3_booking", _fake_stack3)
    monkeypatch.setattr(seed_demo, "seed_demo_recommendations_care_orders", _fake_rec)
    monkeypatch.setattr(seed_demo, "DbCareCommerceRepository", lambda _db: object())
    monkeypatch.setattr(seed_demo, "CareCatalogSyncService", _FakeService)

    exit_code = seed_demo.main(
        [
            "--relative-dates",
            "--start-offset-days",
            "3",
            "--source-anchor-date",
            "2026-04-20",
        ]
    )

    assert exit_code == 0
    expected = {
        "relative_dates": True,
        "start_offset_days": 3,
        "source_anchor_date": date(2026, 4, 20),
    }
    assert captured["stack3"] == expected
    assert captured["recommendations"] == expected


def test_makefile_has_seed_demo_target() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "seed-demo:" in makefile
    assert "python scripts/seed_demo.py --relative-dates" in makefile
