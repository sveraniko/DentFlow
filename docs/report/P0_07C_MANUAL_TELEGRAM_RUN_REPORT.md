# P0-07C Manual Telegram Pre-Live Run — Final Report

**Date:** 2026-04-29
**Environment:** local pre-live (NOT production)

---

## 1. Summary

P0-07C manual Telegram pre-live run executed against local infrastructure.
All automated DB-backed gates passed. All four bots started successfully in polling mode.
Manual Telegram checklist was executed — **9 bugs found and fixed** during the session.

---

## 2. Automated Gates

| Gate | Result |
|------|--------|
| test_p0_07a_patient_read_surfaces_pre_live | PASS |
| test_p0_07b1_booking_mutation_pre_live | PASS |
| test_p0_07b2_recommendation_care_mutation_pre_live | PASS |
| test_p0_07b3_consolidated_mutation_pre_live_gate | PASS |
| test_p0_06d2d2_db_backed_application_reads | PASS |
| Regression (care, recommendation, booking) | 358 passed, 0 failed |
| Compile check | PASS |

---

## 3. Bugs Found & Fixed

| # | Bug | Severity | Status |
|---|-----|----------|--------|
| 1 | Redis runtime adapter returned `None` for dev environment — panel state was not tracked, all buttons showed "Карточка устарела" | Blocker | Fixed |
| 2 | Care categories panel missing Home/Back navigation button | Blocker | Fixed |
| 3 | Back button in doctor picker threw `TelegramBadRequest: message is not modified` and froze | Blocker | Fixed |
| 4 | Cross-family panel transition (Home → Care) blocked by stale `PATIENT_CATALOG` panel state — "Карточка устарела" | Blocker | Fixed |
| 5 | Reply keyboard ("Поделиться контактом" / "Главное меню") leaked into other flows after leaving booking contact step | Major | Fixed |
| 6 | Pressing "Главное меню" from reply keyboard left orphan panel messages and user's text message in chat | Major | Fixed |
| 7 | Duplicate Home panels appeared after reply keyboard → Home transition (old panel not deleted when new message created) | Major | Fixed |
| 8 | `branch_id` not propagated from selected availability slot to booking session — booking card showed "Филиал: не указан" | Major | Fixed |
| 9 | Returning to Home from any panel did not invalidate stale panel states from both families — could cause stale card on re-entry | Minor | Fixed |

---

## 4. Blockers Found

**No remaining blockers.** All 4 blockers discovered during manual testing were fixed and verified.

---

## 5. Notes / Non-Blockers

| # | Item | Impact |
|---|------|--------|
| 1 | Reminder toggle shows "Включены" but no button to enable/disable — feature not implemented | Low — cosmetic, no functional impact |
| 2 | Patient personal data (name, surname) not collected during booking — by design, identity resolved via phone matching to patient registry | None — working as designed |
| 3 | Google Calendar projection disabled for this run | None — expected for local pre-live |
| 4 | Google Sheets sync disabled for this run | None — expected for local pre-live |

---

## 6. Files Modified

| File | Changes |
|------|---------|
| `app/infrastructure/cache/redis_runtime.py` | Fixed Redis adapter factory to work in dev environment |
| `app/interfaces/bots/patient/router.py` | Added Home button to care categories, TelegramBadRequest handling, panel invalidation on cross-family transitions, reply keyboard chat cleanup, orphan panel deletion |
| `app/interfaces/cards/runtime_state.py` | Added `invalidate_panel` method to `CardRuntimeCoordinator` |
| `app/application/booking/orchestration.py` | Propagate `branch_id` from slot to session during slot selection |

---

## 7. Verdict

### Automated Pre-Live Gates: PASS

All mandatory DB-backed tests passed. All regression tests passed. All 4 bots start and poll without errors.

### Manual Telegram Flows: PASS (with fixes applied)

9 bugs discovered and resolved during manual testing. No remaining blockers.

### Recommendation: **GO for controlled live patient demo**
