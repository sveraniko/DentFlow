import pytest
import asyncio

pytest.importorskip("sqlalchemy")

from app.infrastructure.db import repositories


class _MappingsResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self._rows)


class _Conn:
    def __init__(self, sql_to_rows):
        self.sql_to_rows = sql_to_rows

    async def execute(self, stmt):
        sql = " ".join(str(stmt).split())
        for key, rows in self.sql_to_rows.items():
            if key in sql:
                return _MappingsResult(rows)
        raise AssertionError(f"Unexpected SQL: {sql}")


class _Ctx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Engine:
    def __init__(self, sql_to_rows):
        self.conn = _Conn(sql_to_rows)

    def connect(self):
        return _Ctx(self.conn)

    async def dispose(self):
        return None


def test_stack1_db_loaders_hydrate_with_audit_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    sql_to_rows = {
        "FROM core_reference.clinics": [
            {
                "clinic_id": "clinic_main",
                "code": "dentflow-main",
                "display_name": "DentFlow",
                "timezone": "UTC",
                "default_locale": "en",
                "status": "active",
                "created_at": "ignored",
                "updated_at": "ignored",
            }
        ],
        "FROM core_reference.branches": [
            {
                "branch_id": "b1",
                "clinic_id": "clinic_main",
                "display_name": "Main",
                "address_text": "Addr",
                "timezone": "UTC",
                "status": "active",
                "created_at": "ignored",
                "updated_at": "ignored",
            }
        ],
        "FROM core_reference.doctors": [
            {
                "doctor_id": "d1",
                "clinic_id": "clinic_main",
                "branch_id": "b1",
                "display_name": "Dr",
                "specialty_code": "gen",
                "public_booking_enabled": True,
                "status": "inactive",
                "created_at": "ignored",
                "updated_at": "ignored",
            }
        ],
        "FROM core_reference.services": [
            {
                "service_id": "s1",
                "clinic_id": "clinic_main",
                "code": "CONS",
                "title_key": "svc.cons",
                "duration_minutes": 30,
                "specialty_required": None,
                "status": "active",
                "created_at": "ignored",
                "updated_at": "ignored",
            }
        ],
        "FROM core_reference.doctor_access_codes": [
            {
                "doctor_access_code_id": "dac1",
                "clinic_id": "clinic_main",
                "doctor_id": "d1",
                "code": "1234",
                "status": "active",
                "expires_at": None,
                "max_uses": 5,
                "service_scope": ["s1"],
                "branch_scope": ["b1"],
                "created_at": "ignored",
                "updated_at": "ignored",
            }
        ],
        "FROM access_identity.actor_identities": [
            {
                "actor_id": "a1",
                "actor_type": "staff",
                "display_name": "Admin",
                "status": "active",
                "locale": "en",
                "created_at": "ignored",
                "updated_at": "ignored",
            }
        ],
        "FROM access_identity.telegram_bindings": [
            {
                "telegram_binding_id": "tb1",
                "actor_id": "a1",
                "telegram_user_id": 111,
                "telegram_username": "admin",
                "first_seen_at": None,
                "last_seen_at": None,
                "is_primary": True,
                "is_active": True,
                "created_at": "ignored",
            }
        ],
        "FROM access_identity.staff_members": [
            {
                "staff_id": "st1",
                "actor_id": "a1",
                "clinic_id": "clinic_main",
                "full_name": "Admin User",
                "display_name": "Admin",
                "staff_status": "active",
                "primary_branch_id": "b1",
                "created_at": "ignored",
                "updated_at": "ignored",
            }
        ],
        "FROM access_identity.clinic_role_assignments": [
            {
                "role_assignment_id": "ra1",
                "staff_id": "st1",
                "clinic_id": "clinic_main",
                "role_code": "admin",
                "branch_id": None,
                "scope_type": "clinic",
                "scope_ref": None,
                "granted_by_actor_id": None,
                "granted_at": None,
                "revoked_at": None,
                "is_active": True,
                "created_at": "ignored",
            }
        ],
        "FROM policy_config.policy_sets": [
            {
                "policy_set_id": "ps1",
                "policy_family": "booking_policy",
                "scope_type": "clinic",
                "scope_ref": "clinic_main",
                "status": "active",
                "version": 1,
                "created_at": "ignored",
                "updated_at": "ignored",
            }
        ],
        "FROM policy_config.policy_values": [
            {
                "policy_value_id": "pv1",
                "policy_set_id": "ps1",
                "policy_key": "booking.enabled",
                "value_type": "bool",
                "value_json": True,
                "is_override": False,
                "effective_from": None,
                "effective_to": None,
                "created_at": "ignored",
            }
        ],
        "FROM policy_config.feature_flags": [
            {
                "feature_flag_id": "ff1",
                "scope_type": "clinic",
                "scope_ref": "clinic_main",
                "flag_key": "owner.ai_enabled",
                "enabled": False,
                "reason": None,
                "created_at": "ignored",
            }
        ],
    }

    monkeypatch.setattr(repositories, "create_engine", lambda _: _Engine(sql_to_rows))

    clinic_repo = asyncio.run(repositories.DbClinicReferenceRepository.load(object()))
    access_repo = asyncio.run(repositories.DbAccessRepository.load(object()))
    policy_repo = asyncio.run(repositories.DbPolicyRepository.load(object()))

    assert clinic_repo.clinics["clinic_main"].status.value == "active"
    assert clinic_repo.doctors["d1"].status.value == "inactive"
    assert access_repo.actor_identities["a1"].actor_type.value == "staff"
    assert access_repo.role_assignments["ra1"].role_code.value == "admin"
    assert policy_repo.policy_sets["ps1"].status.value == "active"
    assert policy_repo.feature_flags[0].flag_key == "owner.ai_enabled"
