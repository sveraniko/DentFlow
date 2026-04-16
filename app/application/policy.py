from __future__ import annotations

from dataclasses import dataclass

from app.domain.policy_config.models import DEFAULT_POLICY_VALUES, FeatureFlag, PolicySet, PolicyValue


class InMemoryPolicyRepository:
    def __init__(self) -> None:
        self.policy_sets: dict[str, PolicySet] = {}
        self.policy_values: list[PolicyValue] = []
        self.feature_flags: list[FeatureFlag] = []

    def upsert_policy_set(self, policy_set: PolicySet) -> None:
        self.policy_sets[policy_set.policy_set_id] = policy_set

    def add_policy_value(self, policy_value: PolicyValue) -> None:
        self.policy_values.append(policy_value)

    def add_feature_flag(self, feature_flag: FeatureFlag) -> None:
        self.feature_flags.append(feature_flag)


@dataclass(slots=True)
class PolicyResolver:
    repository: InMemoryPolicyRepository

    def resolve_policy(
        self,
        policy_key: str,
        *,
        clinic_id: str,
        branch_id: str | None = None,
        entity_scope: tuple[str, str] | None = None,
    ) -> object:
        precedence: list[tuple[str, str]] = []
        if entity_scope:
            precedence.append(entity_scope)
        if branch_id:
            precedence.append(("branch", branch_id))
        precedence.append(("clinic", clinic_id))

        for scope_type, scope_ref in precedence:
            matched = self._find_policy_value(scope_type=scope_type, scope_ref=scope_ref, policy_key=policy_key)
            if matched is not None:
                return matched
        return DEFAULT_POLICY_VALUES.get(policy_key)

    def is_feature_enabled(self, flag_key: str, *, clinic_id: str, branch_id: str | None = None) -> bool:
        for scope_type, scope_ref in (("branch", branch_id), ("clinic", clinic_id)):
            if not scope_ref:
                continue
            for flag in self.repository.feature_flags:
                if flag.scope_type == scope_type and flag.scope_ref == scope_ref and flag.flag_key == flag_key:
                    return flag.enabled
        return False

    def _find_policy_value(self, *, scope_type: str, scope_ref: str, policy_key: str) -> object | None:
        for policy_set in self.repository.policy_sets.values():
            if policy_set.scope_type != scope_type or policy_set.scope_ref != scope_ref:
                continue
            for value in self.repository.policy_values:
                if value.policy_set_id == policy_set.policy_set_id and value.policy_key == policy_key:
                    return value.value_json
        return None
