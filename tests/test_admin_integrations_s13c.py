from __future__ import annotations

import asyncio
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.common.i18n import I18nService
from app.domain.access_identity.models import (
    ActorIdentity,
    ActorStatus,
    ActorType,
    ClinicRoleAssignment,
    RoleCode,
    StaffMember,
    StaffStatus,
    TelegramBinding,
)
from app.interfaces.bots.admin.router import make_router


class _Message:
    def __init__(self, text: str, user_id: int = 501) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))


class _Reference:
    def get_clinic(self, clinic_id: str):
        return SimpleNamespace(default_locale="en")

    def get_service(self, clinic_id: str, service_id: str):
        return None

    def get_branch(self, clinic_id: str, branch_id: str):
        return SimpleNamespace(display_name="Main")


class _BookingFlow:
    reads = SimpleNamespace()
    orchestration = SimpleNamespace()


class _CatalogSyncService:
    pass


class _CalendarReadService:
    pass


def _access(*, admin_user_id: int = 501, role: RoleCode = RoleCode.ADMIN) -> AccessResolver:
    repo = InMemoryAccessRepository()
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    repo.upsert_actor_identity(ActorIdentity(actor_id="a1", actor_type=ActorType.STAFF, display_name="Admin", status=ActorStatus.ACTIVE, locale="en"))
    repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id="t1", actor_id="a1", telegram_user_id=admin_user_id))
    repo.upsert_staff_member(StaffMember(staff_id="s1", actor_id="a1", clinic_id="c1", full_name="Admin", display_name="Admin", staff_status=StaffStatus.ACTIVE))
    repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id="r1", staff_id="s1", clinic_id="c1", role_code=role, granted_at=now))
    return AccessResolver(repo)


def _router(*, access: AccessResolver, catalog_service=None, calendar_service=None):
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    return make_router(
        i18n,
        access,
        _Reference(),
        _BookingFlow(),
        search_service=SimpleNamespace(),
        stt_service=SimpleNamespace(),
        voice_mode_store=SimpleNamespace(),
        default_locale="en",
        max_voice_duration_sec=60,
        max_voice_file_size_bytes=1024,
        voice_mode_ttl_sec=30,
        care_catalog_sync_service=catalog_service,
        calendar_projection_read_service=calendar_service,
    )


def _handler(router, name: str):
    for h in router.message.handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(name)


def test_admin_integrations_is_admin_guarded() -> None:
    router = _router(
        access=_access(admin_user_id=777, role=RoleCode.DOCTOR),
        catalog_service=_CatalogSyncService(),
        calendar_service=_CalendarReadService(),
    )
    msg = _Message("/admin_integrations", user_id=777)
    asyncio.run(_handler(router, "admin_integrations")(msg))
    assert msg.answers
    assert "Access denied" in msg.answers[-1][0]


def test_admin_integrations_lists_catalog_and_calendar_hints_and_truth_boundaries() -> None:
    router = _router(
        access=_access(),
        catalog_service=_CatalogSyncService(),
        calendar_service=_CalendarReadService(),
    )
    msg = _Message("/admin_integrations")
    asyncio.run(_handler(router, "admin_integrations")(msg))
    text = msg.answers[-1][0]
    low = text.lower()

    assert "/admin_catalog_sync sheets <url_or_id>" in text
    assert "/admin_catalog_sync xlsx <server_local_path>" in text
    assert "/admin_calendar" in text

    assert "DentFlow booking data is source of truth" in text
    assert "Google Calendar is read-only mirror" in text
    assert "Google Sheets/XLSX are import authoring surfaces" in text
    assert "not runtime order/booking truth" in text

    assert "sync from calendar" not in low
    assert "calendar edits update dentflow" not in low
    assert "sheets are live runtime catalog truth" not in low


def test_admin_integrations_wiring_hints_are_bounded_when_services_absent() -> None:
    router = _router(access=_access(), catalog_service=None, calendar_service=None)
    msg = _Message("/admin_integrations")
    asyncio.run(_handler(router, "admin_integrations")(msg))
    text = msg.answers[-1][0]

    assert text.count("Surface wiring: unavailable in this runtime.") == 2
    assert "Worker liveness is not available from bot runtime" in text


def test_s13_c_does_not_add_migration_files() -> None:
    tracked = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
    migration_paths = [
        path
        for path in tracked
        if path.startswith("migrations/")
        or path.startswith("alembic/versions/")
        or path.startswith("db/migrations/")
    ]
    assert migration_paths == []
