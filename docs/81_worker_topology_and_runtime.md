# Worker Topology and Runtime

> Canonical production worker topology for projector and reminder processing.

## 1. Purpose

This document makes DentFlow worker topology explicit so production deployment does not depend on tribal knowledge.

It defines:
- which worker entrypoints exist;
- what each worker line owns;
- which paths are production runtime paths vs one-shot utility paths;
- startup catch-up and shutdown boundaries;
- operator/deployment expectations.

## 2. Canonical worker lines

DentFlow has two explicit continuous worker lines:

1. **Projector worker line**
2. **Reminder worker line**

These lines are independent runtime responsibilities and should be treated as separate deployable worker processes/services in production.

## 3. Entry points

### 3.1 Bot runtime
- `python -m app.main`
- Responsibility: Telegram bot interface runtime only.
- Not responsible for projector or reminder background loops.

### 3.2 Projector worker runtime
- Preferred explicit entrypoint: `python -m app.projector_worker`
- Equivalent mode entrypoint: `WORKER_MODE=projector python -m app.worker`
- Responsibility: outbox-driven projection processing via `ProjectorWorkerRuntime`.

### 3.3 Reminder worker runtime
- Preferred explicit entrypoint: `python -m app.reminder_worker`
- Equivalent mode entrypoint: `WORKER_MODE=reminder python -m app.worker`
- Responsibility: continuous reminder delivery + recovery processing via `ReminderWorkerRuntime`.

### 3.4 Combined mode (optional)
- `WORKER_MODE=all python -m app.worker`
- Runs projector and reminder loops concurrently in one process.
- Useful for local/dev environments; separate processes remain preferred production shape.

### 3.5 One-shot utility path
- `run_worker_once()` in `app/worker.py` is a one-shot helper for tests/dev/manual operations.
- It is **not** the canonical production runtime path.

## 4. Responsibility split

### 4.1 Projector worker responsibility
- Poll outbox in bounded batches.
- Run registered projectors against events.
- Advance projector checkpoints only on success.
- Persist failure visibility and support replay/retry operations.

### 4.2 Reminder worker responsibility
- Poll and process due reminder deliveries in bounded batches.
- Run reminder recovery steps (stale queued reclaim, failed escalation, no-response escalation) in bounded batches.
- Keep reminder delivery/recovery continuously alive in production.

## 5. Startup catch-up behavior

Both worker lines perform bounded startup catch-up to handle restart gaps.

- **Projector worker:** processes up to configured startup catch-up batches before normal polling.
- **Reminder worker:** processes up to configured startup catch-up batches before normal polling.

Catch-up exits when no immediate due work is found, when stop is requested, or when configured catch-up bound is reached.

## 6. Graceful shutdown boundary

Both worker runtimes install signal handlers (`SIGINT`, `SIGTERM` where supported) and stop at safe batch boundaries.

- Stop request does not fake completion for unfinished work.
- Current batch is allowed to finish, then worker exits cleanly.
- Next batch is not started after stop event is set.

## 7. Runtime configuration knobs

### 7.1 Worker mode selection
- `WORKER_MODE=projector|reminder|all` (default: `projector`)

### 7.2 Projector worker knobs
- `PROJECTOR_WORKER_ENABLED`
- `PROJECTOR_WORKER_BATCH_LIMIT`
- `PROJECTOR_WORKER_POLL_INTERVAL_SEC`
- `PROJECTOR_WORKER_STARTUP_CATCHUP_MAX_BATCHES`

### 7.3 Reminder worker knobs
- `REMINDER_WORKER_DELIVERY_BATCH_LIMIT`
- `REMINDER_WORKER_RECOVERY_BATCH_LIMIT`
- `REMINDER_WORKER_POLL_INTERVAL_SEC`
- `REMINDER_WORKER_STARTUP_CATCHUP_MAX_BATCHES`

## 8. Production deployment expectation

Recommended production topology:

- Process A: `python -m app.main` (bot runtime)
- Process B: `python -m app.projector_worker` (projector runtime)
- Process C: `python -m app.reminder_worker` (reminder runtime)

This keeps operational ownership explicit:
- bot runtime handles user interactions,
- projector runtime handles derived-read-model freshness,
- reminder runtime handles reminder delivery/recovery continuity.

## 9. Non-goals for WR-1

This worker topology PR does not add:
- distributed leases/leader election;
- multi-node duplicate prevention sophistication;
- large observability platform redesign.

Those are later hardening concerns.

## 10. WR-2 operational hardening additions

WR-2 adds bounded operational safety and visibility for the reminder worker line:

- **Lease-based active-worker gating** (`system_runtime.worker_leases`) so only one reminder worker instance actively processes reminder batches at a time.
- **Worker status heartbeat surface** (`system_runtime.worker_status`) with:
  - last heartbeat time,
  - current mode (`starting` / `active` / `standby`),
  - last successful processing time,
  - last error timestamp/text.
- **Bounded error cooldown** in reminder runtime to avoid tight infinite error loops.
- **Health inspection command** via `python -m app.reminder_worker_status`.

### WR-2 semantics (explicit limits)

- Lease protection is **bounded best-effort single-active-worker safety**.
- If lease holder crashes, lease expiry allows another worker to take ownership.
- This is not a cross-region consensus system and does not claim strict exactly-once delivery semantics.
