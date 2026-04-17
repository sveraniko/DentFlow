from __future__ import annotations

from typing import Protocol

from app.application.search.models import (
    DoctorSearchResult,
    PatientSearchResult,
    SearchQuery,
    ServiceSearchResult,
)


class SearchBackend(Protocol):
    async def search_patients(self, query: SearchQuery) -> list[PatientSearchResult]: ...

    async def search_doctors(self, query: SearchQuery) -> list[DoctorSearchResult]: ...

    async def search_services(self, query: SearchQuery) -> list[ServiceSearchResult]: ...


class StrictPatientSearchBackend(Protocol):
    async def search_patients_strict(self, query: SearchQuery) -> list[PatientSearchResult]: ...
