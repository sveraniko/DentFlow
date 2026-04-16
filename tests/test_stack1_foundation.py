from pathlib import Path

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.application.policy import InMemoryPolicyRepository, PolicyResolver
from app.bootstrap.seed import SeedBootstrap
from app.domain.access_identity.models import (
    ActorIdentity,
    ActorType,
    ClinicRoleAssignment,
    RoleCode,
    StaffMember,
    TelegramBinding,
)
from app.domain.policy_config.models import PolicySet, PolicyValue


def test_reference_entities_create_and_load() -> None:
    clinic_repo = InMemoryClinicReferenceRepository()
    access_repo = InMemoryAccessRepository()
    policy_repo = InMemoryPolicyRepository()
    SeedBootstrap(clinic_repo, access_repo, policy_repo).load_from_file(Path("seeds/stack1_seed.json"))

    service = ClinicReferenceService(clinic_repo)
    clinic = service.get_clinic("clinic_main")
    assert clinic is not None
    assert clinic.code == "dentflow-main"
    assert len(service.list_doctors("clinic_main")) >= 1
    assert len(service.list_services("clinic_main")) >= 1


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


def test_seed_bootstrap_loads_stack1_contexts() -> None:
    clinic_repo = InMemoryClinicReferenceRepository()
    access_repo = InMemoryAccessRepository()
    policy_repo = InMemoryPolicyRepository()

    SeedBootstrap(clinic_repo, access_repo, policy_repo).load_from_file(Path("seeds/stack1_seed.json"))

    assert clinic_repo.clinics
    assert access_repo.actor_identities
    assert access_repo.telegram_bindings
    assert policy_repo.policy_sets
    assert policy_repo.policy_values
