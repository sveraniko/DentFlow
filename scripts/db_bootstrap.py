from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import asyncio
import logging

from app.bootstrap.logging import configure_logging
from app.config.settings import get_settings
from app.infrastructure.db.bootstrap import bootstrap_database


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings.logging)
    logging.getLogger("dentflow.db.bootstrap").info("starting database bootstrap")
    await bootstrap_database(settings.db)
    logging.getLogger("dentflow.db.bootstrap").info("database bootstrap completed")


if __name__ == "__main__":
    asyncio.run(_run())
