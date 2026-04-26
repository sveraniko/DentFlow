"""Bounded smoke check: build RuntimeRegistry and Dispatcher without polling."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap.runtime import RuntimeRegistry
from app.config.settings import get_settings


def main() -> int:
    try:
        settings = get_settings()
        runtime = RuntimeRegistry(settings)
        runtime.build_dispatcher()
    except Exception as exc:  # bounded launch smoke, surface actionable error
        print("SMOKE_DISPATCHER FAIL")
        print(f"- {exc.__class__.__name__}: {exc}")
        print("- guidance: verify DB_DSN, db bootstrap, seed/reference baseline, and REDIS_URL availability")
        return 1

    print("SMOKE_DISPATCHER OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
