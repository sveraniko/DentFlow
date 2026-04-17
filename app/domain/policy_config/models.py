from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PolicyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass(slots=True, frozen=True)
class PolicySet:
    policy_set_id: str
    policy_family: str
    scope_type: str
    scope_ref: str
    status: PolicyStatus = PolicyStatus.ACTIVE
    version: int = 1


@dataclass(slots=True, frozen=True)
class PolicyValue:
    policy_value_id: str
    policy_set_id: str
    policy_key: str
    value_type: str
    value_json: object
    is_override: bool = False


@dataclass(slots=True, frozen=True)
class FeatureFlag:
    feature_flag_id: str
    scope_type: str
    scope_ref: str
    flag_key: str
    enabled: bool
    reason: str | None = None


DEFAULT_POLICY_VALUES: dict[str, object] = {
    "clinic.default_locale": "ru",
    "clinic.supported_locales": ["ru", "en"],
    "booking.enabled": True,
    "booking.waitlist_enabled": False,
    "booking.confirmation_required": True,
    "booking.confirmation_offset_hours": 24,
    "booking.reminder_offsets_hours": [24, 2],
    "booking.action_required_reminders_enabled": True,
    "booking.allow_on_my_way_ack": True,
    "booking.non_response_escalation_enabled": False,
    "booking.non_response_escalation_after_minutes": 30,
    "communication.reminder_retry_enabled": True,
    "communication.reminder_retry_max_attempts": 3,
    "communication.reminder_retry_delay_minutes": 5,
    "communication.reminder_stale_queued_after_minutes": 15,
    "care.enabled": False,
    "export.form_043_enabled": False,
    "owner.ai_enabled": False,
}
