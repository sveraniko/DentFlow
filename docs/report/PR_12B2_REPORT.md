# PR 12B-2 Report — Generated document delivery seam hardening

## What changed

- Added a bounded generated-artifact delivery seam in export application services:
  - `GeneratedArtifactDeliveryService`
  - `GeneratedArtifactDeliveryResult`
- Delivery seam now resolves generated media assets into structured outcomes:
  - `local_file` (direct Telegram document send path)
  - `unavailable` (missing/unsafe ref)
  - `unsupported_provider` (safe bounded fallback)
- Updated admin and doctor generated-document download handlers to:
  - send actual Telegram document attachments for local file delivery
  - avoid echoing internal `storage_ref` in user-facing text
  - return localized bounded messages for unavailable/unsupported delivery
- Updated admin and doctor generated-document open handlers to keep metadata-first cards while using bounded artifact hints (download available / unavailable / provider unsupported), without raw path leakage.
- Updated EN/RU locale strings for bounded open/download wording and provider-unsupported messaging.

## Exact files changed

- `app/application/export/services.py`
- `app/application/export/__init__.py`
- `app/interfaces/bots/admin/router.py`
- `app/interfaces/bots/doctor/router.py`
- `tests/test_document_registry_ui_12a4a.py`
- `locales/en.json`
- `locales/ru.json`
- `docs/report/PR_12B2_REPORT.md`

## Delivery result modeling

- `GeneratedArtifactDeliveryResult` (`mode`, optional `path`)
- `GeneratedArtifactDeliveryService.resolve(asset)` returns one of:
  - `mode="local_file"` with safe normalized local file `path`
  - `mode="unavailable"` when missing/unsafe path
  - `mode="unsupported_provider"` when provider is not direct-delivery supported

The local path resolver is defensive:
- normalizes and resolves paths
- restricts to configured generated-artifacts base directory scope
- rejects non-file or missing paths

## Tests added/updated

Updated `tests/test_document_registry_ui_12a4a.py` with focused router tests for:
- admin download sends Telegram document (no raw ref leak)
- doctor download sends Telegram document (no raw ref leak)
- admin open remains metadata card with bounded hint
- doctor open remains metadata card with bounded hint
- unavailable artifact behavior remains safe/localized
- unsupported provider behavior is safe/localized and does not leak raw ref

## Environment / execution

- No migrations were added.
- Targeted test execution was used for this PR scope.

## Explicit non-goals left for 12B-3 / 13A

- 12B-3: convergence guardrails/doc drift cleanup and worker bootstrap test seam hardening
- 13A: admin calendar mirror UI, care catalog sync operator UI, patient-facing document surfaces
- No export-generation redesign, no PDF/DOCX expansion, no new storage backend rollout in this PR
