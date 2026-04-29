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

## Architecture reference
- Primary architecture baseline: `docs/74_patient_profile_family_media_architecture.md`.
- Media decision: define `MediaAsset`/`MediaLink` abstraction now, defer implementation.
- Patient avatar policy: optional, softly prompted, never forced during quick booking.
- Product media admin flow (`+ Медиа`, cover/gallery/video roles) is planned for future P0-08M stages and is not implemented now.

## Proposed P0-08 delivery stack
- **P0-08A2**: DB/service gap audit and migration planning (no implementation in A1).
- **P0-08B**: self profile wizard (minimal patient-owned fields).
- **P0-08C**: family/dependents management.
- **P0-08D**: booking patient selector (self vs dependent).
- **P0-08E**: notification settings surface and channel preferences.
- **P0-08F**: branch preference surface and defaulting rules.
- **P0-08G**: documents/pre-visit questionnaire bridge.
- **P0-08M0**: TradeFlow media manager audit.
- **P0-08M1+**: DentFlow media service/product media/patient avatar implementation.

## Document generation note
- `docs/export` flow already exists and depends on patient profile data completeness.
- Profile fields required for document generation must be collected via profile completion flow.
- Do **not** force full document-grade field collection into quick booking.
