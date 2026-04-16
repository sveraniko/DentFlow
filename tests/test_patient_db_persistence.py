import pytest
import asyncio

pytest.importorskip("sqlalchemy")

from app.infrastructure.db import patient_repository


class _Result:
    def mappings(self):
        return self

    def first(self):
        return None


class _Conn:
    def __init__(self):
        self.calls: list[tuple[str, dict | None]] = []

    async def execute(self, stmt, params=None):
        self.calls.append((" ".join(str(stmt).split()), params))
        return _Result()


class _Ctx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Engine:
    def __init__(self):
        self.conn = _Conn()

    def begin(self):
        return _Ctx(self.conn)

    def connect(self):
        return _Ctx(self.conn)

    async def dispose(self):
        return None


def test_db_patient_subentity_methods_persist(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine()
    monkeypatch.setattr(patient_repository, "create_engine", lambda _: engine)

    service = patient_repository.DbPatientRegistryService(patient_repository.DbPatientRegistryRepository(object()))
    async def _run() -> tuple[object, object]:
        patient = await service.create_patient_db(
            clinic_id="clinic_main",
            patient_id="pat_1",
            first_name="Ivan",
            last_name="Ivanov",
            full_name_legal="Ivan Ivanov",
            display_name="Ivan Ivanov",
        )
        await service.upsert_preferences_db(patient_id=patient.patient_id, preferred_language="en", allow_telegram=True)

        flag = await service.add_flag_db(patient_id=patient.patient_id, flag_type="allergy", flag_severity="high")
        await service.deactivate_flag_db(flag.patient_flag_id)

        photo1 = await service.add_photo_db(patient_id=patient.patient_id, source_type="upload", is_primary=True)
        photo2 = await service.add_photo_db(patient_id=patient.patient_id, source_type="camera", is_primary=True)
        await service.set_primary_photo_db(photo2.patient_photo_id)

        await service.upsert_medical_summary_db(patient_id=patient.patient_id, allergy_summary="none")
        await service.upsert_external_id_db(patient_id=patient.patient_id, external_system="legacy", external_id="X-1")
        return patient, (photo1, photo2)

    patient, photos = asyncio.run(_run())
    photo1, photo2 = photos

    sql_calls = "\n".join(sql for sql, _ in engine.conn.calls)
    assert "INSERT INTO core_patient.patient_preferences" in sql_calls
    assert "INSERT INTO core_patient.patient_flags" in sql_calls
    assert "INSERT INTO core_patient.patient_photos" in sql_calls
    assert "UPDATE core_patient.patient_photos SET is_primary=FALSE" in sql_calls
    assert "INSERT INTO core_patient.patient_medical_summaries" in sql_calls
    assert "INSERT INTO core_patient.patient_external_ids" in sql_calls

    primary_photos = [p for p in service.repository.photos.values() if p.patient_id == patient.patient_id and p.is_primary]
    assert len(primary_photos) == 1
    assert primary_photos[0].patient_photo_id == photo2.patient_photo_id

    assert service.get_preferences(patient.patient_id) is not None
    assert len(service.active_flags(patient.patient_id)) == 0
    assert service.get_medical_summary(patient.patient_id) is not None
    assert len(service.list_external_ids(patient.patient_id)) == 1
    assert photo1.patient_photo_id != photo2.patient_photo_id
