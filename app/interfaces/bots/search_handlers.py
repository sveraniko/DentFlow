from __future__ import annotations

from app.application.search.models import SearchQuery
from app.application.search.service import HybridSearchService


async def run_patient_search(*, service: HybridSearchService, clinic_id: str, query: str, limit: int = 5) -> str:
    response = await service.search_patients(SearchQuery(clinic_id=clinic_id, query=query, limit=limit))
    lines = ["Patient search"]
    if response.exact_matches:
        lines.append("Exact:")
        for row in response.exact_matches:
            lines.append(f"• {row.display_name} [{row.patient_id}] ({row.origin.value})")
    if response.suggestions:
        lines.append("Suggestions:")
        for row in response.suggestions:
            lines.append(f"• {row.display_name} [{row.patient_id}] ({row.origin.value})")
    if len(lines) == 1:
        lines.append("No matches")
    return "\n".join(lines)


async def run_doctor_search(*, service: HybridSearchService, clinic_id: str, query: str, limit: int = 5) -> str:
    rows = await service.search_doctors(SearchQuery(clinic_id=clinic_id, query=query, limit=limit))
    if not rows:
        return "Doctor search\nNo matches"
    lines = ["Doctor search"]
    for row in rows:
        lines.append(f"• {row.display_name} [{row.doctor_id}] ({row.origin.value})")
    return "\n".join(lines)


async def run_service_search(*, service: HybridSearchService, clinic_id: str, query: str, locale: str | None, limit: int = 5) -> str:
    rows = await service.search_services(SearchQuery(clinic_id=clinic_id, query=query, limit=limit, locale=locale))
    if not rows:
        return "Service search\nNo matches"
    lines = ["Service search"]
    for row in rows:
        label = row.localized_search_text_ru if locale == "ru" else row.localized_search_text_en
        lines.append(f"• {label or row.title_key or row.code or row.service_id} [{row.service_id}] ({row.origin.value})")
    return "\n".join(lines)
