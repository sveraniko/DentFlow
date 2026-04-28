# P0-07C — Final Patient Pre-Live Manual Checklist + GO/NO-GO Protocol

## 1) Purpose and scope

This runbook is the final manual pre-live checklist for running the **real Telegram patient bot** against a prepared **local/staging demo database**.

- Scope: patient-facing pre-live verification in Telegram + minimal operator checks.
- Out of scope: schema changes, feature work, router/module split, live Google API execution.

---

## 2) Preconditions (must pass before manual Telegram run)

### 2.1 Environment and infrastructure

- [ ] Docker engine is running.
- [ ] Postgres and Redis are running (local/staging only):

```bash
docker compose up -d postgres redis
```

- [ ] Safe DB selected:
  - local/staging DB only;
  - **never production DB**.
- [ ] Env is configured:
  - Telegram bot token is present;
  - DB DSN is present (`DENTFLOW_TEST_DB_DSN` for DB-backed tests);
  - Redis DSN is present if used by current runtime;
  - Google Calendar projection disabled unless explicitly testing projection behavior.

### 2.2 Demo seed load

- [ ] Load demo seed using one of:

```bash
make seed-demo
```

or

```bash
python scripts/seed_demo.py --relative-dates --start-offset-days 1
```

### 2.3 Seed verification gates (DB-backed)

Before GO decision, verify DB-backed smoke gates are green:

- [ ] P0-07A
- [ ] P0-07B1
- [ ] P0-07B2
- [ ] P0-07B3

Reference commands:

```bash
pytest -q tests/test_p0_07a_patient_read_surfaces_pre_live.py
pytest -q tests/test_p0_07b1_booking_mutation_pre_live.py
pytest -q tests/test_p0_07b2_recommendation_care_mutation_pre_live.py
pytest -q tests/test_p0_07b3_consolidated_mutation_pre_live_gate.py
```

If DB-backed tests are skipped (e.g., `DENTFLOW_TEST_DB_DSN` not configured), this checklist may still be reviewed as documentation, but **live readiness status is NO-GO**.

### 2.4 Integration truth boundaries (must be understood)

- Care catalog source can be either seeded JSON/demo fixtures or Sheets sync.
- Reference sheet + patient sheet templates are **template-only** and **not active sync truth** for this pre-live path.
- Google Calendar integration is a **one-way mirror projection**, not booking source-of-truth.

---

## 3) Test identities from demo seed

Use these identities for patient path coverage:

1. Telegram user `3001`
   - patient: `patient_sergey_ivanov`
   - expected: active booking + recommendations + care orders + product-linked recommendations.

2. Telegram user `3002`
   - patient: `patient_elena_ivanova`
   - expected: reschedule-related path + recommendation/order history (if seeded).

3. Telegram user `3004`
   - patient: `patient_maria_petrova`
   - expected: protected-doctor-code path + recommendation/order history (if seeded).

4. Phone-only patient
   - patient: `patient_giorgi_beridze`
   - expected: phone lookup path + canceled/history booking.

### Telegram user_id reality check

Real BotFather bot testing does not reliably allow easy `telegram_user_id` spoofing. Use one workaround:

- bind the real tester Telegram ID in seed/contact data for local run;
- update demo seed contact mapping for local run;
- validate phone lookup path manually when ID mapping is constrained.

Do not assume user_id spoofing is trivial.

---

## 4) Bot startup commands (current project commands)

### 4.1 Infra + seed

```bash
docker compose up -d postgres redis
make seed-demo
```

### 4.2 Application bot runtime

Current repository command:

```bash
make run-bots
```

Equivalent direct entrypoint from Makefile:

```bash
APP_RUN_MODE=polling python -m app.main
```

### 4.3 Optional admin/operator runtime checks

Admin checks are optional for this patient-focused pre-live, unless integration demo explicitly requires them.

---

## 5) Manual patient flow checklist (Telegram)

For each flow below, record PASS/BLOCKER/NOTE with screenshot evidence.

## A. Start/Home

Steps:
1. Open patient bot.
2. Send `/start`.

Expected:
- Readable DentFlow home panel.
- Buttons include:
  - `Записаться на приём`
  - `Моя запись`
  - `Рекомендации врача`
  - `Уход и гигиена`
- Old text `Добро пожаловать в DentFlow. Выберите действие:` does not appear as stale fallback.
- Every non-home path supports Home/back recovery.

Pass/fail rules:
- No dead end.
- No forced `/start` required to recover.

## B. My Booking

Steps:
1. Tap `Моя запись`.

Expected:
- Readable booking card with service/doctor/date/time/branch/reminders/status.
- No raw/debug/internal artifacts such as:
  - `Actions:`
  - `Channel: telegram`
  - raw `booking_id`
  - `branch: -`
  - `UTC/MSK` debug fragments.

Action panel behavior:
- Pending booking: Confirm / Reschedule / Earlier slot / Cancel / Home.
- Terminal booking: no mutation actions.

## C. New Booking basic path

Steps:
1. `/start`
2. `Записаться`
3. Choose service `Консультация`
4. Choose public doctor (e.g., Dr. Anna) or any public doctor.
5. Choose slot.
6. Submit phone/contact.
7. Review.
8. Confirm.

Expected:
- Readable service picker.
- Readable doctor picker.
- Localized slot picker (no raw UTC or English weekday/month like Tue/Apr in RU UI).
- Contact prompt includes phone example and reply keyboard.
- Review panel contains edit actions.
- Success panel is readable.
- `Моя запись` reflects new booking.

## D. Protected doctor code path

Steps:
1. Start booking.
2. Choose service `Лечение` / `service_treatment`.
3. Choose doctor-by-code path.
4. Enter `IRINA-TREAT`.
5. Choose slot.
6. Contact/review/confirm.

