from __future__ import annotations

import argparse
import asyncio

from app.application.search.reindex import MeiliReindexService
from app.config.settings import get_settings
from app.infrastructure.search.meili_client import HttpMeiliClient
from app.infrastructure.search.meili_backend import configure_meili_indexes
from app.infrastructure.search.projection_reader import ProjectionSearchReader


async def _run(target: str) -> None:
    settings = get_settings()
    if not settings.search.enabled:
        raise RuntimeError("SEARCH_ENABLED is false; refusing to run meili reindex")

    client = HttpMeiliClient(
        endpoint=settings.search.meili_endpoint,
        api_key=settings.search.meili_api_key,
        timeout_sec=settings.search.meili_timeout_sec,
    )
    await configure_meili_indexes(client=client, prefix=settings.search.meili_index_prefix)
    service = MeiliReindexService(
        reader=ProjectionSearchReader(settings.db),
        meili_client=client,
        index_prefix=settings.search.meili_index_prefix,
        batch_size=settings.search.meili_batch_size,
    )

    if target == "all":
        counts = await service.reindex_all()
    elif target == "patients":
        counts = {"patients": await service.reindex_patients()}
    elif target == "doctors":
        counts = {"doctors": await service.reindex_doctors()}
    else:
        counts = {"services": await service.reindex_services()}
    print(counts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reindex canonical search projections into Meilisearch")
    parser.add_argument("target", choices=["all", "patients", "doctors", "services"], nargs="?", default="all")
    args = parser.parse_args()
    asyncio.run(_run(args.target))


if __name__ == "__main__":
    main()
