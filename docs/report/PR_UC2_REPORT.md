# PR UC-2 Report: Product / Patient / Doctor Card Profiles

## 1. Objective
Implement first real business card profiles on the shared unified card shell: product, patient, and doctor cards with compact/expanded modes, role-safe actions, source-aware behavior, and product media baseline.

## 2. Docs Read
1. README.md
2. docs/18_development_rules_and_baseline.md
3. docs/10_architecture.md
4. docs/12_repo_structure_and_code_map.md
5. docs/15_ui_ux_and_product_rules.md
6. docs/17_localization_and_i18n.md
7. docs/16_unified_card_system.md
8. docs/16-1_card_profiles.md
9. docs/16-2_card_callback_contract.md
10. docs/16-3_card_media_and_navigation_rules.md
11. docs/16-4_booking_card_profile.md
12. docs/22_access_and_identity_model.md
13. docs/23_policy_and_configuration_model.md
14. docs/40_search_model.md
15. docs/60_care_commerce.md
16. docs/shop/00_shop_readme.md
17. docs/shop/61_care_catalog_model.md
18. docs/shop/63_recommendation_to_product_engine.md
19. docs/shop/64_care_patient_catalog_and_flow.md
20. docs/shop/66_care_stock_and_pickup_semantics.md
21. docs/shop/67_care_media_and_content_rules.md
22. docs/68_admin_reception_workdesk.md
23. docs/69_google_calendar_schedule_projection.md
24. docs/report/PR_UC1_REPORT.md
25. docs/report/PR_UC1A_REPORT.md

## 3. Scope Implemented
- Added product profile-rich adapter behavior in compact and expanded modes.
- Added patient profile adapter with role-safe rendering and bounded expanded context.
- Added doctor profile adapter with operational compact/expanded payload and actions.
- Added profile-specific card actions in shared action enum.
- Extended UC card tests to cover product/patient/doctor profile behavior, source-aware variation, media-safe actions, and stale/context safety through profile flow.

## 4. Product Card Strategy
- Compact mode includes title, short label (if present), price, availability, branch hint (if present), and recommendation badge when source is recommendation detail.
- Expanded mode adds localized description/usage/category and source-aware secondary line:
  - recommendation rationale for recommendation context
  - category-origin context for category context
- Product actions use shared shell actions only: details/collapse, reserve, change branch, media actions (cover/gallery only when media exists), and back.
- Runtime content path expectation is explicit in seed fields (`localized_description`, `usage_hint`, `short_label`), intended to be hydrated from catalog DB sync path (`care_commerce.product_i18n`) by caller services.

## 5. Patient Card Strategy
- Compact mode includes identity and operational summary: name, patient number, contact hint, photo presence, active flags, and booking snippet.
- Expanded mode remains bounded: contact block, flags, current/upcoming booking, recommendation summary, order summary, chart summary entry.
- Role-safe behavior:
  - allowed roles: admin/doctor
  - other roles receive limited-access card variant with back-only action.
- No deep chart dumping is included.

## 6. Doctor Card Strategy
- Compact mode includes display name, specialty, branch, and operational hint.
- Expanded mode includes bounded schedule + queue summaries + service tags.
- Actions remain operational and compact: details/collapse, today, schedule, open, back.
- No HR/admin analytics content added.

## 7. Source-Aware Rendering Notes
- Product expanded detail varies by source context:
  - recommendation source shows recommendation rationale
  - category source shows category-origin context line
- Patient expanded recommendation block is only emphasized for search/booking sourced opens in this PR implementation.

## 8. Media Integration Notes
- Product card integrates media state through shared `CardMedia` and action set:
  - cover action appears only when media exists
  - gallery action appears only when multiple media items exist
  - no-media path suppresses media actions safely
- Back behavior remains handled via existing shared navigation/target resolution.

## 9. Files Added
- docs/report/PR_UC2_REPORT.md

## 10. Files Modified
- app/interfaces/cards/models.py
- app/interfaces/cards/adapters.py
- app/interfaces/cards/__init__.py
- tests/test_unified_card_framework_uc1.py

## 11. Commands Run
- `find .. -name AGENTS.md -print`
- `rg --files | head -n 200`
- multiple `sed -n` reads for required docs and UC1/UC1A reports
- `pytest -q tests/test_unified_card_framework_uc1.py`

## 12. Test Results
- `tests/test_unified_card_framework_uc1.py`: pass

## 13. Known Limitations / Explicit Non-Goals
- No booking profile business expansion in UC-2 (explicit non-goal).
- No full aiogram handler wiring for these new profile seeds in this PR.
- Role-safety is adapter-level and should be reinforced in handler/service integration path in follow-up wiring PR.
- Media actions are baseline card-level actions only; full media transport/open execution remains existing framework concern.

## 14. Deviations From Docs (if any)
- `docs/16-1_card_profiles.md` contains language that booking card should also be designed in this wave, while UC-2 request explicitly scopes this PR away from booking business implementation. Followed explicit UC-2 scope and only kept booking adapter baseline unchanged.

## 15. Readiness Assessment for PR UC-3
- Shared shell now hosts three real business profile adapters with role/source/media behavior.
- Test suite now exercises these profile flows and callback/nav safety in-profile context.
- Repo is ready for UC-3 booking-focused profile/business layering without replacing card framework.
