# PILOT-0 audit — launch readiness after PAT / ADM / DOC / Stack13 / Owner baseline closure

Date: 2026-04-22  
Auditor stance: launch-readiness only (not feature scope)  
Verdict basis: code reality first, docs second.

## 1. Executive verdict

**Verdict: NO (not yet ready for a live pilot start attempt).**

DentFlow has substantial bounded functional coverage (PAT/ADM/DOC/Stack13/Owner baseline), but current runtime launch shape has at least one hard blocker for a real bot launch: `python -m app.main` builds dispatcher wiring and exits without starting polling/webhook loop, so bots do not actually run. In addition, environment/runbook clarity remains partial (notably integration env parity and production Redis/session stance), and fresh-environment startup requires non-obvious DB/bootstrap sequencing plus mandatory multi-token configuration before any smoke can run. Worker foundations are materially stronger than bot runtime entry.

### Top 5 launch blockers/risks
1. Bot runtime entrypoint does not start Telegram update loop (hard blocker).  
2. Env/config docs are incomplete vs runtime settings (`INTEGRATIONS_GOOGLE_CALENDAR_*` settings exist but are absent in `.env.example`).  
3. Redis/session behavior differs by env (`APP_ENV!=prod` uses in-memory state), risky for pilot realism and restart continuity.  
4. Fresh environment startup requires DB availability + bootstrap + seeds, but launch runbook is fragmented and non-operationally explicit.  
5. Telegram role-bot identities/entrypoints are only partially explicit for operators (tokens listed, but launch mechanics per bot are unclear given single entrypoint that currently exits).

---

## 2. Launch readiness matrix

| Area | Status | Evidence | Risk | Next action |
|---|---|---|---|---|
| app startup | **Blocked** | `app/main.py` builds `RuntimeRegistry` + dispatcher and exits; no polling/webhook start call in repo. | App process can “start” but no bot interaction occurs. | Add canonical bot runtime loop entrypoint and document it. |
| bot startup | **Blocked** | Routers are wired (patient/admin/doctor/owner), but no runtime update consumer. | Live pilot cannot receive Telegram updates. | Implement bounded launch entry and smoke command. |
| worker startup | **Partial** | `app/projector_worker.py`, `app/reminder_worker.py`, mode-based `app/worker.py` exist with signal handling/catch-up. | Depends on DB/env readiness; not validated end-to-end here due missing infra. | Keep topology; add minimal worker smoke runbook steps. |
| DB/migrations | **Partial** | No `alembic/` dir; baseline uses `scripts/db_bootstrap.py` + large SQL bootstrap; seed scripts exist for stack1/2/3. | Fresh launch depends on strict manual bootstrap/seed order; migration-era operational contract not present. | Publish explicit launch bootstrap sequence and success criteria. |
| Redis/state | **Partial** | Card runtime uses Redis only when `APP_ENV` is prod; otherwise in-memory fallback. | In-memory state is unsafe for realistic pilot continuity/restarts/multi-process. | Require prod-like env + Redis for pilot and state this as mandatory. |
| Telegram config | **Partial** | Tokens are required (`Field(...)`) for patient/admin/doctor/owner. | Startup fails fast without all 4 tokens, even for limited-scope smoke. | Document mandatory token policy and scoped fallback strategy. |
| role/access config | **Ready** | Runtime wires all role routers; admin/doctor/owner have role guards; patient flow is intentionally user-bound flow. | Role misbinding still possible if seed/access data incomplete. | Add small startup check for actor-role seed presence. |
| calendar integration | **Partial** | Projector checks `google_calendar_enabled`; disabled path is safe skip; misconfigured enabled path can fail projection events. | If enabled without credentials, projector failures accumulate; can confuse operators. | Add explicit preflight checks + env docs for enabled path. |
| catalog sync | **Partial** | Admin command surface exists; sync service optional wiring and bounded reporting present. | Operational misuse possible (path/url expectations, data quality errors). | Keep bounded; add one operator smoke command in runbook. |
| notification delivery | **Partial** | Reminder sender and patient delivery senders exist; resolver expects Telegram contact in DB. | Missing/invalid telegram contact leads to delivery misses; must be expected in pilot. | Add pre-pilot data sanity check for patient telegram bindings. |
| smoke scripts | **Partial** | Make targets: test/db-bootstrap/run-app/run-worker/seed-stack*. | Missing canonical “bot live smoke” command and no single launch smoke script. | Add a compact smoke checklist + scripts. |
| launch runbook | **Blocked** | Strategic docs exist, but operator-grade launch sequence is not a single concrete executable path. | Pilot start may fail from sequencing ambiguity rather than product logic. | Add one explicit launch runbook doc section (bounded). |

