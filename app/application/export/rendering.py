from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.application.export.models import Structured043ExportPayload


@dataclass(slots=True, frozen=True)
class Editable043Document:
    content: bytes
    content_type: str
    extension: str


@dataclass(slots=True, frozen=True)
class Rendered043Document:
    content: bytes
    content_type: str
    extension: str
    editable_source: Editable043Document | None = None


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
    locales_dir: Path | None = None
    template_base_dir: Path | None = None

    def render(self, *, payload: Structured043ExportPayload, locale: str, template_source_ref: str) -> Rendered043Document:
        service_label = self._localize_or_humanize(payload.booking.service_label, locale=locale, fallback="Service")
        doctor_label = self._humanize_text(payload.booking.doctor_label, fallback="Doctor")
        branch_label = self._humanize_text(payload.booking.branch_label, fallback="Branch")
        contact_label = self._render_contact(payload.patient.primary_contact_hint)
        warnings_text = self._render_warnings(payload.warnings)

        final_text = self._render_template(
            template_source_ref=template_source_ref,
            values={
                "patient_name": payload.patient.full_name_legal or payload.patient.display_name,
                "patient_number": payload.patient.patient_number or "—",
                "patient_contact": contact_label,
                "patient_language": payload.patient.preferred_language or "—",
                "booking_id": self._render_booking_reference(payload.booking.booking_id),
                "booking_status": self._humanize_text(payload.booking.booking_status, fallback="Not set"),
                "booking_service": service_label,
                "booking_doctor": doctor_label,
                "booking_branch": branch_label,
                "booking_start": payload.booking.scheduled_start_local_label or "—",
                "booking_end": payload.booking.scheduled_end_local_label or "—",
                "chart_number": payload.chart.chart_number or "—",
                "chart_summary": payload.chart.chart_notes_summary or "Not recorded",
                "diagnosis_text": payload.diagnosis.diagnosis_text or "No current diagnosis recorded",
                "treatment_plan": payload.treatment_plan.title or payload.treatment_plan.plan_text or "No current treatment plan recorded",
                "latest_note": payload.complaint_and_notes.latest_note_text or "No chart note summary available",
                "imaging_count": self._render_imaging_summary(payload.imaging.total_count),
                "odontogram_surfaces": str(payload.odontogram.surface_count_hint)
                if payload.odontogram.surface_count_hint is not None
                else "No snapshot recorded",
                "warnings": warnings_text,
            },
        )
        editable_text = self._build_editable_source(payload=payload, rendered_text=final_text, template_source_ref=template_source_ref)
        return Rendered043Document(
            content=final_text.encode("utf-8"),
            content_type="text/plain",
            extension="txt",
            editable_source=Editable043Document(
                content=editable_text.encode("utf-8"),
                content_type="text/markdown",
                extension="md",
            ),
        )

    def _render_template(self, *, template_source_ref: str, values: dict[str, str]) -> str:
        template_text = self._load_template_text(template_source_ref)
        rendered = template_text.format_map(values).strip() + "\n"
        return rendered

    def _build_editable_source(
        self, *, payload: Structured043ExportPayload, rendered_text: str, template_source_ref: str
    ) -> str:
        lines = [
            "# DentFlow 043 Editable Source",
            "",
            f"- Template source: {template_source_ref}",
            f"- Template locale: {payload.metadata.template_locale}",
            f"- Template type: {payload.metadata.template_type}",
            "",
            "## Rendered Preview",
            "```text",
            rendered_text.rstrip("\n"),
            "```",
            "",
            "## Manual completion notes",
            "- Add clinic signature block if required.",
            "- Add stamp/attachment annotations if required.",
            "- Editable source is supplemental; generated artifact remains the registry-tracked final export.",
        ]
        return "\n".join(lines).strip() + "\n"

    def _render_booking_reference(self, booking_id: str | None) -> str:
        return "Linked scheduled booking" if booking_id else "No linked booking"

    def _render_imaging_summary(self, count: int) -> str:
        if count <= 0:
            return "No imaging references linked"
        return f"{count} linked"

    def _render_warnings(self, warnings: tuple[str, ...]) -> str:
        if not warnings:
            return "None"
        labels = [self._warning_label(code) for code in warnings]
        return ", ".join(sorted(set(labels)))

    def _warning_label(self, code: str) -> str:
        mapping = {
            "booking_context_missing": "Booking context is missing",
            "encounter_not_found_for_requested_id": "Encounter context could not be resolved",
            "current_diagnosis_missing": "Current diagnosis is missing",
            "current_treatment_plan_missing": "Current treatment plan is missing",
            "imaging_references_missing": "Imaging references are missing",
            "patient_contact_missing": "Patient contact is missing",
            "booking_doctor_unresolved": "Doctor reference is unresolved",
            "booking_service_unresolved": "Service reference is unresolved",
            "booking_branch_unresolved": "Branch reference is unresolved",
        }
        return mapping.get(code, self._humanize_text(code, fallback="Unknown warning"))

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
        locale_file = self._resolve_locales_dir() / f"{locale}.json"
        if not locale_file.exists():
            return {}
        return json.loads(locale_file.read_text(encoding="utf-8"))

    def _load_template_text(self, template_source_ref: str) -> str:
        source = template_source_ref.strip()
        if not source:
            raise ValueError("template_source_ref must be non-empty")
        if source.startswith("builtin://"):
            rel = source.removeprefix("builtin://")
            template_file = self._resolve_template_base_dir() / rel
        elif source.startswith("file://"):
            template_file = Path(source.removeprefix("file://")).expanduser()
        else:
            template_file = Path(source).expanduser()
            if not template_file.is_absolute():
                template_file = self._resolve_template_base_dir() / source
        if not template_file.exists():
            raise FileNotFoundError(f"template source not found: {template_source_ref}")
        return template_file.read_text(encoding="utf-8")

    def _resolve_locales_dir(self) -> Path:
        if self.locales_dir is not None:
            return self.locales_dir
        env_override = os.environ.get("DENTFLOW_LOCALES_DIR")
        if env_override:
            candidate = Path(env_override).expanduser()
            if candidate.exists():
                return candidate
        for candidate in (Path.cwd() / "locales", Path(__file__).resolve().parents[3] / "locales"):
            if candidate.exists():
                return candidate
        return Path("locales")

    def _resolve_template_base_dir(self) -> Path:
        if self.template_base_dir is not None:
            return self.template_base_dir
        env_override = os.environ.get("DENTFLOW_EXPORT_TEMPLATES_DIR")
        if env_override:
            candidate = Path(env_override).expanduser()
            if candidate.exists():
                return candidate
        for candidate in (Path.cwd() / "templates" / "exports", Path(__file__).resolve().parents[3] / "templates" / "exports"):
            if candidate.exists():
                return candidate
        return Path("templates/exports")

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
