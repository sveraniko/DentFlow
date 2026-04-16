from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import asyncio
import json

from app.bootstrap.logging import configure_logging
from app.config.settings import get_settings
from app.infrastructure.db.patient_repository import seed_stack2_patients


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings.logging)
    payload = json.loads(Path("seeds/stack2_patients.json").read_text(encoding="utf-8"))
    counts = await seed_stack2_patients(settings.db, payload)
    print("Stack 2 patient seed loaded into DB")
    print(" ".join(f"{k}={v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    asyncio.run(_run())
