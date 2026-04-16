from enum import StrEnum


class Role(StrEnum):
    PATIENT = "patient"
    CLINIC_ADMIN = "clinic_admin"
    DOCTOR = "doctor"
    OWNER = "owner"
    SERVICE = "service"
