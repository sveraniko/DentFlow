# DentFlow — Architecture Audit & Refactoring Proposals

## 1. File Size Overview (production code, excl. tests)

| File | Lines | Verdict |
|------|-------|---------|
| `app/interfaces/bots/patient/router.py` | **4 650** | 🔴 Critical |
| `app/interfaces/bots/admin/router.py` | **3 262** | 🔴 Critical |
| `app/interfaces/bots/doctor/router.py` | **2 217** | 🟠 High |
| `app/infrastructure/db/booking_repository.py` | **1 143** | 🟡 Medium |
| `app/application/booking/telegram_flow.py` | **1 068** | 🟡 Medium |
| `app/application/care_commerce/service.py` | **985** | 🟡 Medium |
| `app/application/booking/orchestration.py` | **899** | 🟡 Medium |
| `app/infrastructure/db/patient_repository.py` | **809** | 🟡 Medium |
| `app/interfaces/cards/adapters.py` | **749** | 🟢 Acceptable |
| `app/interfaces/bots/owner/router.py` | **539** | 🟢 OK |

---

## 2. Root Cause: The Giant Closure Pattern

All bot routers use a single `make_router(...)` factory function that returns one `Router` object.
**Everything** — state helpers, panel renderers, callback handlers — is defined as nested functions
inside that one closure. This creates 4 000-line Python files that are:

- Impossible to navigate without IDE symbol search
- Untestable in isolation (no public API, only inner functions)
- Impossible to split without refactoring the entire closure
- A single merge-conflict magnet in any team environment

---

## 3. Proposals

---

### 3.1 `patient/router.py` — 4 650 lines → 8 files

The patient bot has 5 clearly distinct feature domains currently merged into one file.

#### Proposed split:

```
app/interfaces/bots/patient/
├── router.py              ← STAYS: thin assembler (~80 lines)
├── deps.py                ← NEW: shared deps dataclass (i18n, booking_flow, etc.)
├── state.py               ← NEW: _PatientFlowState, _CareViewState, load/save helpers (~120 lines)
├── panels.py              ← NEW: _send_or_edit_panel, _send_media_panel (~100 lines)
├── resolvers.py           ← NEW: _resolve_service_label, _resolve_status_label, etc. (~80 lines)
├── handlers/
│   ├── __init__.py
│   ├── home.py            ← NEW: /start, phome:* callbacks (~60 lines)
│   ├── booking_new.py     ← NEW: new booking flow (service→doctor→slot→contact→review→confirm) (~600 lines)
│   ├── booking_control.py ← NEW: my_booking, reschedule, cancel, waitlist (~450 lines)
│   ├── care.py            ← NEW: care catalog, product cards, branch picker, order creation (~900 lines)
│   └── recommendations.py ← NEW: recommendations list + detail + reminder actions (~500 lines)
```

**Key insight**: the closure pattern can be replaced by a `PatientRouterDeps` dataclass
injected into each sub-module's `make_*_router(deps)` factory. All deps are shared
via that one object, not via closure capture.

---

### 3.2 `admin/router.py` — 3 262 lines → 6 files

```
app/interfaces/bots/admin/
├── router.py              ← STAYS: thin assembler (~80 lines)
├── deps.py                ← NEW: AdminRouterDeps dataclass
├── handlers/
│   ├── __init__.py
│   ├── queue.py           ← NEW: booking queue view + claim + pass (~500 lines)
│   ├── booking_ops.py     ← NEW: confirm / reschedule / cancel / check-in (~400 lines)
│   ├── patients.py        ← NEW: patient search + profile view (~350 lines)
│   ├── reference.py       ← NEW: /admin_reference, catalog view (~200 lines)
│   └── exports.py         ← NEW: reports, CSV exports (~200 lines)
```

---

### 3.3 `doctor/router.py` — 2 217 lines → 4 files

```
app/interfaces/bots/doctor/
├── router.py              ← thin assembler
├── handlers/
│   ├── schedule.py        ← daily schedule view + slot navigation
│   ├── patient_ops.py     ← patient card, notes, check-in
│   └── care_orders.py     ← care order view for doctor
```

---

### 3.4 `booking_repository.py` — 1 143 lines → 3 files

The repository mixes 3 distinct concerns:

```
app/infrastructure/db/
├── booking_repository.py       ← STAYS: BookingOrchestrationRepository (writes, transactions)
├── booking_read_repository.py  ← NEW: read-only queries (list_open_slots, get_booking_session, etc.)
├── booking_seed.py             ← NEW: seed_stack3_booking + _seed_rows helpers
```

---

### 3.5 `telegram_flow.py` — 1 068 lines → 3 files

The application service mixing orchestration delegation + slot queries + snapshot builders:

```
app/application/booking/
├── telegram_flow.py            ← STAYS: BookingPatientFlowService (entry point, ~300 lines)
├── telegram_flow_queries.py    ← NEW: list_slots_for_session, get_availability_slot, get_booking
├── telegram_flow_snapshots.py  ← NEW: build_booking_card, build_booking_snapshot
```

---

### 3.6 `care_commerce/service.py` — 985 lines → 3 files

```
app/application/care_commerce/
├── service.py             ← STAYS: CareCommerceService core (create_order, transition, ~350 lines)
├── catalog.py             ← NEW: list_catalog_products_by_category, resolve_product_content
├── reservations.py        ← NEW: create_reservation, compute_free_qty, availability queries
```

---

## 4. Migration Strategy

These are large refactors. Recommended order to avoid regressions:

1. **Start with `state.py` + `resolvers.py` + `panels.py`** — pure extractions, zero logic change
2. **Extract `handlers/home.py`** — 3 handlers, trivial
3. **Extract `handlers/booking_new.py`** — highest-impact flow, well-tested
4. **Extract `handlers/care.py`** — large but isolated from booking
5. **Tackle `admin/router.py`** after patient bot is stable

Each step: extract → update imports → run full test suite → commit.

---

## 5. What NOT to Split

- `orchestration.py` (899 lines) — coherent transactional unit. Splitting would scatter
  the state machine across files and make transaction boundaries invisible.
- `adapters.py` (749 lines) — card rendering pipeline, tight internal coupling.
  A split here would create circular import risk.
- `owner/router.py` (539 lines) — fine as is.