---

## 3. Hard blockers

### HB-1 — Bot runtime does not actually run Telegram updates
- **Evidence:** `python -m app.main` currently initializes settings/logging/runtime dispatcher and then exits; repository has no `start_polling`/webhook runtime call.
- **Why it blocks:** Live pilot requires bots to receive and process incoming Telegram updates continuously.
- **Minimal fix:** Add one bounded bot runtime entry (`run_polling`/equivalent) with clear role/token behavior and startup logging.

### HB-2 — No operator-grade launch runbook that matches runtime reality
- **Evidence:** There are strategy docs, but no single concrete “from clean env to first bot command” runbook with strict order and verification checks.
- **Why it blocks:** Real pilot launch can fail operationally even if code paths exist.
- **Minimal fix:** Add a compact canonical run sequence (env → db bootstrap/seed → worker start → bot start → first commands).

---

## 4. Major risks

### R-1 — Env example drift vs settings model
- **Evidence:** `IntegrationsConfig` includes multiple Google Calendar env knobs not represented in `.env.example`.
- **Mitigation:** Align `.env.example` to settings model (including all `INTEGRATIONS_GOOGLE_CALENDAR_*` and base URL fields).

### R-2 — Redis/session fallback can hide pilot-only failures
- **Evidence:** non-prod runtime uses in-memory card/session state.
- **Mitigation:** Force pilot environment to use production-style Redis runtime and explicitly prohibit in-memory fallback in pilot.

### R-3 — DB/bootstrap path is baseline-style, not migration-ops style
- **Evidence:** No alembic chain; bootstrap script is canonical schema creation path.
- **Mitigation:** Accept for bounded pilot, but codify exact bootstrap + seed + verification commands.

### R-4 — Telegram recipient assumptions rely on DB contact hygiene
- **Evidence:** Reminder delivery resolves Telegram user id from patient contact table and fails to non-target/invalid-target states otherwise.
- **Mitigation:** Add pre-pilot data check for active telegram contacts for pilot cohort.

### R-5 — Integration enablement failure surface can look like silent partial runtime degradation
- **Evidence:** Calendar projector only runs when enabled; misconfigured enabled state raises runtime failures per event path.
- **Mitigation:** Add integration preflight check and explicit operator warnings in launch checklist.

---

## 5. Things good enough

1. **Role router wiring baseline is present** across patient/admin/doctor/owner in runtime assembly.  
2. **Worker topology is bounded and coherent** (projector/reminder split, mode switching, signal handling, startup catch-up).  
3. **Baseline DB bootstrap + seed assets exist** and are sufficient as a pre-migration launch method for pilot smoke if executed in strict order.  
4. **Integration guardrail intent is mostly sound** (calendar mirror is optional/one-way, catalog sync bounded).  
5. **Targeted test coverage depth is high** for many scenario slices, even though pilot launch smoke is not yet consolidated.

---

## 6. Recommended pilot hardening PR stack

### PILOT-A1 — Make bot runtime truly launchable (highest priority)
- **Objective:** Ensure app can actually receive Telegram updates in a live pilot process.
- **Exact scope:**
  - Add canonical bot run loop entry in `app.main` (or dedicated runtime module) using existing dispatcher wiring.
  - Add startup log lines showing active runtime mode and configured role tokens presence (without leaking tokens).
  - Add one minimal smoke command path in docs/Makefile for local pilot-like launch.
- **Non-goals:**
  - no role surface redesign,
  - no business logic expansion,
  - no integration redesign.
- **Files likely touched:**
  - `app/main.py`
  - optional `Makefile`
  - `README.md` and/or `docs/95_testing_and_launch.md`
