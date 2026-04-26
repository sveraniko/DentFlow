"""Bounded smoke check: import core app modules without starting runtime loops."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import importlib

MODULES = (
    "app.main",
    "app.worker",
    "app.bootstrap.runtime",
    "app.config.settings",
)


def main() -> int:
    failures: list[str] = []
    for module_name in MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # bounded smoke script, explicit failure report
            failures.append(f"{module_name}: {exc.__class__.__name__}: {exc}")

    if failures:
        print("SMOKE_IMPORT_APP FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    print("SMOKE_IMPORT_APP OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
