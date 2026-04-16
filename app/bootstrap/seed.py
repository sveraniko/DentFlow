from __future__ import annotations

from pathlib import Path

from app.infrastructure.db.repositories import seed_stack_data


async def load_seed_to_db(db_config, *, seed_path: Path) -> dict[str, int]:
    return await seed_stack_data(db_config, seed_path)
