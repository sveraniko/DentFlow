from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import asyncio

from app.config.settings import get_settings
from app.projections.admin import AdminWorkdeskProjectionStore


async def _run() -> None:
    settings = get_settings()
    stats = await AdminWorkdeskProjectionStore(settings.db, app_default_timezone=settings.app.default_timezone).rebuild_all()
    print(stats)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
