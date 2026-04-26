from __future__ import annotations

import ast
from pathlib import Path

SMOKE_SCRIPTS = [
    Path("scripts/smoke_import_app.py"),
    Path("scripts/smoke_settings.py"),
    Path("scripts/smoke_dispatcher.py"),
    Path("scripts/smoke_worker_modes.py"),
]


def test_smoke_scripts_exist_and_compile() -> None:
    for script in SMOKE_SCRIPTS:
        assert script.exists(), f"missing {script}"
        source = script.read_text(encoding="utf-8")
        ast.parse(source, filename=str(script))


def test_smoke_scripts_do_not_print_raw_token_values() -> None:
    forbidden_patterns = [
        "print(settings.telegram.patient_bot_token)",
        "print(settings.telegram.clinic_admin_bot_token)",
        "print(settings.telegram.doctor_bot_token)",
        "print(settings.telegram.owner_bot_token)",
        "f\"{settings.telegram.patient_bot_token}\"",
        "f\"{settings.telegram.clinic_admin_bot_token}\"",
        "f\"{settings.telegram.doctor_bot_token}\"",
        "f\"{settings.telegram.owner_bot_token}\"",
    ]
    for script in SMOKE_SCRIPTS:
        text = script.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            assert pattern not in text, f"unsafe token print pattern in {script}: {pattern}"


def test_makefile_contains_smoke_targets() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")
    for target in [
        "smoke-import:",
        "smoke-settings:",
        "smoke-dispatcher:",
        "smoke-worker-modes:",
        "smoke-launch:",
    ]:
        assert target in makefile


def test_runbook_exists_with_key_sections() -> None:
    runbook = Path("docs/PILOT_LAUNCH_RUNBOOK.md")
    assert runbook.exists()
    text = runbook.read_text(encoding="utf-8")
    expected_phrases = [
        "Required environment checklist",
        "DB/bootstrap steps",
        "Redis requirement",
        "Bot startup",
        "Worker startup",
        "First smoke commands per role",
        "Integration toggles",
        "Stop/rollback basics",
        "Known limitations",
        "no webhook deployment",
    ]
    for phrase in expected_phrases:
        assert phrase.lower() in text.lower()


def test_readme_points_to_runbook_and_smoke_targets() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "docs/PILOT_LAUNCH_RUNBOOK.md" in readme
    assert "make smoke-launch" in readme


def test_no_migrations_introduced() -> None:
    assert not Path("migrations").exists()
    assert not Path("alembic.ini").exists()
