from __future__ import annotations

from app.infrastructure.search.meili_client import MeiliClient
from app.infrastructure.search.meili_documents import (
    doctor_projection_to_document,
    patient_projection_to_document,
    service_projection_to_document,
)
from app.infrastructure.search.projection_reader import ProjectionSearchReader


class MeiliReindexService:
    def __init__(
        self,
        *,
        reader: ProjectionSearchReader,
        meili_client: MeiliClient,
        index_prefix: str,
        batch_size: int,
    ) -> None:
        self._reader = reader
        self._client = meili_client
        self._index_prefix = index_prefix
        self._batch_size = batch_size

    async def reindex_patients(self) -> int:
        rows = await self._reader.load_patient_projection_rows()
        docs = [patient_projection_to_document(row) for row in rows]
        await self._replace_in_batches(index_name=f"{self._index_prefix}_patients", docs=docs)
        return len(docs)

    async def reindex_doctors(self) -> int:
        rows = await self._reader.load_doctor_projection_rows()
        docs = [doctor_projection_to_document(row) for row in rows]
        await self._replace_in_batches(index_name=f"{self._index_prefix}_doctors", docs=docs)
        return len(docs)

    async def reindex_services(self) -> int:
        rows = await self._reader.load_service_projection_rows()
        docs = [service_projection_to_document(row) for row in rows]
        await self._replace_in_batches(index_name=f"{self._index_prefix}_services", docs=docs)
        return len(docs)

    async def reindex_all(self) -> dict[str, int]:
        return {
            "patients": await self.reindex_patients(),
            "doctors": await self.reindex_doctors(),
            "services": await self.reindex_services(),
        }

    async def _replace_in_batches(self, *, index_name: str, docs: list[dict]) -> None:
        await self._client.clear_documents(index_name=index_name)
        if not docs:
            return
        for start in range(0, len(docs), self._batch_size):
            await self._client.add_documents(index_name=index_name, documents=docs[start : start + self._batch_size])
