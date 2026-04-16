# DentFlow Policy and Configuration Model

> Canonical model for clinic, branch, doctor, reminder, AI, export, and integration settings.

## 1. Purpose

This document defines where DentFlow settings live and how they are resolved.

It exists to prevent the classic disease where configuration ends up split between:
- environment variables;
- hardcoded constants;
- random tables;
- forgotten handler branches;
- “temporary” feature flags that become permanent architecture.

---

## 2. Core principles

## 2.1 Configuration is modeled, not improvised

Operational behavior must come from explicit policy/config models.

## 2.2 Environment is not business policy

Environment variables are for:
- secrets
- infrastructure connectivity
- deployment toggles

They are not the right home for:
- doctor public-booking rules
- reminder timings
- export permissions
- per-clinic feature behavior

## 2.3 Policy resolution must be predictable

When multiple scopes exist, precedence must be explicit.

Recommended policy precedence:
1. explicit entity-level override
2. branch-level policy
3. clinic-level policy
4. product default

## 2.4 Feature toggles must be explainable

If a feature is on or off, DentFlow should be able to explain why.

---

## 3. Policy scopes

DentFlow should support these scopes:

- product default
- clinic
- branch
- doctor
- role surface
- integration target

Not every policy uses every scope.

---

## 4. Core policy families

## 4.1 Clinic policy

Examples:
- default locale
- supported locales
- booking enabled
- waitlist enabled
- care-commerce enabled
- document export enabled
- owner AI enabled
- Sheets sync enabled

## 4.2 Branch policy

Examples:
- branch booking enabled
- reminder templates override
- pickup availability
- branch-specific working hours
- branch export template preference

## 4.3 Doctor booking policy

Examples:
- public booking enabled
- premium protected
- repeat-patient priority
- code-only booking
- urgent-capable
- public quota settings
- service restrictions

## 4.4 Reminder policy

Examples:
- confirmation required yes/no
- confirmation lead time
- reminder schedule offsets
- action-required reminder enabled
- acknowledgement deadline
- fallback channel policy
- escalation after non-response

## 4.5 Search policy

Examples:
- voice search enabled
- photo previews enabled
- fuzzy threshold tuning
- transliteration enabled
- owner patient-level drill-down restrictions

## 4.6 Care-commerce policy

Examples:
- reserve/pickup enabled
- pay-at-pickup enabled
- recommendation-to-product auto-linking enabled
- category visibility
- doctor recommendation constraints

## 4.7 Export/document policy

Examples:
- 043 export enabled
- editable export enabled
- who can export
- branch-specific templates
- signature workflow flags

## 4.8 Owner analytics policy

Examples:
- digest cadence
- anomaly thresholds
- branch aggregation mode
- doctor metrics visibility
- AI explanation enablement

## 4.9 Integration policy

Examples:
- Sheets sync direction
- sync frequency
- allowed entities
- adapter enable flags
- conflict resolution mode

---

## 5. Suggested entities

## 5.1 `PolicySet`
Top-level policy group.

Suggested fields:
- `policy_set_id`
- `policy_family`
- `scope_type`
- `scope_ref`
- `status`
- `version`
- `created_at`
- `updated_at`

## 5.2 `PolicyValue`
Individual policy value.

Suggested fields:
- `policy_value_id`
- `policy_set_id`
- `policy_key`
- `value_type`
- `value_json`
- `is_override`
- `effective_from` (nullable)
- `effective_to` (nullable)

## 5.3 `FeatureFlag`
Useful for controlled rollout.

Suggested fields:
- `feature_flag_id`
- `scope_type`
- `scope_ref`
- `flag_key`
- `enabled`
- `reason`
- `created_at`

---

## 6. Reminder policy: explicit stance

Reminder behavior is important enough to deserve explicit configuration.

Suggested reminder policy keys:
- `booking.confirmation_required`
- `booking.confirmation_offset_hours`
- `booking.reminder_offsets_hours`
- `booking.same_day_reminder_enabled`
- `booking.action_required_reminders_enabled`
- `booking.allow_on_my_way_ack`
- `booking.non_response_escalation_enabled`
- `booking.non_response_escalation_after_minutes`
- `booking.repeat_no_show_confirmation_mode`

This makes reminder behavior configurable rather than hardcoded folklore.

---

## 7. Single-clinic deployment and policy

Because DentFlow is single-clinic per deployment by default:
- clinic policy is the main business-policy root;
- branch overrides are optional;
- doctor-level booking overrides remain allowed;
- cross-clinic owner federation policy belongs to integration/owner scope, not booking core.

---

## 8. Configuration groups vs policy groups

## 8.1 Environment/infrastructure config
Examples:
- DB DSN
- bot tokens
- storage credentials
- AI provider key
- search endpoint

Lives in config/env management.

## 8.2 Runtime business policy
Examples:
- confirmation required
- doctor public-booking rules
- export availability
- AI enablement by clinic

Lives in policy/config model.

---

## 9. CODEX rules

CODEX must not:
- hardcode doctor booking rules inside handlers;
- store business policy only in `.env`;
- create random ad hoc settings tables by subsystem;
- bypass documented precedence rules.

If a feature needs settings, CODEX should extend this model rather than inventing a private policy cult.

---

## 10. Summary

DentFlow policy/configuration must be:

- explicit;
- scoped;
- precedence-aware;
- split cleanly from infrastructure secrets;
- rich enough to control booking, reminders, exports, AI, and integrations;
- centralized enough that later feature growth does not become a settings scavenger hunt.
