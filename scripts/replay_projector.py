from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse
import asyncio

from app.config.settings import get_settings
from app.infrastructure.outbox.repository import ProjectorCheckpointRepository
from app.projections.runtime import build_default_projector_registry


async def _run(projector_name: str, reset: bool, to_event_id: int | None) -> None:
    settings = get_settings()
    repo = ProjectorCheckpointRepository(settings.db)
    valid_projectors = set(build_default_projector_registry().names())
    if projector_name not in valid_projectors:
        raise SystemExit(f"unknown projector '{projector_name}', known={sorted(valid_projectors)}")
    if to_event_id is not None:
        await repo.save_checkpoint(projector_name=projector_name, last_outbox_event_id=max(0, to_event_id))
        print({"projector": projector_name, "checkpoint": max(0, to_event_id)})
        return
    if reset:
        await repo.reset_checkpoint(projector_name=projector_name)
        print({"projector": projector_name, "checkpoint": 0})
        return
    checkpoint = await repo.get_checkpoint(projector_name=projector_name)
    print({"projector": projector_name, "checkpoint": checkpoint})


def main() -> None:
    parser = argparse.ArgumentParser(description="Read/reset/set projector checkpoint")
    parser.add_argument("projector_name")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--to-event-id", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(_run(args.projector_name, args.reset, args.to_event_id))


if __name__ == "__main__":
    main()
