# PR_PAT_A7_2A Report

## What changed
- Added a bounded proactive Telegram delivery bridge for newly issued patient-facing recommendations.
- Introduced `PatientRecommendationDeliveryService.deliver_patient_recommendation_if_possible(...)` with explicit bounded outcomes:
  - `delivered`
  - `skipped_no_binding`
  - `skipped_ambiguous_binding`
  - `skipped_unavailable`
  - `failed_safe`
- Hooked proactive delivery at recommendation issuance seams in doctor operations:
  - manual doctor recommendation issue
  - auto-generated booking-completion aftercare issue
- Added a tiny forward trusted binding lookup on recommendation repository to resolve Telegram targets by patient conservatively.
- Added an aiogram sender dedicated to proactive recommendation message delivery with one canonical CTA callback.
- Added localized proactive delivery copy (EN/RU).

## Exact files changed
- `app/application/recommendation/services.py`
- `app/application/recommendation/__init__.py`
- `app/application/doctor/operations.py`
- `app/interfaces/bots/doctor/router.py`
- `app/bootstrap/runtime.py`
- `app/infrastructure/db/recommendation_repository.py`
- `app/infrastructure/communication/telegram_delivery.py`
- `app/infrastructure/communication/__init__.py`
- `locales/en.json`
- `locales/ru.json`
- `tests/test_recommendation_stack10a.py`
- `docs/report/PR_PAT_A7_2A_REPORT.md`

## Where the proactive delivery trigger is attached
- `DoctorOperationsService.issue_recommendation(...)` immediately after recommendation transitions to `issued`.
- `DoctorOperationsService._create_completion_aftercare(...)` immediately after booking-triggered aftercare transitions to `issued`.

This keeps triggering narrow and aligned to issuance semantics only (not list/read/edit operations).

## How trusted patient Telegram binding is resolved
- Added `DbRecommendationRepository.find_telegram_user_ids_by_patient(clinic_id, patient_id)`.
- Delivery service sanitizes and deduplicates numeric Telegram IDs and only sends when exactly one trusted target exists.
- No heuristic/best-guess multi-match behavior is used.

## How safe skip/failure works
- If sender/binding reader is unavailable: `skipped_unavailable`.
- If no trusted binding rows: `skipped_no_binding`.
- If multiple trusted Telegram IDs resolve: `skipped_ambiguous_binding`.
- If resolver/sender throws: `failed_safe`.
- Recommendation issuance path always continues; delivery never crashes issuance.

## Canonical open-path reuse
- Proactive CTA uses callback data `prec:open:<recommendation_id>`.
- No new viewer was introduced and no raw `/recommendation_open <id>` command is used as primary proactive UX.

## Tests added/updated
Updated `tests/test_recommendation_stack10a.py` with focused assertions:
1. proactive delivery succeeds with trusted binding and uses canonical callback path (`prec:open:*`),
2. no trusted binding safely skips delivery without send attempt,
3. doctor issuance still succeeds when proactive delivery fails safe.

## Environment / execution notes
- Targeted recommendation stack tests were executed in this environment.
- No migrations were created.

## Explicit non-goals intentionally left for PAT-A7-2B and PAT-A7-3
- No retry scheduler or broad notification framework.
- No patient-facing PDF/document delivery.
- No recommendation engine redesign.
- No reminder engine redesign.
- No care-commerce redesign.
- No admin/doctor/owner flow redesign beyond issuance trigger integration.
- No migrations.
