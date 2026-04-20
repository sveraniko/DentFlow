from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.application.export.services import TemplateResolutionError
from app.common.i18n import I18nService
from app.domain.access_identity.models import ActorIdentity, ActorStatus, ActorType, ClinicRoleAssignment, DoctorProfile, RoleCode, StaffMember, StaffStatus, TelegramBinding
from app.domain.media_docs.models import GeneratedDocument, MediaAsset
from app.interfaces.bots.admin.router import make_router as make_admin_router
from app.interfaces.bots.doctor.router import make_router as make_doctor_router


class _Message:
    def __init__(self, text: str, user_id: int) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))


class _ExportService:
    def __init__(self) -> None:
        self.calls: list[object] = []
        self.error: Exception | None = None

    async def generate_043_export(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        return SimpleNamespace(generated_document_id="gdoc_new")


class _GeneratedRegistry:
    def __init__(self, rows: dict[str, GeneratedDocument]) -> None:
        self.rows = rows

    async def list_for_booking(self, *, booking_id: str):
        return [row for row in self.rows.values() if row.booking_id == booking_id]

    async def list_for_patient(self, *, patient_id: str, clinic_id: str | None = None):
        return [row for row in self.rows.values() if row.patient_id == patient_id and (clinic_id is None or row.clinic_id == clinic_id)]

    async def get_generated_document(self, generated_document_id: str):
        return self.rows.get(generated_document_id)


class _MediaRegistry:
    def __init__(self, rows: dict[str, MediaAsset]) -> None:
        self.rows = rows

    async def get_media_asset(self, media_asset_id: str):
        return self.rows.get(media_asset_id)


class _DoctorBookingService:
    def __init__(self) -> None:
        self.booking = SimpleNamespace(
            booking_id="b1",
            patient_id="p1",
            clinic_id="c1",
            doctor_id="d1",
            branch_id="br1",
            service_id="s1",
            status="confirmed",
            scheduled_start_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
        )

    async def load_booking(self, booking_id: str):
        return self.booking if booking_id == "b1" else None

    async def list_by_patient(self, *, patient_id: str):
        return [self.booking] if patient_id == "p1" else []


class _PatientReader:
    async def read_snapshot(self, *, patient_id: str):
        if patient_id != "p1":
            return None
        return SimpleNamespace(
            patient_id="p1",
            display_name="Jane Roe",
            patient_number="1001",
            phone_raw="+15550001111",
            has_photo=False,
            active_flags_summary=None,
        )


class _Reference:
    def list_clinics(self):
        return [SimpleNamespace(clinic_id="c1", timezone="UTC")]

    def get_doctor(self, clinic_id: str, doctor_id: str):
        if clinic_id == "c1" and doctor_id == "d1":
            return SimpleNamespace(doctor_id="d1", branch_id="br1")
        return None

    def list_services(self, clinic_id: str):
        return [SimpleNamespace(service_id="s1", code="CONS", title_key="Consultation")]

    def list_branches(self, clinic_id: str):
        return [SimpleNamespace(branch_id="br1", display_name="Main", timezone="UTC")]

    def get_clinic(self, clinic_id: str):
        return SimpleNamespace(default_locale="en", timezone="UTC")


class _Clinical:
    async def open_or_get_chart(self, *, patient_id: str, clinic_id: str, primary_doctor_id: str | None = None):
        return SimpleNamespace(chart_id="ch1")


def _access(*, role: RoleCode, telegram_user_id: int, actor_id: str) -> AccessResolver:
    repo = InMemoryAccessRepository()
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    repo.upsert_actor_identity(ActorIdentity(actor_id=actor_id, actor_type=ActorType.STAFF, display_name="User", status=ActorStatus.ACTIVE, locale="en"))
    repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id=f"tb_{actor_id}", actor_id=actor_id, telegram_user_id=telegram_user_id))
    repo.upsert_staff_member(StaffMember(staff_id=f"st_{actor_id}", actor_id=actor_id, clinic_id="c1", full_name="User", display_name="User", staff_status=StaffStatus.ACTIVE))
    repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id=f"ra_{actor_id}", staff_id=f"st_{actor_id}", clinic_id="c1", role_code=role, granted_at=now))
    if role == RoleCode.DOCTOR:
        repo.upsert_doctor_profile(DoctorProfile(doctor_profile_id="dp1", staff_id=f"st_{actor_id}", clinic_id="c1", doctor_id="d1", specialty_code="general", active_for_clinical_work=True))
    return AccessResolver(repo)


def _handler(router, name: str):
    for h in router.message.handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(name)


def test_doctor_generate_uses_export_app_seam() -> None:
    i18n = I18nService(Path("locales"), default_locale="en")
    export = _ExportService()
    router = make_doctor_router(
        i18n,
        _access(role=RoleCode.DOCTOR, telegram_user_id=501, actor_id="a_doctor"),
        search_service=SimpleNamespace(),
        stt_service=SimpleNamespace(),
        voice_mode_store=SimpleNamespace(),
        booking_service=_DoctorBookingService(),
        booking_state_service=SimpleNamespace(),
        booking_orchestration=SimpleNamespace(),
        reference_service=_Reference(),
        patient_reader=_PatientReader(),
        clinical_service=_Clinical(),
        recommendation_service=SimpleNamespace(),
        default_locale="en",
        max_voice_duration_sec=60,
        max_voice_file_size_bytes=1024,
        voice_mode_ttl_sec=30,
        document_export_service=export,
        generated_document_registry=_GeneratedRegistry({}),
        media_asset_registry=_MediaRegistry({}),
    )
    msg = _Message("/doc_generate p1 b1", user_id=501)
    asyncio.run(_handler(router, "doc_generate")(msg))
    assert export.calls and export.calls[0].template_type == "043_card_export"
    assert "Document generated" in msg.answers[-1][0]


