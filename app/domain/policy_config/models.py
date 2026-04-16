from dataclasses import dataclass, field


@dataclass(slots=True)
class ClinicPolicy:
    clinic_id: str
    default_locale: str = "ru"
    reminder_policy_key: str = "default"
    feature_flags: dict[str, bool] = field(default_factory=dict)
    role_surface_toggles: dict[str, bool] = field(default_factory=dict)
