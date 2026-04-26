"""Bounded smoke check: validate worker mode parsing and worker runtime imports."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os

from app.worker import _projector_worker_config_from_env, _reminder_worker_config_from_env

VALID_WORKER_MODES = {"projector", "reminder", "all"}


def _validate_mode(value: str) -> bool:
    return value.strip().lower() in VALID_WORKER_MODES


def main() -> int:
    mode = os.getenv("WORKER_MODE", "projector")
    if not _validate_mode(mode):
        print("SMOKE_WORKER_MODES FAIL")
        print(f"- invalid WORKER_MODE='{mode}' expected one of: projector, reminder, all")
        return 1

    # Pure config parsing helpers only; no forever loops.
    projector_cfg = _projector_worker_config_from_env()
    reminder_cfg = _reminder_worker_config_from_env()

    print("SMOKE_WORKER_MODES OK")
    print(f"- selected_mode={mode.strip().lower()}")
    print(f"- projector_batch_limit={projector_cfg.batch_limit} poll_interval={projector_cfg.poll_interval_sec}")
    print(
        f"- reminder_delivery_batch_limit={reminder_cfg.delivery_batch_limit} "
        f"recovery_batch_limit={reminder_cfg.recovery_batch_limit} poll_interval={reminder_cfg.poll_interval_sec}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
