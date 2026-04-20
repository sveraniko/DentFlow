from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.application.export.models import Structured043ExportPayload


@dataclass(slots=True, frozen=True)
class Rendered043Document:
    content: bytes
    content_type: str
    extension: str


@dataclass(slots=True, frozen=True)
class StoredArtifact:
    storage_provider: str
    storage_ref: str
    byte_size: int
    checksum_sha256: str


class Export043Renderer(Protocol):
    def render(self, *, payload: Structured043ExportPayload, locale: str, template_source_ref: str) -> Rendered043Document: ...


class ArtifactStorage(Protocol):
    def store(self, *, generated_document_id: str, artifact: Rendered043Document) -> StoredArtifact: ...


@dataclass(slots=True)
class PlainText043Renderer:
    locales_dir: Path = Path("locales")

    def render(self, *, payload: Structured043ExportPayload, locale: str, template_source_ref: str) -> Rendered043Document:
        del template_source_ref
        service_label = self._localize_or_humanize(payload.booking.service_label, locale=locale, fallback="Service")
        doctor_label = self._humanize_text(payload.booking.doctor_label, fallback="Doctor")
        branch_label = self._humanize_text(payload.booking.branch_label, fallback="Branch")
        contact_label = self._render_contact(payload.patient.primary_contact_hint)

        lines = [
            "DentFlow 043 Export",
            "",
            "Patient",
            f"- Name: {payload.patient.full_name_legal or payload.patient.display_name}",
            f"- Patient #: {payload.patient.patient_number or '—'}",
            f"- Contact: {contact_label}",
            f"- Language: {payload.patient.preferred_language or '—'}",
            "",
            "Booking",
            f"- Booking ID: {payload.booking.booking_id or '—'}",
            f"- Status: {payload.booking.booking_status or '—'}",
            f"- Service: {service_label}",
            f"- Doctor: {doctor_label}",
            f"- Branch: {branch_label}",
            f"- Start: {payload.booking.scheduled_start_local_label or '—'}",
            f"- End: {payload.booking.scheduled_end_local_label or '—'}",
            "",
            "Chart",
            f"- Chart #: {payload.chart.chart_number or '—'}",
            f"- Notes summary: {payload.chart.chart_notes_summary or '—'}",
            "",
            "Clinical",
            f"- Primary diagnosis: {payload.diagnosis.diagnosis_text or '—'}",
            f"- Treatment plan: {payload.treatment_plan.title or payload.treatment_plan.plan_text or '—'}",
            f"- Latest note: {payload.complaint_and_notes.latest_note_text or '—'}",
            f"- Imaging refs: {payload.imaging.total_count}",
            f"- Odontogram surfaces: {payload.odontogram.surface_count_hint if payload.odontogram.surface_count_hint is not None else '—'}",
        ]
        if payload.warnings:
            lines.extend(["", "Warnings", f"- {', '.join(payload.warnings)}"])
        text = "\n".join(lines).strip() + "\n"
        return Rendered043Document(content=text.encode("utf-8"), content_type="text/plain", extension="txt")

    def _render_contact(self, contact_hint: str | None) -> str:
        if not contact_hint:
            return "—"
        if ":" not in contact_hint:
            return contact_hint
        raw_type, raw_value = contact_hint.split(":", 1)
        contact_type = raw_type.strip().lower()
        value = raw_value.strip()
        labels = {
            "phone": "Phone",
            "telegram": "Telegram",
            "email": "Email",
        }
        return f"{labels.get(contact_type, self._humanize_text(contact_type, fallback='Contact'))}: {value}" if value else "—"

    def _localize_or_humanize(self, value: str | None, *, locale: str, fallback: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return fallback
        catalog = self._load_locale_catalog(locale)
        localized = catalog.get(raw)
        if isinstance(localized, str) and localized.strip():
            return localized.strip()
        return self._humanize_text(raw, fallback=fallback)

    def _load_locale_catalog(self, locale: str) -> dict[str, str]:
        locale_file = self.locales_dir / f"{locale}.json"
        if not locale_file.exists():
            return {}
        return json.loads(locale_file.read_text(encoding="utf-8"))

    def _humanize_text(self, value: str | None, *, fallback: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return fallback
        head = raw
        if "." in raw and " " not in raw:
            head = raw.rsplit(".", 1)[-1]
        text = head.replace("_", " ").replace("-", " ").strip()
        if not text:
            return fallback
        return text[:1].upper() + text[1:]


@dataclass(slots=True)
class LocalArtifactStorage:
    base_dir: Path = Path(os.environ.get("DENTFLOW_EXPORT_ARTIFACTS_DIR", "artifacts/generated_documents"))

    def store(self, *, generated_document_id: str, artifact: Rendered043Document) -> StoredArtifact:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{generated_document_id}.{artifact.extension}"
        path = self.base_dir / filename
        path.write_bytes(artifact.content)
        checksum = hashlib.sha256(artifact.content).hexdigest()
        return StoredArtifact(
            storage_provider="local_fs",
            storage_ref=str(path),
            byte_size=len(artifact.content),
            checksum_sha256=checksum,
        )
