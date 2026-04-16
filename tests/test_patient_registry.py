from app.application.patient import InMemoryPatientRegistryRepository, PatientRegistryService, normalize_contact_value


def _service() -> PatientRegistryService:
    return PatientRegistryService(InMemoryPatientRegistryRepository())


def test_patient_create_update_and_resolution() -> None:
    service = _service()
    patient = service.create_patient(
        clinic_id="clinic_main",
        patient_id="pat_1",
        first_name="Ivan",
        last_name="Ivanov",
        full_name_legal="Ivan Ivanov",
        display_name="Ivan Ivanov",
    )
    updated = service.update_patient(patient.patient_id, display_name="Иван Иванов")
    assert updated.display_name == "Иван Иванов"

    service.upsert_contact(
        patient_id=patient.patient_id,
        contact_type="phone",
        contact_value="+7 (900) 111-22-33",
        is_primary=True,
        is_verified=True,
    )
    found = service.find_by_exact_contact(contact_type="phone", contact_value="79001112233")
    assert found is not None
    assert found.patient_id == patient.patient_id


def test_preferences_flags_photo_external_and_summary() -> None:
    service = _service()
    patient = service.create_patient(
        clinic_id="clinic_main",
        patient_id="pat_2",
        first_name="Elena",
        last_name="Ivanova",
        full_name_legal="Elena Ivanova",
        display_name="Elena Ivanova",
    )

    preference = service.upsert_preferences(patient_id=patient.patient_id, preferred_language="en", allow_telegram=True)
    assert preference.preferred_language == "en"

    flag = service.add_flag(patient_id=patient.patient_id, flag_type="allergy", flag_severity="high")
    assert len(service.active_flags(patient.patient_id)) == 1
    service.deactivate_flag(flag.patient_flag_id)
    assert len(service.active_flags(patient.patient_id)) == 0

    photo1 = service.add_photo(patient_id=patient.patient_id, source_type="upload", is_primary=False)
    photo2 = service.add_photo(patient_id=patient.patient_id, source_type="upload", is_primary=False)
    service.set_primary_photo(photo2.patient_photo_id)
    assert service.repository.photos[photo2.patient_photo_id].is_primary
    assert not service.repository.photos[photo1.patient_photo_id].is_primary

    summary = service.upsert_medical_summary(patient_id=patient.patient_id, allergy_summary="penicillin")
    assert summary.allergy_summary == "penicillin"

    service.upsert_external_id(patient_id=patient.patient_id, external_system="legacy", external_id="X-1")
    found = service.find_by_external_id(external_system="legacy", external_id="X-1")
    assert found and found.patient_id == patient.patient_id


def test_contact_normalization() -> None:
    assert normalize_contact_value("phone", "+7 (901) 222-33-44") == "79012223344"
    assert normalize_contact_value("email", " User@Mail.COM ") == "user@mail.com"
