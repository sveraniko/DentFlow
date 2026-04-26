from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.application.integration.google_calendar_projection import CalendarProjectionRecentMapping, CalendarProjectionSummary
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


class _CalendarReadService:
    async def get_calendar_projection_summary(self, *, clinic_id: str) -> CalendarProjectionSummary:
        return CalendarProjectionSummary(mapped_events=4, pending_projection=2, failed_projection=1)

    async def list_recent_calendar_mappings(
        self,
        *,
        clinic_id: str,
        limit: int = 5,
    ) -> list[CalendarProjectionRecentMapping]:
        return [
            CalendarProjectionRecentMapping(
                booking_id="b10",
                sync_status="synced",
                target_calendar_id="doc_1",
                external_event_id="evt_1",
                last_synced_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
            ),
            CalendarProjectionRecentMapping(
                booking_id="b11",
                sync_status="failed",
                target_calendar_id="doc_2",
                external_event_id=None,
                last_synced_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
            ),
        ]


class _CalendarReadServiceEmpty(_CalendarReadService):
    async def get_calendar_projection_summary(self, *, clinic_id: str) -> CalendarProjectionSummary:
        return CalendarProjectionSummary(mapped_events=0, pending_projection=0, failed_projection=0)

    async def list_recent_calendar_mappings(
        self,
        *,
        clinic_id: str,
        limit: int = 5,
    ) -> list[CalendarProjectionRecentMapping]:
        return []


class _CalendarReadServiceUnavailable:
    async def get_calendar_projection_summary(self, *, clinic_id: str) -> CalendarProjectionSummary:
        raise RuntimeError("db-down")

    async def list_recent_calendar_mappings(self, *, clinic_id: str, limit: int = 5) -> list[CalendarProjectionRecentMapping]:
        raise RuntimeError("db-down")


def _access(*, admin_user_id: int = 501, role: RoleCode = RoleCode.ADMIN) -> AccessResolver:
    repo = InMemoryAccessRepository()
    now = datetime(2026, 4, 17, tzinfo=timezone.utc)
    repo.upsert_actor_identity(ActorIdentity(actor_id="a1", actor_type=ActorType.STAFF, display_name="Admin", status=ActorStatus.ACTIVE, locale="en"))
    repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id="t1", actor_id="a1", telegram_user_id=admin_user_id))
    repo.upsert_staff_member(StaffMember(staff_id="s1", actor_id="a1", clinic_id="c1", full_name="Admin", display_name="Admin", staff_status=StaffStatus.ACTIVE))
    repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id="r1", staff_id="s1", clinic_id="c1", role_code=role, granted_at=now))
    return AccessResolver(repo)


def _router(*, access: AccessResolver, calendar_service) -> object:
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
        calendar_projection_read_service=calendar_service,
    )


def _handler(router, name: str):
    for h in router.message.handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(name)


def test_admin_calendar_panel_renders_read_only_mirror_summary() -> None:
    router = _router(access=_access(), calendar_service=_CalendarReadService())
    msg = _Message("/admin_calendar")
    asyncio.run(_handler(router, "admin_calendar")(msg))
    text = msg.answers[-1][0]
    assert "Google Calendar mirror awareness" in text
    assert "source of truth" in text
    assert "Recent mirrored bookings:" in text
    assert "b10" in text and "synced" in text


def test_admin_calendar_empty_state_is_bounded() -> None:
    router = _router(access=_access(), calendar_service=_CalendarReadServiceEmpty())
    msg = _Message("/admin_calendar")
    asyncio.run(_handler(router, "admin_calendar")(msg))
    assert "No projected mapping rows yet." in msg.answers[-1][0]


def test_admin_calendar_unavailable_is_bounded() -> None:
    router = _router(access=_access(), calendar_service=_CalendarReadServiceUnavailable())
    msg = _Message("/admin_calendar")
    asyncio.run(_handler(router, "admin_calendar")(msg))
    assert "Calendar projection awareness is unavailable" in msg.answers[-1][0]


def test_admin_calendar_non_admin_is_guarded() -> None:
    router = _router(access=_access(admin_user_id=777, role=RoleCode.DOCTOR), calendar_service=_CalendarReadService())
    msg = _Message("/admin_calendar", user_id=777)
    asyncio.run(_handler(router, "admin_calendar")(msg))
    assert msg.answers
    assert "Access denied" in msg.answers[-1][0]
