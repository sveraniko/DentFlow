from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

DOCUMENT_GENERATION_STATUSES: frozenset[str] = frozenset({"pending", "generating", "generated", "failed"})


@dataclass(slots=True, frozen=True)
class DocumentTemplate:
    document_template_id: str
    clinic_id: str | None
    template_type: str
    template_version: int
    locale: str
    render_engine: str
    template_source_ref: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class GeneratedDocument:
    generated_document_id: str
    clinic_id: str
    patient_id: str
    chart_id: str | None
    encounter_id: str | None
    booking_id: str | None
    document_template_id: str
    document_type: str
    generation_status: str
    generated_file_asset_id: str | None
    editable_source_asset_id: str | None
    created_by_actor_id: str | None
    created_at: datetime
    updated_at: datetime
    generation_error_text: str | None