Expected:
- Dr. Irina is hidden from public doctor picker if non-public.
- Valid code resolves Dr. Irina.
- Wrong service/code combination does not resolve.
- Final review and booking reflect Dr. Irina.

## E. Slot conflict / unavailable behavior

Steps (if practical):
- Attempt same slot from second tester/session, or use known occupied slot.

Expected:
- No popup-only dead end.
- Inline unavailable notice.
- Refreshed slot list.
- Failed slot is not immediately re-offered.
- Home/back recovery available.

## F. Review edit actions

Steps:
1. Reach review panel.
2. Edit service.
3. Edit doctor.
4. Edit time.
5. Edit phone.

Expected:
- Previous slot hold released.
- Flow returns to correct picker/contact step.
- Review refreshes after reselection.
- No repeated unnecessary phone request unless phone edit explicitly chosen.
- Final booking uses updated values only.

## G. Recommendations

Steps:
1. `/start`
2. `Рекомендации врача`

Expected:
- Active/history/all filters.
- Readable rows.
- Pagination when needed.
- Detail card readable.
- Status-aware action buttons.
- Product handoff works for linked recommendations.
- Ack/accept/decline shows inline notice (not popup-only).
- Terminal recommendations do not expose mutation buttons.

## H. Recommendation products

Steps:
1. Open product-linked recommendation.
2. Open recommended products.

Expected:
- Product list/picker appears.
- Product card readable.
- Invalid recommendation fallback shows recovery panel.
- Empty products state shows recovery panel.
- `Care catalog` / `Home` actions exist.

## I. Care catalog

Steps:
1. `/start`
2. `Уход и гигиена`

Expected:
- Categories list.
- Product list.
- Product card.
- Branch/availability/price visible in readable format.
- Reserve action present when in stock.
- Home/back recovery.
- No raw/internal fields.

## J. Care reserve

Steps:
1. Open in-stock product `SKU-BRUSH-SOFT`.
2. Reserve.

Expected:
- Order created.
- Order result panel appears.
- Current order opens.
- My orders includes it.
- Order detail is readable.

## K. Out-of-stock invariant

Steps:
1. Open out-of-stock product `SKU-GEL-REMIN`.
2. Try reserve if button appears.

Expected:
- Reserve blocked.
- No active visible invalid order created.
- Recovery panel appears.
- Return path to Care catalog/Home.

## L. Repeat/reorder

Steps:
1. Open existing care order.
2. Repeat/reorder.

Expected:
- Either valid new reservation or safe stock/branch constraint message.
- No raw `view.text`/debug rendering.
- Orders list updates, or safe explanatory message shown.

## M. Navigation audit

At random points use Back/Home/My Booking.

Expected:
- No dead ends.
- No mandatory `/start` recovery.

---

## 6) Admin/operator spot checks (minimal)

Optional quick checks:

- `/admin_calendar` — confirms calendar-awareness surface (no need for live Google call).
- `/admin_integrations` — integration status surface.
- `/admin_catalog_sync sheets <url_or_id>` — document-only unless Sheets are prepared.

If admin bot is not run for this patient pre-live pass, record as optional parallel check, not a patient blocker unless demo contract requires integration verification.

---

## 7) Blockers vs non-blockers

### 7.1 Blockers (NO-GO triggers)

- Bot crash or traceback in flow.
- DB exception leaks to user UI.
- User gets stuck with no Home/back recovery.
- `/start` required to escape normal flow.
- Booking cannot be created in core path.
- My Booking shows raw/debug/internal fields.
- Slot date/time localization is raw UTC/English in RU UI.
- Review edit produces inconsistent booking result.
- Out-of-stock flow creates active visible invalid order.
- Recommendation action callbacks are popup-only/broken.
- Care reserve creates order with missing product/branch invariants.
- Telegram contact keyboard remains stuck after review completion.
- Callback-expired stale loop with no recovery.

### 7.2 Non-blockers (can carry forward)

- Minor copy/wording polish.
- Emoji preference disagreements.
- Long text trim opportunities.
- Optional Google Calendar not configured in this pass.
- Reference/patient Sheets sync absent (template-only truth for now).
- Admin/doctor polish outside patient path unless it blocks patient demo readiness.

---

## 8) Evidence collection requirements

Collect and attach:

### 8.1 Screenshots

- Home.
- Service picker.
- Doctor picker.
- Slot picker.
- Contact prompt.
- Review panel.
- Booking success.
- My Booking card.
- Recommendations list/detail.
- Care product card.
- Care order detail.

### 8.2 Logs/snippets

- Bot startup logs.
- `make seed-demo` output.
- DB-backed smoke outputs (P0-07A/B1/B2/B3 minimum).
- Confirmation of no traceback in exercised flows.

### 8.3 Final matrix

Maintain per-flow matrix with `PASS | BLOCKER | NOTE` statuses.

---

## 9) GO/NO-GO protocol

### GO only if all are true

- P0-07 DB-backed tests are green.
- Manual patient checklist contains no blockers.
- `seed-demo` completed successfully.
- Patient booking creation works end-to-end.
- My Booking is readable and mutation-safe.
- Recommendations and care surfaces are readable and mutation-safe.
- No raw/debug leaks.
- No dead-end navigation.

### NO-GO if any are true

- Any blocker in section 7.1 found.
- DB-backed gate skipped/unverified.
- Booking mutation fails.
- Care reserve invariant broken.
- Recommendation action path broken.

When reporting outcome, include explicit recommendation line:

- `Recommendation: GO for controlled live patient demo` or
- `Recommendation: NO-GO — fix blockers and rerun checklist`.
