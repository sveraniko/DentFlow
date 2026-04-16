# DentFlow Access and Identity Model

> Canonical identity, staff, role-binding, and authorization model for DentFlow.

## 1. Purpose

This document defines how DentFlow models:

- human actors;
- staff membership;
- clinic roles;
- Telegram bindings;
- privileged actions;
- service identities.

It exists because “we know who is who from chat id” is not an access model.
It is a shortcut to future pain.

---

## 2. Core principles

## 2.1 Telegram identity is not enough

Telegram identity may help identify a chat session.
It does not automatically determine:
- clinic membership;
- doctor role;
- owner role;
- export privilege;
- branch access scope.

## 2.2 Staff identity and role binding are explicit

Operational access must come from explicit role bindings that can be:
- granted;
- changed;
- revoked;
- audited.

## 2.3 Least privilege by default

A role sees only what it needs.
“Owner” is not a magical excuse for unlimited raw clinical browsing.

## 2.4 Access model must survive staff change

If a staff member leaves:
- access should be revocable fast;
- role bindings should disappear cleanly;
- the system should not rely on hardcoded chat IDs in handlers.

---

## 3. Actor model

## 3.1 Actor categories

DentFlow should distinguish these categories:

- patient actor
- staff actor
- service actor

### Patient actor
A patient interacting with the clinic.

### Staff actor
A human with clinic-side responsibilities, such as:
- admin
- doctor
- owner
- manager
- support role if needed later

### Service actor
A system process, such as:
- reminder worker
- sync worker
- export worker
- projection worker

---

## 4. Core entities

## 4.1 `ActorIdentity`

A canonical identity record for a human or service principal.

Suggested fields:
- `actor_id`
- `actor_type` (`patient`, `staff`, `service`)
- `display_name`
- `status`
- `created_at`
- `updated_at`

## 4.2 `TelegramBinding`

Binds an actor to Telegram.

Suggested fields:
- `telegram_binding_id`
- `actor_id`
- `telegram_user_id`
- `telegram_username` (nullable)
- `first_seen_at`
- `last_seen_at`
- `is_primary`
- `is_active`

### Notes
- one actor may have zero or one primary Telegram binding for most flows;
- do not use Telegram binding as replacement for actor identity.

## 4.3 `StaffMember`

Clinic-side human identity.

Suggested fields:
- `staff_id`
- `actor_id`
- `clinic_id`
- `full_name`
- `display_name`
- `staff_status`
- `primary_branch_id` (nullable)
- `created_at`
- `updated_at`

## 4.4 `ClinicRoleAssignment`

Explicit role binding.

Suggested fields:
- `role_assignment_id`
- `staff_id`
- `clinic_id`
- `branch_id` (nullable)
- `role_code`
- `scope_type`
- `scope_ref`
- `granted_at`
- `granted_by_actor_id`
- `revoked_at` (nullable)
- `is_active`

### Role examples
- `admin`
- `doctor`
- `owner`
- `manager`
- `export_operator`
- `analytics_viewer`

## 4.5 `DoctorProfile`

Doctor is a role-bearing staff specialization tied to clinic reference.

Suggested fields:
- `doctor_id`
- `staff_id`
- `clinic_id`
- `branch_id` (nullable)
- `specialty_code`
- `active_for_booking`
- `active_for_clinical_work`

## 4.6 `OwnerProfile`

Owner/management specialization.

Suggested fields:
- `owner_profile_id`
- `staff_id`
- `clinic_id`
- `owner_scope_kind`
- `analytics_scope`
- `cross_branch_enabled`

## 4.7 `ServicePrincipal`

System/service identity.

Suggested fields:
- `service_principal_id`
- `principal_code`
- `description`
- `status`

---

## 5. Authorization model

## 5.1 Authorization inputs

A privileged action should evaluate at least:

- actor identity
- clinic membership
- active role assignment
- branch/scope if relevant
- action code
- target entity scope

## 5.2 Authorization outputs

The system should answer:
- allowed
- denied
- denied with reason
- allowed under limited scope

## 5.3 Role scope examples

### Admin
May operate:
- booking control
- patient operational profile
- reminder exceptions
- care pickup handling

### Doctor
May operate:
- own/current patient queue
- chart and encounter actions
- recommendation issuance

### Owner
May operate:
- owner analytics
- owner digests
- selected exports if explicitly allowed
- clinic-level settings if explicitly allowed

### Export operator
May generate/export documents but is not automatically owner.

---

## 6. Privileged actions

These actions should be treated as privilege-sensitive:

- export patient document
- mass data export
- connect integration credentials
- run manual sync
- grant/revoke roles
- view owner analytics
- view cross-branch metrics
- delete or hard-revoke records where supported
- generate AI insights over owner data if restricted

Suggested entity:
### `PrivilegedActionPolicy`
- `policy_id`
- `action_code`
- `role_code`
- `scope_kind`
- `requires_explicit_grant`
- `enabled`

---

## 7. Role matrix guidance

| Capability | Patient | Admin | Doctor | Owner |
|---|---|---|---|---|
| Book / manage own booking | yes | assisted | limited | no |
| Search broad patient list | no | yes | scoped | limited, policy-based |
| Open clinical encounter | no | limited summary only | yes | no by default |
| Generate patient export | own limited docs only | policy-based | policy-based | policy-based |
| View owner metrics | no | no by default | no by default | yes |
| Manage reminder failures | no | yes | no | view exceptions only |
| Issue clinical recommendation | no | limited/admin-issued | yes | no |
| Fulfill care pickup | no | yes | no | view metrics only |

---

## 8. Clinic and branch scope

## 8.1 Clinic scope is mandatory
All role assignments are clinic-scoped.

## 8.2 Branch scope is optional
Where branches exist, assignments may also be limited to branch scope.

## 8.3 Cross-branch owner scope
If enabled, owner scope should be explicit.
Never assume cross-branch visibility automatically.

---

## 9. Telegram operational rules

## 9.1 Role surfaces must validate actor binding
A bot should not expose admin/doctor/owner surfaces until actor binding and role eligibility are validated.

## 9.2 Rebinding must be controlled
If a staff member changes Telegram account, rebinding should be explicit and auditable.

## 9.3 Lost/stale bindings
Bindings can be disabled without deleting underlying staff history.

---

## 10. Service identities

Workers and adapters should use service identities or service credentials.
They should not impersonate random human actors.

Examples:
- `svc_reminder_worker`
- `svc_projection_worker`
- `svc_sheets_sync`
- `svc_export_worker`

---

## 11. Interaction with security and data model

This document defines identity and authorization structure.
It works together with:
- `docs/30_data_model.md`
- `docs/85_security_and_privacy.md`

It should influence:
- staff tables
- actor metadata
- audit trails
- access checks in application services

---

## 12. Summary

DentFlow access is based on:
- explicit actor identity;
- explicit staff membership;
- explicit role assignment;
- clinic/branch scope;
- privileged action checks;
- controlled Telegram bindings.

This prevents the system from degenerating into “if chat id equals X then owner.”
That kind of improvisation is fun only until the first access incident.
