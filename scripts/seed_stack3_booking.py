from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import asyncio

from app.config.settings import get_settings
from app.infrastructure.db.booking_repository import seed_stack3_booking


async def _run() -> None:
    settings = get_settings()
    counts = await seed_stack3_booking(settings.db, Path("seeds/stack3_booking.json"))
    print("Stack 3A booking seed loaded into DB")
    for key, value in counts.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(_run())
