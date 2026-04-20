from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse
import asyncio
import json

from app.config.settings import get_settings
from app.infrastructure.outbox.repository import OutboxRepository, ProjectorCheckpointRepository
from app.projections.runtime import ProjectorOperationsService, build_default_projector_registry


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    registry = build_default_projector_registry()
    service = ProjectorOperationsService(
        outbox_repository=OutboxRepository(settings.db),
        checkpoint_repository=ProjectorCheckpointRepository(settings.db),
        projector_names=registry.names(),
    )

    if args.command == "status":
        print(json.dumps(await service.lag_status(), ensure_ascii=False, indent=2))
        return
    if args.command == "failures":
        print(
            json.dumps(
                await service.recent_failures(limit=args.limit, projector_name=args.projector_name),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.command == "retry":
        print(
            json.dumps(
                await service.retry_failed_event(projector_name=args.projector_name, outbox_event_id=args.outbox_event_id),
                ensure_ascii=False,
                indent=2,
            )
        )
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Projector runtime operations")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show projector lag/freshness status")
    failures = sub.add_parser("failures", help="Show recent projector failures")
    failures.add_argument("--limit", type=int, default=20)
    failures.add_argument("--projector-name", type=str, default=None)

    retry = sub.add_parser("retry", help="Retry projector from failed outbox event")
    retry.add_argument("projector_name")
    retry.add_argument("outbox_event_id", type=int)

    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
