from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import argparse
import asyncio

from app.config.settings import get_settings
from app.projections.search import SearchProjectionRebuilder


async def _run(scope: str) -> None:
    settings = get_settings()
    service = SearchProjectionRebuilder(db_config=settings.db, locales_path=Path("locales"))
    if scope == "all":
        counts = await service.rebuild_all()
    elif scope == "patients":
        counts = {"patients": await service.rebuild_patients()}
    elif scope == "doctors":
        counts = {"doctors": await service.rebuild_doctors()}
    else:
        counts = {"services": await service.rebuild_services()}
    print(counts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild canonical search projections from canonical truth")
    parser.add_argument("scope", choices=["all", "patients", "doctors", "services"], nargs="?", default="all")
    args = parser.parse_args()
    asyncio.run(_run(args.scope))


if __name__ == "__main__":
    main()
