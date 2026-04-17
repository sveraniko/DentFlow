from __future__ import annotations

from app.application.search.models import (
    DoctorSearchResult,
    PatientSearchResult,
    SearchQuery,
    SearchResultOrigin,
    ServiceSearchResult,
)
from app.infrastructure.search.meili_client import MeiliClient, MeiliIndexDefinition


class MeiliSearchBackend:
    def __init__(
        self,
        *,
        client: MeiliClient,
        patient_index: str,
        doctor_index: str,
        service_index: str,
    ) -> None:
        self._client = client
        self._patient_index = patient_index
        self._doctor_index = doctor_index
        self._service_index = service_index

    async def search_patients(self, query: SearchQuery) -> list[PatientSearchResult]:
        docs = await self._client.search(
            index_name=self._patient_index,
            query=query.query,
            payload={
                "limit": query.limit,
                "filter": [f"clinic_id = '{query.clinic_id}'"],
            },
        )
        return [
            PatientSearchResult(
                patient_id=row["patient_id"],
                clinic_id=row["clinic_id"],
                display_name=row.get("display_name") or "",
                patient_number=row.get("patient_number"),
                primary_phone_normalized=row.get("primary_phone_normalized"),
                active_flags_summary=row.get("active_flags_summary"),
                status=row.get("status"),
                origin=SearchResultOrigin.MEILI,
            )
            for row in docs
        ]

    async def search_doctors(self, query: SearchQuery) -> list[DoctorSearchResult]:
        docs = await self._client.search(
            index_name=self._doctor_index,
            query=query.query,
            payload={"limit": query.limit, "filter": [f"clinic_id = '{query.clinic_id}'"]},
        )
        return [
            DoctorSearchResult(
                doctor_id=row["doctor_id"],
                clinic_id=row["clinic_id"],
                branch_id=row.get("branch_id"),
                display_name=row.get("display_name") or "",
                specialty_code=row.get("specialty_code"),
                specialty_label=row.get("specialty_label"),
                public_booking_enabled=bool(row.get("public_booking_enabled", False)),
                status=row.get("status"),
                origin=SearchResultOrigin.MEILI,
            )
            for row in docs
        ]

    async def search_services(self, query: SearchQuery) -> list[ServiceSearchResult]:
        docs = await self._client.search(
            index_name=self._service_index,
            query=query.query,
            payload={"limit": query.limit, "filter": [f"clinic_id = '{query.clinic_id}'"]},
        )
        return [
            ServiceSearchResult(
                service_id=row["service_id"],
                clinic_id=row["clinic_id"],
                code=row.get("code"),
                title_key=row.get("title_key"),
                localized_search_text_ru=row.get("localized_search_text_ru"),
                localized_search_text_en=row.get("localized_search_text_en"),
                specialty_required=bool(row.get("specialty_required", False)),
                status=row.get("status"),
                origin=SearchResultOrigin.MEILI,
            )
            for row in docs
        ]


PATIENT_INDEX_SETTINGS = MeiliIndexDefinition(
    name="patients",
    settings={
        "searchableAttributes": [
            "display_name",
            "name_normalized",
            "name_tokens_normalized",
            "translit_tokens",
            "patient_number",
            "external_id_normalized",
            "primary_phone_normalized",
        ],
        "filterableAttributes": ["clinic_id", "status"],
        "displayedAttributes": [
            "patient_id",
            "clinic_id",
            "display_name",
            "patient_number",
            "name_normalized",
            "primary_phone_normalized",
            "external_id_normalized",
            "preferred_language",
            "primary_photo_ref",
            "active_flags_summary",
            "status",
            "updated_at",
        ],
    },
)

DOCTOR_INDEX_SETTINGS = MeiliIndexDefinition(
    name="doctors",
    settings={
        "searchableAttributes": [
            "display_name",
            "name_normalized",
            "name_tokens_normalized",
            "translit_tokens",
            "specialty_label",
            "specialty_code",
        ],
        "filterableAttributes": ["clinic_id", "branch_id", "public_booking_enabled", "status"],
        "displayedAttributes": [
            "doctor_id",
            "clinic_id",
            "branch_id",
            "display_name",
            "name_normalized",
            "specialty_code",
            "specialty_label",
            "public_booking_enabled",
            "status",
            "updated_at",
        ],
    },
)

SERVICE_INDEX_SETTINGS = MeiliIndexDefinition(
    name="services",
    settings={
        "searchableAttributes": ["code", "title_key", "localized_search_text_ru", "localized_search_text_en"],
        "filterableAttributes": ["clinic_id", "specialty_required", "status"],
        "displayedAttributes": [
            "service_id",
            "clinic_id",
            "code",
            "title_key",
            "localized_search_text_ru",
            "localized_search_text_en",
            "specialty_required",
            "status",
            "updated_at",
        ],
    },
)


async def configure_meili_indexes(*, client: MeiliClient, prefix: str) -> None:
    for definition in [PATIENT_INDEX_SETTINGS, DOCTOR_INDEX_SETTINGS, SERVICE_INDEX_SETTINGS]:
        await client.update_settings(index_name=f"{prefix}_{definition.name}", settings=definition.settings)
