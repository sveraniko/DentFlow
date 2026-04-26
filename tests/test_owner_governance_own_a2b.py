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


class _PatientBaseStub:
    def __init__(self) -> None:
        self.last_days: int | None = None

    async def get_today_snapshot(self, *, clinic_id: str):
        return SimpleNamespace(
            local_date=date(2026, 4, 26),
            bookings_today=2,
            pending_confirmations_today=1,
            completed_today=1,
            canceled_today=0,
            no_show_today=0,
            charts_opened_today=0,
            reminder_failures_today=0,
            open_alerts_count=0,
        )

    async def get_patient_base_snapshot(self, *, clinic_id: str, days: int = 30, limit: int = 10):
        self.last_days = days
        return SimpleNamespace(
            total_patients_count=120,
            new_patients_in_window_count=14,
            upcoming_live_booking_patients_count=9,
            completed_booking_patients_in_window_count=21,
            active_care_patients_count=6,
            telegram_bound_patients_count=88,
            recent_new_patients=[
                SimpleNamespace(patient_id=f"patient-{i}", display_name=f"Patient {i}", created_at=datetime(2026, 4, 26, tzinfo=timezone.utc))
                for i in range(1, 13)
            ][:limit],
        )

    async def get_clinic_reference_overview(self, *, clinic_id: str, limit: int = 20):
        return SimpleNamespace(
            branches=[
                SimpleNamespace(branch_id="branch-1", display_name="Main Branch", status="active", timezone="Europe/Tbilisi"),
            ][:limit],
            services=[
                SimpleNamespace(service_id="service-1", code="SVC-101", title_key="service.cleaning", duration_minutes=45, status="active"),
                SimpleNamespace(service_id="service-2", code="SVC-201", title_key="service.unknown_title", duration_minutes=30, status=None),
                SimpleNamespace(service_id="service-3", code=None, title_key=None, duration_minutes=None, status="active"),
            ][:limit],
            doctors=[
                SimpleNamespace(
                    doctor_id="doctor-1",
                    display_name="Dr. Bright",
                    specialty="orthodontics",
                    status="active",
                    branch_id="branch-1",
                    branch_display_name="Main Branch",
                ),
                SimpleNamespace(
                    doctor_id="doctor-2",
                    display_name=None,
                    specialty=None,
                    status=None,
                    branch_id=None,
                    branch_display_name=None,
                ),
            ][:limit],
        )


def test_owner_patients_guard_and_default_explicit_window_and_today_non_regression() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    analytics = _PatientBaseStub()
    owner_router = make_router(i18n, _access(RoleCode.OWNER), analytics=analytics, default_locale="en")
    admin_router = make_router(i18n, _access(RoleCode.ADMIN), analytics=_PatientBaseStub(), default_locale="en")

    default_msg = _Message("/owner_patients")
    asyncio.run(_handler_by_name(owner_router, "owner_patients")(default_msg))
    assert "Owner Patient Base Snapshot" in default_msg.answers[-1]
    assert analytics.last_days == 30

    explicit_msg = _Message("/owner_patients 45")
    asyncio.run(_handler_by_name(owner_router, "owner_patients")(explicit_msg))
    assert analytics.last_days == 45

    denied_msg = _Message("/owner_patients")
    asyncio.run(_handler_by_name(admin_router, "owner_patients")(denied_msg))
    assert any("Access denied" in x for x in denied_msg.answers)

    today_msg = _Message("/owner_today")
    asyncio.run(_handler_by_name(owner_router, "owner_today")(today_msg))
    assert "Owner Today" in today_msg.answers[-1]


def test_owner_patients_invalid_window_usage() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    router = make_router(i18n, _access(RoleCode.OWNER), analytics=_PatientBaseStub(), default_locale="en")

    bad_msg = _Message("/owner_patients 0")
    asyncio.run(_handler_by_name(router, "owner_patients")(bad_msg))
    assert "Invalid window" in bad_msg.answers[0]
    assert "Usage: /owner_patients" in bad_msg.answers[1]


def test_owner_patients_renders_counts_bounded_recent_and_privacy_safe() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    router = make_router(i18n, _access(RoleCode.OWNER), analytics=_PatientBaseStub(), default_locale="en")

    msg = _Message("/owner_patients")
    asyncio.run(_handler_by_name(router, "owner_patients")(msg))
    payload = msg.answers[-1]

    assert "Total patients: 120" in payload
    assert "New patients (30d): 14" in payload
    assert "Patients with upcoming/live bookings: 9" in payload
    assert "Patients with completed bookings (30d): 21" in payload
    assert "Patients with active care orders/reservations: 6" in payload
    assert "Patients with Telegram binding: 88" in payload

    assert payload.count("\n• Patient") == 10
    assert "diagnosis" not in payload.lower()
    assert "medical" not in payload.lower()
    assert "recommendation" not in payload.lower()


