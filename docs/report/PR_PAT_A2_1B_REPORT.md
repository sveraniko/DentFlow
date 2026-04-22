# PR PAT-A2-1B Report — Returning-patient quick-book parity, resume hardening, and regression safety

## What changed after PAT-A2-1A

This PR is a bounded hardening pass on the trusted returning-patient quick-book foundation from PAT-A2-1A.

- Hardened contact-input safety when flow state points to a stale/missing booking session id:
  - new-booking contact submissions now verify that the referenced session still exists before mutating booking context;
  - if the session is missing, the flow state is normalized back to neutral `new_booking_flow` with empty `booking_session_id`.
- Added explicit parity and fallback regressions for `/book` and `phome:book` so trusted quick-entry behavior is proven by tests, not implied.
- Added explicit regression assertions that active reschedule context still takes precedence over `/book` and blocks quick-book start.
- Added service-level regressions for active existing `service_first` sessions (hydrated and non-hydrated) to prove existing-session discipline:
  - existing active session is resumed unchanged;
  - trusted shortcut is not retroactively applied or claimed.

## Exact files changed

- `app/interfaces/bots/patient/router.py`
- `tests/test_booking_patient_flow_stack3c1.py`
- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`
- `tests/test_patient_first_booking_review_pat_a1_1.py`
- `tests/test_patient_reschedule_start_pat_a4_1.py`
- `docs/report/PR_PAT_A2_1B_REPORT.md`

## Trust/fallback cases now covered

Covered by focused router/service tests:

1. `/book` trusted patient + primary phone -> contact step skipped (review path).
2. `phome:book` trusted patient + primary phone -> same review path behavior (parity).
3. `/book` trusted patient without phone -> falls back to normal contact prompt.
4. `/book` without trusted patient -> falls back to normal contact prompt.
5. active reschedule context -> `/book` resumes reschedule panel and does not enter quick-book start.
6. contact input outside `new_booking_contact` mode remains non-destructive/ignored (existing regression remains).
7. stale/missing booking session id while in `new_booking_contact` -> contact submission ignored safely and flow state normalized.
8. no migrations introduced (`migrations/` and `alembic/` absence regression remains in suite).

## How `/book` and `phome:book` parity is guaranteed

Parity is guaranteed by shared router entry helper usage and explicit regression coverage:

- both command and callback routes delegate to `_enter_new_booking(...)`;
- parity test now asserts that `phome:book` uses the same trusted patient + phone lookup payload and reaches the same review flow outcome as `/book` in trusted-safe conditions.

## Resume/active-session hardening notes

- Existing active `service_first` sessions (hydrated and non-hydrated) are resumed unchanged by `start_or_resume_returning_patient_booking(...)`.
- Trusted shortcut is **not** reported as applied when an active session already exists.
- No retroactive mutation is introduced for already-active sessions in this PR.

## Tests added/updated

- `tests/test_booking_patient_flow_stack3c1.py`
  - active hydrated `service_first` session resumes unchanged.
  - active non-hydrated `service_first` session resumes unchanged.
- `tests/test_patient_existing_booking_shortcut_pat_a3_2.py`
  - `phome:book` trusted parity with `/book`.
  - `/book` no trusted patient fallback to contact prompt.
- `tests/test_patient_first_booking_review_pat_a1_1.py`
  - stale/missing session id in `new_booking_contact` is ignored safely and flow state is normalized.
- `tests/test_patient_reschedule_start_pat_a4_1.py`
  - active reschedule `/book` resume additionally asserts quick-book starter was not called.

## Environment/test execution notes

- Targeted regression suites for changed files were executed in this environment.
- No environment blocker prevented execution of the scoped suites run for this PR.

## Closure statement

- **PAT-A2-1 is now considered closed** for the bounded quick-entry foundation scope (PAT-A2-1A + PAT-A2-1B): parity is explicit, trust/fallback matrix is covered, active-session/resume safety is hardened, and PAT-A1/PAT-A3/PAT-A4 semantics remain intact.

## Explicit non-goals left for PAT-A2-2 and PAT-A2-3

### PAT-A2-2 (not done here)
- continuity suggestions (recent service/doctor/branch);
- one-tap repeat/rebook shortcuts;
- broader continuity UX acceleration beyond trusted contact-step skip.

### PAT-A2-3 (not done here)
- broader PAT-002 closure acceptance layer and scenario/doc truth updates;
- expanded cross-suite hardening beyond this bounded quick-entry/resume/fallback matrix.

### Still intentionally out of scope
- reminders redesign;
- booking orchestration redesign;
- admin/doctor/owner flow changes;
- migrations.
