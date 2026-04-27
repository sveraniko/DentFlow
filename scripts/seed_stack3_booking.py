from pathlib import Path
import sys
from datetime import date
import argparse

sys.path.append(str(Path(__file__).resolve().parents[1]))

import asyncio

from app.config.settings import get_settings
from app.infrastructure.db.booking_repository import seed_stack3_booking


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Stack 3 booking fixtures")
    parser.add_argument("--relative-dates", action="store_true", help="Shift stack3 date/time fields relative to today")
    parser.add_argument("--start-offset-days", type=int, default=1, help="Target day offset from today when using --relative-dates")
    parser.add_argument(
        "--source-anchor-date",
        type=date.fromisoformat,
        default=None,
        help="Explicit source anchor date in YYYY-MM-DD format when using --relative-dates",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    counts = await seed_stack3_booking(
        settings.db,
        Path("seeds/stack3_booking.json"),
        relative_dates=args.relative_dates,
        start_offset_days=args.start_offset_days,
        source_anchor_date=args.source_anchor_date,
    )
    print("Stack 3A booking seed loaded into DB")
    for key, value in counts.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(_run(_parse_args()))