def test_owner_patients_unknown_unavailable_and_empty_recent_safe() -> None:
    class _UnknownStub(_PatientBaseStub):
        async def get_patient_base_snapshot(self, *, clinic_id: str, days: int = 30, limit: int = 10):
            return SimpleNamespace(
                total_patients_count=None,
                new_patients_in_window_count=None,
                upcoming_live_booking_patients_count=None,
                completed_booking_patients_in_window_count=None,
                active_care_patients_count=None,
                telegram_bound_patients_count=None,
                recent_new_patients=[],
            )

    class _BrokenStub(_PatientBaseStub):
        async def get_patient_base_snapshot(self, *, clinic_id: str, days: int = 30, limit: int = 10):
            raise RuntimeError("db down")

    i18n = I18nService(locales_path=Path("locales"), default_locale="en")

    unknown_router = make_router(i18n, _access(RoleCode.OWNER), analytics=_UnknownStub(), default_locale="en")
    unknown_msg = _Message("/owner_patients")
    asyncio.run(_handler_by_name(unknown_router, "owner_patients")(unknown_msg))
    unknown_payload = unknown_msg.answers[-1]
    assert unknown_payload.count("unknown") >= 6
    assert "No recent new patients" in unknown_payload

    broken_router = make_router(i18n, _access(RoleCode.OWNER), analytics=_BrokenStub(), default_locale="en")
    broken_msg = _Message("/owner_patients")
    asyncio.run(_handler_by_name(broken_router, "owner_patients")(broken_msg))
    assert broken_msg.answers[-1] == "Patient base snapshot is temporarily unavailable."


def test_owner_references_guard_default_valid_invalid_and_sections() -> None:
    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    owner_router = make_router(i18n, _access(RoleCode.OWNER), analytics=_PatientBaseStub(), default_locale="en")
    admin_router = make_router(i18n, _access(RoleCode.ADMIN), analytics=_PatientBaseStub(), default_locale="en")

    default_msg = _Message("/owner_references")
    asyncio.run(_handler_by_name(owner_router, "owner_references")(default_msg))
    payload = default_msg.answers[-1]
    assert "Owner Clinic Reference Overview" in payload
    assert "Branches (" in payload
    assert "Services (" in payload
    assert "Doctors (" in payload

    explicit_msg = _Message("/owner_references 12")
    asyncio.run(_handler_by_name(owner_router, "owner_references")(explicit_msg))
    assert "per-section limit: 12" in explicit_msg.answers[-1]

    bad_msg = _Message("/owner_references 0")
    asyncio.run(_handler_by_name(owner_router, "owner_references")(bad_msg))
    assert "Invalid limit" in bad_msg.answers[0]
    assert "Usage: /owner_references" in bad_msg.answers[1]

    denied_msg = _Message("/owner_references")
    asyncio.run(_handler_by_name(admin_router, "owner_references")(denied_msg))
    assert any("Access denied" in x for x in denied_msg.answers)
    assert not any("edit" in handler.callback.__name__ for handler in owner_router.message.handlers)


def test_owner_references_localization_fallback_empty_and_unavailable_safe() -> None:
    class _RefsStub(_PatientBaseStub):
        async def get_clinic_reference_overview(self, *, clinic_id: str, limit: int = 20):
            return SimpleNamespace(
                branches=[],
                services=[
                    SimpleNamespace(service_id="service-1", code="SVC-101", title_key="service.cleaning", duration_minutes=45, status="active"),
                    SimpleNamespace(service_id="service-2", code="SVC-201", title_key="service.not_translated", duration_minutes=30, status=None),
                    SimpleNamespace(service_id="service-3", code=None, title_key=None, duration_minutes=None, status="active"),
                ][:limit],
                doctors=[],
            )

    class _BrokenRefsStub(_PatientBaseStub):
        async def get_clinic_reference_overview(self, *, clinic_id: str, limit: int = 20):
            raise RuntimeError("db down")

    i18n = I18nService(locales_path=Path("locales"), default_locale="en")
    router = make_router(i18n, _access(RoleCode.OWNER), analytics=_RefsStub(), default_locale="en")
    msg = _Message("/owner_references")
    asyncio.run(_handler_by_name(router, "owner_references")(msg))
    payload = msg.answers[-1]

    assert "• empty" in payload
    assert "service.cleaning" not in payload
    assert "Teeth cleaning" in payload
    assert "code:SVC-201" in payload
    assert "dur:unknownm" in payload

    broken_router = make_router(i18n, _access(RoleCode.OWNER), analytics=_BrokenRefsStub(), default_locale="en")
    broken_msg = _Message("/owner_references")
    asyncio.run(_handler_by_name(broken_router, "owner_references")(broken_msg))
    assert broken_msg.answers[-1] == "Clinic reference overview is temporarily unavailable."
