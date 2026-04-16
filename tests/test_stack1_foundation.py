import pytest

pytest.importorskip("sqlalchemy")

from pathlib import Path

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.application.policy import InMemoryPolicyRepository, PolicyResolver
from app.domain.access_identity.models import (
    ActorIdentity,
    ActorType,
    ClinicRoleAssignment,
    RoleCode,
    StaffMember,
    TelegramBinding,
)
from app.domain.clinic_reference.models import Clinic
from app.domain.policy_config.models import PolicySet, PolicyValue
from app.infrastructure.db import repositories as stack_repositories


class _DummyConn:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | None]] = []

    async def execute(self, stmt, params=None):
        self.calls.append((str(stmt), params))
        return None


class _DummyBegin:
    def __init__(self, conn: _DummyConn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyEngine:
    def __init__(self) -> None:
        self.conn = _DummyConn()

    def begin(self):
        return _DummyBegin(self.conn)

    async def dispose(self):
        return None


def test_reference_entities_create_and_load() -> None:
    clinic_repo = InMemoryClinicReferenceRepository()
    clinic_repo.upsert_clinic(
        Clinic(
            clinic_id="clinic_main",
            code="dentflow-main",
            display_name="DentFlow Demo Clinic",
            timezone="Europe/Moscow",
            default_locale="ru",
        )
    )

    service = ClinicReferenceService(clinic_repo)
    clinic = service.get_clinic("clinic_main")
    assert clinic is not None
    assert clinic.code == "dentflow-main"


def test_access_resolution_and_role_denial() -> None:
    repository = InMemoryAccessRepository()
    repository.upsert_actor_identity(ActorIdentity(actor_id="a1", actor_type=ActorType.STAFF, display_name="Admin"))
    repository.upsert_telegram_binding(TelegramBinding(telegram_binding_id="t1", actor_id="a1", telegram_user_id=2001))
    repository.upsert_staff_member(
        StaffMember(staff_id="s1", actor_id="a1", clinic_id="clinic_main", full_name="Admin User", display_name="Admin")
    )
    repository.upsert_role_assignment(
        ClinicRoleAssignment(role_assignment_id="r1", staff_id="s1", clinic_id="clinic_main", role_code=RoleCode.ADMIN)
    )

    resolver = AccessResolver(repository)
    context = resolver.resolve_actor_context(2001)
    assert context is not None
    assert RoleCode.ADMIN in context.role_codes
    assert resolver.check_roles(context, {RoleCode.ADMIN}).allowed
    assert not resolver.check_roles(context, {RoleCode.DOCTOR}).allowed


def test_policy_resolution_precedence() -> None:
    repository = InMemoryPolicyRepository()
    repository.upsert_policy_set(
        PolicySet(policy_set_id="clinic_set", policy_family="booking_policy", scope_type="clinic", scope_ref="clinic_main")
    )
    repository.add_policy_value(
        PolicyValue(
            policy_value_id="clinic_booking_enabled",
            policy_set_id="clinic_set",
            policy_key="booking.enabled",
            value_type="bool",
            value_json=False,
        )
    )
    repository.upsert_policy_set(
        PolicySet(policy_set_id="branch_set", policy_family="booking_policy", scope_type="branch", scope_ref="branch_central")
    )
    repository.add_policy_value(
        PolicyValue(
            policy_value_id="branch_booking_enabled",
            policy_set_id="branch_set",
            policy_key="booking.enabled",
            value_type="bool",
            value_json=True,
            is_override=True,
        )
    )

    resolver = PolicyResolver(repository)
    assert resolver.resolve_policy("booking.enabled", clinic_id="clinic_main") is False
    assert resolver.resolve_policy("booking.enabled", clinic_id="clinic_main", branch_id="branch_central") is True


@pytest.mark.asyncio
async def test_seed_stack1_writes_to_db(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _DummyEngine()
    monkeypatch.setattr(stack_repositories, "create_engine", lambda _: engine)

    counts = await stack_repositories.seed_stack_data(object(), Path("seeds/stack1_seed.json"))

    assert counts["clinics"] == 1
    assert any("INSERT INTO core_reference.clinics" in sql for sql, _ in engine.conn.calls)
    assert any("INSERT INTO access_identity.actor_identities" in sql for sql, _ in engine.conn.calls)
    assert any("INSERT INTO policy_config.policy_sets" in sql for sql, _ in engine.conn.calls)
