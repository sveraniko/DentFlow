from __future__ import annotations

from app.application.search.models import PatientSearchResult, SearchQuery
from app.application.search.service import HybridSearchService
from app.common.i18n import I18nService


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    if len(phone) <= 4:
        return phone
    return f"***{phone[-4:]}"


def _patient_line(row: PatientSearchResult) -> str:
    parts = [row.display_name]
    if row.patient_number:
        parts.append(f"#{row.patient_number}")
    masked_phone = _mask_phone(row.primary_phone_normalized)
    if masked_phone:
        parts.append(masked_phone)
    if row.active_flags_summary:
        parts.append(f"⚑ {row.active_flags_summary}")
    if row.status:
        parts.append(row.status)
    parts.append(f"({row.origin.value})")
    return " • ".join(parts)


async def run_patient_search(
    *,
    service: HybridSearchService,
    i18n: I18nService,
    locale: str,
    clinic_id: str,
    query: str,
    limit: int = 5,
) -> str:
    response = await service.search_patients(SearchQuery(clinic_id=clinic_id, query=query, limit=limit, locale=locale))
    lines = [i18n.t("search.patient.title", locale)]
    if response.exact_matches:
        lines.append(i18n.t("search.patient.exact", locale))
        for row in response.exact_matches:
            lines.append(f"• {_patient_line(row)}")
    if response.suggestions:
        lines.append(i18n.t("search.patient.suggestions", locale))
        for row in response.suggestions:
            lines.append(f"• {_patient_line(row)}")
    if len(lines) == 1:
        lines.append(i18n.t("search.no_matches", locale))
    return "\n".join(lines)


async def run_doctor_search(
    *, service: HybridSearchService, i18n: I18nService, locale: str, clinic_id: str, query: str, limit: int = 5
) -> str:
    rows = await service.search_doctors(SearchQuery(clinic_id=clinic_id, query=query, limit=limit, locale=locale))
    if not rows:
        return f"{i18n.t('search.doctor.title', locale)}\n{i18n.t('search.no_matches', locale)}"
    lines = [i18n.t("search.doctor.title", locale)]
    for row in rows:
        lines.append(f"• {row.display_name} [{row.doctor_id}] ({row.origin.value})")
    return "\n".join(lines)


async def run_service_search(
    *, service: HybridSearchService, i18n: I18nService, locale: str, clinic_id: str, query: str, limit: int = 5
) -> str:
    rows = await service.search_services(SearchQuery(clinic_id=clinic_id, query=query, limit=limit, locale=locale))
    if not rows:
        return f"{i18n.t('search.service.title', locale)}\n{i18n.t('search.no_matches', locale)}"
    lines = [i18n.t("search.service.title", locale)]
    for row in rows:
        label = row.localized_search_text_ru if locale == "ru" else row.localized_search_text_en
        lines.append(f"• {label or row.title_key or row.code or row.service_id} [{row.service_id}] ({row.origin.value})")
    return "\n".join(lines)
