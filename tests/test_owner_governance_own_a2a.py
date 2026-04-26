from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.common.i18n import I18nService
from app.domain.access_identity.models import ActorIdentity, ActorStatus, ActorType, ClinicRoleAssignment, RoleCode, StaffMember, StaffStatus, TelegramBinding
from app.interfaces.bots.owner.router import make_router


class _Message:
    def __init__(self, text: str, *, user_id: int = 501) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


def _handler_by_name(router, name: str):
    for handler in router.message.handlers:
        if handler.callback.__name__ == name:
            return handler.callback
    raise AssertionError(f"handler not found: {name}")


def _access(role: RoleCode) -> AccessResolver:
    repo = InMemoryAccessRepository()
    now = datetime(2026, 4, 26, tzinfo=timezone.utc)
    repo.upsert_actor_identity(ActorIdentity(actor_id="a1", actor_type=ActorType.STAFF, display_name="Owner", status=ActorStatus.ACTIVE, locale="en"))
    repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id="t1", actor_id="a1", telegram_user_id=501))
    repo.upsert_staff_member(StaffMember(staff_id="s1", actor_id="a1", clinic_id="c1", full_name="Owner", display_name="Owner", staff_status=StaffStatus.ACTIVE))
    repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id="r1", staff_id="s1", clinic_id="c1", role_code=role, granted_at=now))
    return AccessResolver(repo)


class _GovernanceStub:
    def __init__(self) -> None:
        self.last_limit: int | None = None

    async def get_today_snapshot(self, *, clinic_id: str):
        return SimpleNamespace(
            local_date=date(2026, 4, 26),
            bookings_today=1,
            pending_confirmations_today=1,
            completed_today=0,
            canceled_today=0,
            no_show_today=0,
            charts_opened_today=0,
            reminder_failures_today=0,
            open_alerts_count=0,
        )

    async def get_staff_access_overview(self, *, clinic_id: str, limit: int = 50):
        self.last_limit = limit
        return SimpleNamespace(
            rows=[
                SimpleNamespace(
                    actor_id="actor-1",
                    display_name="Alice Owner",
                    role_code="owner",
                    role_label="Owner",
                    staff_kind="owner",
                    doctor_id=None,
                    telegram_binding_state="yes",
                    active_state="active",
                    branch_id="b1",
                    branch_label="Main branch",
                ),
                SimpleNamespace(
                    actor_id="very-long-actor-id-0002",
                    display_name=None,
                    role_code=None,
                    role_label=None,
                    staff_kind="unknown",
                    doctor_id=None,
                    telegram_binding_state="unknown",
                    active_state="unknown",
                    branch_id=None,
                    branch_label=None,
                ),
            ]
        )


def test_owner_staff_owner_guard_and_non_regression_today() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    owner_router = make_router(i18n, _access(RoleCode.OWNER), analytics=_GovernanceStub(), default_locale="en")
    admin_router = make_router(i18n, _access(RoleCode.ADMIN), analytics=_GovernanceStub(), default_locale="en")

    allowed = _Message("/owner_staff")
    asyncio.run(_handler_by_name(owner_router, "owner_staff")(allowed))
    assert "Owner Staff / Access Overview" in allowed.answers[-1]

    denied = _Message("/owner_staff")
    asyncio.run(_handler_by_name(admin_router, "owner_staff")(denied))
    assert any("Access denied" in x for x in denied.answers)

    today = _Message("/owner_today")
    asyncio.run(_handler_by_name(owner_router, "owner_today")(today))
    assert "Owner Today" in today.answers[-1]


def test_owner_staff_default_and_explicit_limit() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    analytics = _GovernanceStub()
    router = make_router(i18n, _access(RoleCode.OWNER), analytics=analytics, default_locale="en")

    default_msg = _Message("/owner_staff")
    asyncio.run(_handler_by_name(router, "owner_staff")(default_msg))
    assert analytics.last_limit == 30

    explicit_msg = _Message("/owner_staff 50")
    asyncio.run(_handler_by_name(router, "owner_staff")(explicit_msg))
    assert analytics.last_limit == 50


def test_owner_staff_invalid_limit_usage() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    router = make_router(i18n, _access(RoleCode.OWNER), analytics=_GovernanceStub(), default_locale="en")

    bad_msg = _Message("/owner_staff 0")
    asyncio.run(_handler_by_name(router, "owner_staff")(bad_msg))
    assert "Invalid limit" in bad_msg.answers[0]
    assert "Usage: /owner_staff" in bad_msg.answers[1]


def test_owner_staff_rows_include_role_and_telegram_and_safe_fallback() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    router = make_router(i18n, _access(RoleCode.OWNER), analytics=_GovernanceStub(), default_locale="en")

    msg = _Message("/owner_staff")
    asyncio.run(_handler_by_name(router, "owner_staff")(msg))
    payload = msg.answers[-1]
    assert "role:Owner" in payload
    assert "tg:yes" in payload
    assert "kind:unknown" in payload
    assert "very-l…0002" in payload


def test_owner_staff_empty_state() -> None:
    class _EmptyStub(_GovernanceStub):
        async def get_staff_access_overview(self, *, clinic_id: str, limit: int = 50):
            return SimpleNamespace(rows=[])

    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    router = make_router(i18n, _access(RoleCode.OWNER), analytics=_EmptyStub(), default_locale="en")
    msg = _Message("/owner_staff")
    asyncio.run(_handler_by_name(router, "owner_staff")(msg))
    assert "No staff/access rows found" in msg.answers[-1]


def test_owner_staff_unavailable_is_bounded() -> None:
    class _BrokenStub(_GovernanceStub):
        async def get_staff_access_overview(self, *, clinic_id: str, limit: int = 50):
            raise RuntimeError("db down")

    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    router = make_router(i18n, _access(RoleCode.OWNER), analytics=_BrokenStub(), default_locale="en")
    msg = _Message("/owner_staff")
    asyncio.run(_handler_by_name(router, "owner_staff")(msg))
    assert msg.answers[-1] == "Staff access overview is temporarily unavailable."
