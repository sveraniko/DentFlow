from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class MeiliClient(Protocol):
    async def update_settings(self, *, index_name: str, settings: dict[str, Any]) -> None: ...

    async def clear_documents(self, *, index_name: str) -> None: ...

    async def add_documents(self, *, index_name: str, documents: list[dict[str, Any]]) -> None: ...

    async def search(self, *, index_name: str, query: str, payload: dict[str, Any]) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class MeiliIndexDefinition:
    name: str
    settings: dict[str, Any]


class HttpMeiliClient:
    def __init__(self, *, endpoint: str, api_key: str | None, timeout_sec: float) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._timeout_sec = timeout_sec

    async def update_settings(self, *, index_name: str, settings: dict[str, Any]) -> None:
        await self._request(
            method="PATCH",
            path=f"/indexes/{index_name}/settings",
            payload=settings,
        )

    async def clear_documents(self, *, index_name: str) -> None:
        await self._request(
            method="DELETE",
            path=f"/indexes/{index_name}/documents",
        )

    async def add_documents(self, *, index_name: str, documents: list[dict[str, Any]]) -> None:
        await self._request(
            method="POST",
            path=f"/indexes/{index_name}/documents",
            payload=documents,
        )

    async def search(self, *, index_name: str, query: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        body = {"q": query}
        body.update(payload)
        response = await self._request(method="POST", path=f"/indexes/{index_name}/search", payload=body)
        return list(response.get("hits", []))

    async def _request(self, *, method: str, path: str, payload: dict | list | None = None) -> dict[str, Any]:
        url = f"{self._endpoint}{path}"
        encoded = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        def _sync() -> dict[str, Any]:
            request = Request(url=url, data=encoded, method=method, headers=headers)
            try:
                with urlopen(request, timeout=self._timeout_sec) as response:
                    data = response.read().decode("utf-8")
                    if not data:
                        return {}
                    return json.loads(data)
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"meili http error {exc.code}: {detail}") from exc

        return await asyncio.to_thread(_sync)