- **Tests/scripts likely added:**
  - minimal runtime import/startup smoke test (bounded).
- **Migrations needed?** no
- **Acceptance criteria:**
  - one documented command starts long-running bot runtime,
  - first role commands can be executed from Telegram in pilot env.

### PILOT-A2 — Launch env/runbook contract closure
- **Objective:** Remove operator ambiguity for clean-environment launch.
- **Exact scope:**
  - Align `.env.example` with all required/optional runtime settings used by startup and integrations.
  - Add explicit launch order: env prep, DB bootstrap, seeds, worker start, app start, first smoke commands, stop/rollback basics.
  - Clarify mandatory vs optional integrations and safe-disabled expectations.
- **Non-goals:**
  - no feature changes,
  - no broad architecture rewrite.
- **Files likely touched:**
  - `.env.example`
  - `README.md`
  - `docs/95_testing_and_launch.md`
  - `docs/81_worker_topology_and_runtime.md`
- **Tests/scripts likely added:**
  - optional tiny config sanity script/checklist snippets.
- **Migrations needed?** no
- **Acceptance criteria:**
  - new operator can launch from clean machine via documented steps only,
  - env variable set is complete and internally consistent.

### PILOT-A3 — Pilot safety preflight checks (data + integration + state)
- **Objective:** Catch common pilot launch surprises before live bot run.
- **Exact scope:**
  - Add bounded preflight script/command(s) validating: DB reachable, key tables exist, Redis reachable (for pilot), required role actors present, Telegram contact readiness for pilot cohort, integration toggle consistency.
  - Add runbook mapping of each failed preflight to corrective action.
- **Non-goals:**
  - no new product features,
  - no full observability platform,
  - no migration framework rollout.
- **Files likely touched:**
  - `scripts/` (new preflight helper)
  - docs launch sections
- **Tests/scripts likely added:**
  - focused script-level checks.
- **Migrations needed?** no
- **Acceptance criteria:**
  - preflight returns pass/fail with actionable messages,
  - pilot start is blocked when critical dependencies are missing.

---

## 7. Launch run checklist draft

### env
- [ ] Create `.env` from `.env.example`.
- [ ] Fill all 4 Telegram bot tokens (patient/admin/doctor/owner).
- [ ] Set `DB_DSN` to reachable Postgres.
- [ ] For pilot realism, set `APP_ENV=prod` and valid `REDIS_URL`.
- [ ] If calendar mirror enabled, set all required `INTEGRATIONS_GOOGLE_CALENDAR_*` values.

### DB
- [ ] Run DB bootstrap.
- [ ] Load stack seeds required for role/access + core patient/booking smoke.
- [ ] Verify required schemas/tables exist and seed counts look sane.

### Redis
- [ ] Confirm Redis reachable from runtime.
- [ ] Confirm no in-memory fallback is used for pilot runtime.

### Telegram
- [ ] Verify each bot token resolves to intended bot identity.
- [ ] Verify token-to-role entrypoint mapping is documented for operators.

### app
- [ ] Start bot runtime with canonical command.
- [ ] Confirm process remains alive and logs startup success.

### workers
- [ ] Start projector worker.
- [ ] Start reminder worker.
- [ ] Confirm heartbeat/status path for reminder worker.

### first smoke commands
- [ ] Admin: `/admin_integrations`, `/admin_calendar`, `/admin_today`.
- [ ] Doctor: `/doctor_today` (or current queue/schedule equivalent).
- [ ] Owner: `/owner_today`, `/owner_digest`, `/owner_alerts`.
- [ ] Patient: `/start`, `/book`, `/my_booking`.

### first role commands
- [ ] Validate unauthorized role guard behavior (admin/doctor/owner).
- [ ] Validate patient flow continuity across at least one booking path.

---

## 8. Final recommendation

Start pilot hardening PRs immediately. Sequence should be **PILOT-A1 first**, then **PILOT-A2**, then **PILOT-A3**. Do **not** start broad refactors or new feature waves before these bounded launch-readiness gaps are closed; focus only on making live bot run + clean-environment operations reliable and unambiguous.
