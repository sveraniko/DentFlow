from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.bootstrap import runtime as runtime_module
from app.config.settings import TelegramConfig
from app.infrastructure.db import patient_repository as patient_repo_module
from app.infrastructure.db import repositories as repo_module


class _DummyConn:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, stmt, params):
        self.calls.append((str(stmt), params))


def test_seed_rows_jsonb_values_are_json_serialized_and_none_defaults_omitted() -> None:
    conn = _DummyConn()
    payload = {
        "policy_values": [
            {
                "policy_value_id": "pv-1",
                "policy_set_id": "ps-1",
                "policy_key": "booking.reminder_offsets_minutes",
                "value_type": "json",
                "value_json": {"offsets": [60, 180]},
                "is_override": True,
                "effective_from": "2024-01-01T00:00:00+00:00",
                "effective_to": None,
            }
        ]
    }

    asyncio.run(repo_module._seed_rows(conn, payload))

    sql, params = conn.calls[0]
    assert "effective_to" not in sql
    assert params["value_json"] == json.dumps({"offsets": [60, 180]})


class _FakeBegin:
    def __init__(self, conn: _DummyConn) -> None:
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, conn: _DummyConn) -> None:
        self._conn = conn

    def begin(self):
        return _FakeBegin(self._conn)

    async def dispose(self):
        return None


def test_persist_patient_coerces_birth_date_string(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _DummyConn()
    monkeypatch.setattr(patient_repo_module, "create_engine", lambda _cfg: _FakeEngine(conn))

    repo = patient_repo_module.DbPatientRegistryRepository(db_config=object())
    patient = patient_repo_module.Patient(
        patient_id="p-1",
        clinic_id="c-1",
        patient_number="100",
        full_name_legal="John Doe",
        first_name="John",
        last_name="Doe",
        middle_name=None,
        display_name="John Doe",
        birth_date="1988-04-11",
        sex_marker=None,
        status="active",
        first_seen_at=patient_repo_module.DEFAULT_SEED_TIMESTAMP,
        last_seen_at=patient_repo_module.DEFAULT_SEED_TIMESTAMP,
    )

    asyncio.run(repo.persist_patient(patient))

    _, params = conn.calls[0]
    assert params["birth_date"] == date(1988, 4, 11)


def test_persist_preferences_serializes_contact_time_window(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _DummyConn()
    monkeypatch.setattr(patient_repo_module, "create_engine", lambda _cfg: _FakeEngine(conn))

    repo = patient_repo_module.DbPatientRegistryRepository(db_config=object())
    pref = patient_repo_module.PatientPreference(
        patient_preference_id="pp-1",
        patient_id="p-1",
        preferred_language="en",
        preferred_reminder_channel="telegram",
        allow_sms=True,
        allow_telegram=True,
        allow_call=False,
        allow_email=False,
        marketing_opt_in=False,
        contact_time_window={"from": "09:00", "to": "17:00"},
    )

    asyncio.run(repo.persist_preferences(pref))

    _, params = conn.calls[0]
    assert params["contact_time_window"] == json.dumps({"from": "09:00", "to": "17:00"})


def test_seed_stack2_passes_event_name_to_persist_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    class _FakeRepo:
        def __init__(self, db_config) -> None:
            self.db_config = db_config

        async def persist_patient(self, _model):
            return None

        async def persist_preferences(self, _pref):
            return None

        async def persist_flag(self, _flag, *, event_name: str):
            captured.append(event_name)

        async def persist_photo(self, _photo):
            return None

        async def persist_medical_summary(self, _summary):
            return None

        async def persist_external_id(self, _external):
            return None

    class _FakeService:
        def __init__(self, repository) -> None:
            self.repository = repository

        def create_patient(self, **kwargs):
            return kwargs

        async def upsert_contact_db(self, **kwargs):
            return kwargs

    monkeypatch.setattr(patient_repo_module, "DbPatientRegistryRepository", _FakeRepo)
    monkeypatch.setattr(patient_repo_module, "DbPatientRegistryService", _FakeService)

    payload = {
        "patient_flags": [
            {
                "patient_flag_id": "pf-1",
                "patient_id": "p-1",
                "flag_type": "vip",
                "flag_severity": "info",
            }
        ]
    }

    asyncio.run(patient_repo_module.seed_stack2_patients(object(), payload))

    assert captured == ["patient.flag_set"]


def test_telegram_nested_settings_load_from_env_file_and_env_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TELEGRAM_PATIENT_BOT_TOKEN=file_patient\n"
        "TELEGRAM_CLINIC_ADMIN_BOT_TOKEN=file_admin\n"
        "TELEGRAM_DOCTOR_BOT_TOKEN=file_doctor\n"
        "TELEGRAM_OWNER_BOT_TOKEN=file_owner\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    from_file = TelegramConfig()
    assert from_file.patient_bot_token == "file_patient"

    monkeypatch.setenv("TELEGRAM_PATIENT_BOT_TOKEN", "env_patient")
    from_env = TelegramConfig()
    assert from_env.patient_bot_token == "env_patient"


def test_runtime_build_dispatcher_patient_router_call_signature_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    def _strict_patient_router(
        i18n,
        booking_patient_flow_service,
        reference_service,
        *,
        reminder_actions,
        recommendation_service,
        care_commerce_service,
        recommendation_repository,
        default_locale,
        card_runtime,
        card_callback_codec,
    ):
        return object()

    monkeypatch.setattr(runtime_module, "make_patient_router", _strict_patient_router)
    monkeypatch.setattr(runtime_module, "make_admin_router", lambda *args, **kwargs: object())
    monkeypatch.setattr(runtime_module, "make_doctor_router", lambda *args, **kwargs: object())
    monkeypatch.setattr(runtime_module, "make_owner_router", lambda *args, **kwargs: object())

    class _Dispatcher:
        def include_router(self, _router):
            return None

    monkeypatch.setattr(runtime_module, "Dispatcher", _Dispatcher)

    runtime = SimpleNamespace(
        i18n=object(),
        booking_patient_flow_service=object(),
        reference_service=object(),
        reminder_action_service=object(),
        recommendation_service=object(),
        care_commerce_service=object(),
        recommendation_repository=object(),
        settings=SimpleNamespace(
            app=SimpleNamespace(default_locale="en"),
            stt=SimpleNamespace(max_voice_duration_sec=30, max_voice_file_size_bytes=1000, mode_ttl_sec=45),
        ),
        card_runtime=object(),
        card_callback_codec=object(),
        access_resolver=object(),
        search_service=object(),
        speech_to_text_service=object(),
        voice_mode_store=object(),
        admin_workdesk_service=object(),
        document_export_service=object(),
        generated_document_registry_service=object(),
        media_asset_registry_service=object(),
        care_catalog_sync_service=object(),
        google_calendar_projection_read_service=object(),
        booking_service=object(),
        booking_state_service=object(),
        booking_orchestration_service=object(),
        doctor_patient_reader=object(),
        clinical_chart_service=object(),
        owner_analytics_service=object(),
    )

    runtime_module.RuntimeRegistry.build_dispatcher(runtime)


def test_pyproject_declares_wheel_package_app() -> None:
    content = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.hatch.build.targets.wheel]" in content
    assert 'packages = ["app"]' in content
