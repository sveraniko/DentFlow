from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import asyncio

from app.application.search.models import (
    DoctorProjectionRow,
    DoctorSearchResult,
    PatientProjectionRow,
    PatientSearchResult,
    SearchQuery,
    SearchResultOrigin,
    ServiceProjectionRow,
    ServiceSearchResult,
)
from app.application.search.reindex import MeiliReindexService
from app.application.search.service import HybridSearchService
from app.infrastructure.search.meili_documents import (
    doctor_projection_to_document,
    patient_projection_to_document,
    service_projection_to_document,
)
from app.interfaces.bots.search_handlers import run_doctor_search, run_patient_search, run_service_search


def test_patient_projection_mapping_privacy_safe() -> None:
    row = PatientProjectionRow(
        patient_id="p1",
        clinic_id="c1",
        display_name="John Doe",
        patient_number="PT-9",
        name_tokens_normalized="john doe",
        translit_tokens="jon dou",
        primary_phone_normalized="79991234567",
        preferred_language="en",
        primary_photo_ref="photo-1",
        active_flags_summary="vip",
        status="active",
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    doc = patient_projection_to_document(row)
    assert doc["patient_id"] == "p1"
    assert "clinical_notes" not in doc
    assert "diagnosis" not in doc


def test_doctor_and_service_projection_mapping() -> None:
    d = doctor_projection_to_document(
        DoctorProjectionRow(
            doctor_id="d1",
            clinic_id="c1",
            branch_id="b1",
            display_name="Dr A",
            name_tokens_normalized="dr a",
            translit_tokens="dr a",
            specialty_code="ortho",
            specialty_label="Orthodontics",
            public_booking_enabled=True,
            status="active",
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    s = service_projection_to_document(
        ServiceProjectionRow(
            service_id="s1",
            clinic_id="c1",
            code="SVC-1",
            title_key="svc.cleaning",
            localized_search_text_ru="чистка",
            localized_search_text_en="cleaning",
            specialty_required=False,
            status="active",
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    assert d["doctor_id"] == "d1"
    assert s["localized_search_text_ru"] == "чистка"


@dataclass
class _StrictStub:
    rows: list[PatientSearchResult]

    async def search_patients_strict(self, query: SearchQuery) -> list[PatientSearchResult]:
        return self.rows


@dataclass
class _SearchStub:
    patient_rows: list[PatientSearchResult]
    doctor_rows: list[DoctorSearchResult]
    service_rows: list[ServiceSearchResult]
    should_fail: bool = False

    async def search_patients(self, query: SearchQuery) -> list[PatientSearchResult]:
        if self.should_fail:
            raise RuntimeError("meili down")
        return self.patient_rows

    async def search_doctors(self, query: SearchQuery) -> list[DoctorSearchResult]:
        if self.should_fail:
            raise RuntimeError("meili down")
        return self.doctor_rows

    async def search_services(self, query: SearchQuery) -> list[ServiceSearchResult]:
        if self.should_fail:
            raise RuntimeError("meili down")
        return self.service_rows


def test_hybrid_patient_search_strict_first_and_dedup() -> None:
    strict = [
        PatientSearchResult("p1", "c1", "John", "N1", "100", "active", SearchResultOrigin.POSTGRES_STRICT),
        PatientSearchResult("p2", "c1", "Jane", "N2", "200", "active", SearchResultOrigin.POSTGRES_STRICT),
    ]
    meili = [
        PatientSearchResult("p2", "c1", "Jane fuzzy", "N2", "200", "active", SearchResultOrigin.MEILI),
        PatientSearchResult("p3", "c1", "Janet", "N3", "300", "active", SearchResultOrigin.MEILI),
    ]
    service = HybridSearchService(
        strict_backend=_StrictStub(strict),
        meili_backend=_SearchStub(meili, [], []),
        postgres_backend=_SearchStub([], [], []),
    )
    result = asyncio.run(service.search_patients(SearchQuery(clinic_id="c1", query="jan")))
    assert [r.patient_id for r in result.exact_matches] == ["p1", "p2"]
    assert [r.patient_id for r in result.suggestions] == ["p3"]


def test_patient_and_doctor_service_fallback_when_meili_down() -> None:
    postgres = _SearchStub(
        patient_rows=[],
        doctor_rows=[DoctorSearchResult("d1", "c1", None, "Dr A", None, None, True, "active", SearchResultOrigin.POSTGRES_FALLBACK)],
        service_rows=[ServiceSearchResult("s1", "c1", "x", "k", "чистка", "cleaning", False, "active", SearchResultOrigin.POSTGRES_FALLBACK)],
    )
    svc = HybridSearchService(
        strict_backend=_StrictStub([]),
        meili_backend=_SearchStub([], [], [], should_fail=True),
        postgres_backend=postgres,
    )
    patient = asyncio.run(svc.search_patients(SearchQuery(clinic_id="c1", query="q")))
    doctors = asyncio.run(svc.search_doctors(SearchQuery(clinic_id="c1", query="q")))
    services = asyncio.run(svc.search_services(SearchQuery(clinic_id="c1", query="q", locale="ru")))
    assert patient.exact_matches == [] and patient.suggestions == []
    assert doctors[0].origin == SearchResultOrigin.POSTGRES_FALLBACK
    assert services[0].localized_search_text_ru == "чистка"


class _ReaderStub:
    async def load_patient_projection_rows(self):
        return [
            PatientProjectionRow("p1", "c1", "John", None, None, None, None, None, None, None, "active", datetime(2026, 1, 1, tzinfo=timezone.utc))
        ]

    async def load_doctor_projection_rows(self):
        return [
            DoctorProjectionRow("d1", "c1", None, "Dr A", None, None, None, None, True, "active", datetime(2026, 1, 1, tzinfo=timezone.utc))
        ]

    async def load_service_projection_rows(self):
        return [
            ServiceProjectionRow("s1", "c1", "S1", "svc", "чистка", "cleaning", False, "active", datetime(2026, 1, 1, tzinfo=timezone.utc))
        ]


class _MeiliClientStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def replace_documents(self, *, index_name: str, documents: list[dict]) -> None:
        self.calls.append((index_name, len(documents)))


def test_full_reindex_uses_projection_rows() -> None:
    client = _MeiliClientStub()
    svc = MeiliReindexService(reader=_ReaderStub(), meili_client=client, index_prefix="dentflow", batch_size=2)
    counts = asyncio.run(svc.reindex_all())
    assert counts == {"patients": 1, "doctors": 1, "services": 1}
    assert ("dentflow_patients", 1) in client.calls
    assert ("dentflow_doctors", 1) in client.calls
    assert ("dentflow_services", 1) in client.calls


def test_search_handlers_surface_hybrid_paths() -> None:
    svc = HybridSearchService(
        strict_backend=_StrictStub([
            PatientSearchResult("p1", "c1", "John", None, None, "active", SearchResultOrigin.POSTGRES_STRICT)
        ]),
        meili_backend=_SearchStub(
            [PatientSearchResult("p2", "c1", "Jon", None, None, "active", SearchResultOrigin.MEILI)],
            [DoctorSearchResult("d1", "c1", None, "Dr A", None, None, True, "active", SearchResultOrigin.MEILI)],
            [ServiceSearchResult("s1", "c1", "S", "svc", "чистка", "cleaning", False, "active", SearchResultOrigin.MEILI)],
        ),
        postgres_backend=_SearchStub([], [], []),
    )
    patient_text = asyncio.run(run_patient_search(service=svc, clinic_id="c1", query="john"))
    doctor_text = asyncio.run(run_doctor_search(service=svc, clinic_id="c1", query="a"))
    service_text = asyncio.run(run_service_search(service=svc, clinic_id="c1", query="clean", locale="en"))
    assert "Exact:" in patient_text and "Suggestions:" in patient_text
    assert "(meili)" in doctor_text
    assert "cleaning" in service_text
