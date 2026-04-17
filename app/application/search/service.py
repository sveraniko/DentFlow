from __future__ import annotations

import logging

from app.application.search.backends import SearchBackend, StrictPatientSearchBackend
from app.application.search.models import (
    DoctorSearchResult,
    PatientSearchResponse,
    SearchQuery,
    ServiceSearchResult,
)

logger = logging.getLogger("dentflow.search.service")


class HybridSearchService:
    def __init__(
        self,
        *,
        strict_backend: StrictPatientSearchBackend,
        meili_backend: SearchBackend | None,
        postgres_backend: SearchBackend,
    ) -> None:
        self._strict_backend = strict_backend
        self._meili_backend = meili_backend
        self._postgres_backend = postgres_backend

    async def search_patients(self, query: SearchQuery) -> PatientSearchResponse:
        strict_results = await self._strict_backend.search_patients_strict(query)
        strict_by_id = {row.patient_id: row for row in strict_results}
        suggestions = []
        if self._meili_backend:
            try:
                fuzzy_results = await self._meili_backend.search_patients(query)
                for candidate in fuzzy_results:
                    if candidate.patient_id not in strict_by_id:
                        suggestions.append(candidate)
            except Exception:
                logger.exception("meili patient search failed, continuing with strict postgres search")
        return PatientSearchResponse(exact_matches=strict_results, suggestions=suggestions)

    async def search_doctors(self, query: SearchQuery) -> list[DoctorSearchResult]:
        if self._meili_backend is None:
            return await self._postgres_backend.search_doctors(query)
        try:
            return await self._meili_backend.search_doctors(query)
        except Exception:
            logger.exception("meili doctor search failed, falling back to postgres")
            return await self._postgres_backend.search_doctors(query)

    async def search_services(self, query: SearchQuery) -> list[ServiceSearchResult]:
        if self._meili_backend is None:
            return await self._postgres_backend.search_services(query)
        try:
            return await self._meili_backend.search_services(query)
        except Exception:
            logger.exception("meili service search failed, falling back to postgres")
            return await self._postgres_backend.search_services(query)
