# P0-08A4C4 — PatientMediaService foundation report

## Summary
Implemented `PatientMediaService` foundation as service-layer only over media repository contracts. No DB schema, Alembic, Telegram API, or S3/object-storage integrations were added.

## Files changed
- `app/application/patient/media.py`
- `app/application/patient/__init__.py`
- `tests/test_p0_08a4c4_patient_media_service.py`
- `docs/report/P0_08A4C4_PATIENT_MEDIA_SERVICE_REPORT.md`

## Service methods added
- `register_telegram_asset`
- `attach_media_to_owner`
- `register_and_attach_telegram_media`
- `list_owner_media`
- `set_primary_owner_media`
- `remove_owner_media_link`
- `get_patient_avatar`
- `get_product_cover`

## Telegram asset registration behavior
- Validates clinic id, Telegram file ids, media type, and non-negative `size_bytes`.
- Reuses existing asset by `telegram_file_unique_id` and upserts refined metadata.
- Creates Telegram-backed media assets with mapped fields.
- No Telegram API calls.

## Owner attach behavior
- Validates owner type, role, role-owner compatibility, visibility, sort order.
- Verifies media asset exists before attach.
- Applies default visibility by role.
- Defaults primary for `product_cover` and `patient_avatar`, false otherwise.
- Promotes primary using repository `set_primary_media` when needed.

## Role/visibility validation
Implemented allowlists and compatibility matrix for owner/role/visibility rules requested in C4.

## Primary media behavior
- `product_cover` and `patient_avatar` default to primary.
- `product_gallery`, `product_video`, `clinical_photo`, `document_attachment` default non-primary unless requested.

## Patient avatar/product cover helpers
- `get_patient_avatar` lists `patient_profile` + `patient_avatar` and returns first (primary-sorted by repository).
- `get_product_cover` lists `care_product` + `product_cover` and returns first.

## No Telegram/S3/live storage calls
Service is pure orchestration/validation and does not call Bot, Telegram API, download, boto3, S3, or object storage APIs.

## Tests run with exact commands/results
(See terminal run log in this PR; unit and regression suites executed per task checklist.)

## Grep checks
Executed required grep checks for service names, role strings, forbidden external-call terms, and migration terms.

## No Alembic / no migrations confirmation
No migration files created/modified. No schema edits done.

## Defects found/fixed
- Added explicit owner-role compatibility validation and default visibility/primary behavior.
- Added deterministic id injection support for stable unit tests.

## Carry-forward
- P0-08A4C5 service DB smoke
- P0-08M0 TradeFlow media manager audit
- P0-08M1 generic media implementation
- P0-08M2 product media admin
- P0-08M3 patient avatar upload

## GO/NO-GO for P0-08A4C5
GO for P0-08A4C5 (service DB smoke), based on service-unit completion and regression status.
