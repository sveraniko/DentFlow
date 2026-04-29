# P0-08 Patient Profile / Family Scope Proposal

Date: 2026-04-29

## Current state
- Quick booking currently asks only for phone/contact sharing.
- Patient registry and related persistence tables already exist and are used for matching.
- Patient-facing profile/family cabinet UI is currently absent.
- Notification settings UI is currently absent.
- Branch preference UI is currently absent.

## Product decision
- Keep quick booking short and conversion-oriented.
- Ask FIO only when phone/Telegram identity does not resolve to an existing patient safely.
- Add optional profile completion after booking confirmation.
- Add dedicated `Profile and family` cabinet for ongoing self-service data management.

## Proposed P0-08 delivery stack
- **P0-08A**: profile/family model alignment and service contracts.
- **P0-08B**: self profile wizard (minimal patient-owned fields).
- **P0-08C**: family/dependents management.
- **P0-08D**: booking patient selector (self vs dependent).
- **P0-08E**: notification settings surface and channel preferences.
- **P0-08F**: branch preference surface and defaulting rules.
- **P0-08G**: documents/pre-visit questionnaire bridge.

## Document generation note
- `docs/export` flow already exists and depends on patient profile data completeness.
- Profile fields required for document generation must be collected via profile completion flow.
- Do **not** force full document-grade field collection into quick booking.
