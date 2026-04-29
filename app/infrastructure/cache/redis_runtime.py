from __future__ import annotations

from app.config.settings import Settings
from app.interfaces.cards.runtime_state import InMemoryRedis, RedisLike


class AsyncRedisRuntimeAdapter:
    def __init__(self, *, url: str) -> None:
        import redis.asyncio as redis

        self._client = redis.from_url(url, encoding="utf-8", decode_responses=True)

    async def set(self, key: str, value: str, ex: int | None = None) -> object:
        return await self._client.set(key, value, ex=ex)

    async def get(self, key: str) -> str | bytes | None:
        return await self._client.get(key)

    async def delete(self, key: str) -> int:
        return int(await self._client.delete(key))


def build_card_runtime_redis(settings: Settings) -> RedisLike:
    if settings.redis.url:
        return AsyncRedisRuntimeAdapter(url=settings.redis.url)
    return InMemoryRedis()