def test_doctor_generate_forbidden_role_is_blocked() -> None:
    i18n = I18nService(Path("locales"), default_locale="en")
    export = _ExportService()
    router = make_doctor_router(
        i18n,
        _access(role=RoleCode.ADMIN, telegram_user_id=502, actor_id="a_admin"),
        search_service=SimpleNamespace(),
        stt_service=SimpleNamespace(),
        voice_mode_store=SimpleNamespace(),
        default_locale="en",
        max_voice_duration_sec=60,
        max_voice_file_size_bytes=1024,
        voice_mode_ttl_sec=30,
        document_export_service=export,
        generated_document_registry=_GeneratedRegistry({}),
        media_asset_registry=_MediaRegistry({}),
    )
    msg = _Message("/doc_generate p1 b1", user_id=502)
    asyncio.run(_handler(router, "doc_generate")(msg))
    assert "Access denied" in msg.answers[-1][0]
    assert not export.calls


def test_admin_registry_open_and_regenerate_template_failure() -> None:
    i18n = I18nService(Path("locales"), default_locale="en")
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    row = GeneratedDocument(
        generated_document_id="g1",
        clinic_id="c1",
        patient_id="p1",
        chart_id="ch1",
        encounter_id=None,
        booking_id="b1",
        document_template_id="dt1",
        document_type="043_card_export",
        generation_status="failed",
        generated_file_asset_id=None,
        editable_source_asset_id=None,
        created_by_actor_id="a_admin",
        created_at=now,
        updated_at=now,
        generation_error_text="template missing",
    )
    export = _ExportService()
    export.error = TemplateResolutionError("missing template")
    router = make_admin_router(
        i18n,
        _access(role=RoleCode.ADMIN, telegram_user_id=601, actor_id="a_admin"),
        reference_service=SimpleNamespace(get_clinic=lambda cid: SimpleNamespace(default_locale="en"), get_service=lambda c, s: None),
        booking_flow=SimpleNamespace(),
        search_service=SimpleNamespace(),
        stt_service=SimpleNamespace(),
        voice_mode_store=SimpleNamespace(),
        default_locale="en",
        max_voice_duration_sec=60,
        max_voice_file_size_bytes=1024,
        voice_mode_ttl_sec=30,
        document_export_service=export,
        generated_document_registry=_GeneratedRegistry({"g1": row}),
        media_asset_registry=_MediaRegistry({}),
    )
    open_msg = _Message("/admin_doc_open g1", user_id=601)
    asyncio.run(_handler(router, "admin_doc_open")(open_msg))
    assert "Failed" in open_msg.answers[-1][0]
    assert "template is unavailable" in open_msg.answers[-1][0]

    regen_msg = _Message("/admin_doc_regenerate g1", user_id=601)
    asyncio.run(_handler(router, "admin_doc_regenerate")(regen_msg))
    assert "template is unavailable" in regen_msg.answers[-1][0]


def test_admin_download_shows_artifact_ref_when_exists() -> None:
    i18n = I18nService(Path("locales"), default_locale="en")
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    row = GeneratedDocument(
        generated_document_id="g2",
        clinic_id="c1",
        patient_id="p1",
        chart_id="ch1",
        encounter_id=None,
        booking_id=None,
        document_template_id="dt1",
        document_type="043_card_export",
        generation_status="generated",
        generated_file_asset_id="m1",
        editable_source_asset_id=None,
        created_by_actor_id="a_admin",
        created_at=now,
        updated_at=now,
        generation_error_text=None,
    )
    asset = MediaAsset(
        media_asset_id="m1",
        clinic_id="c1",
        asset_kind="generated_document",
        storage_provider="local_fs",
        storage_ref="artifacts/generated_documents/g2.txt",
        content_type="text/plain",
        byte_size=12,
        checksum_sha256="abc",
        created_by_actor_id="a_admin",
        created_at=now,
        updated_at=now,
    )
    router = make_admin_router(
        i18n,
        _access(role=RoleCode.ADMIN, telegram_user_id=602, actor_id="a_admin"),
        reference_service=SimpleNamespace(get_clinic=lambda cid: SimpleNamespace(default_locale="en"), get_service=lambda c, s: None),
        booking_flow=SimpleNamespace(),
        search_service=SimpleNamespace(),
        stt_service=SimpleNamespace(),
        voice_mode_store=SimpleNamespace(),
        default_locale="en",
        max_voice_duration_sec=60,
        max_voice_file_size_bytes=1024,
        voice_mode_ttl_sec=30,
        document_export_service=_ExportService(),
        generated_document_registry=_GeneratedRegistry({"g2": row}),
        media_asset_registry=_MediaRegistry({"m1": asset}),
    )
    msg = _Message("/admin_doc_download g2", user_id=602)
    asyncio.run(_handler(router, "admin_doc_download")(msg))
    assert "artifacts/generated_documents/g2.txt" in msg.answers[-1][0]
