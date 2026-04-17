from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse
import asyncio

from app.config.settings import get_settings
from app.infrastructure.outbox.repository import ProjectorCheckpointRepository


async def _run(projector_name: str, reset: bool) -> None:
    settings = get_settings()
    repo = ProjectorCheckpointRepository(settings.db)
    if reset:
        await repo.reset_checkpoint(projector_name=projector_name)
        print({"projector": projector_name, "checkpoint": 0})
        return
    checkpoint = await repo.get_checkpoint(projector_name=projector_name)
    print({"projector": projector_name, "checkpoint": checkpoint})


def main() -> None:
    parser = argparse.ArgumentParser(description="Read/reset projector checkpoint")
    parser.add_argument("projector_name")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    asyncio.run(_run(args.projector_name, args.reset))


if __name__ == "__main__":
    main()
