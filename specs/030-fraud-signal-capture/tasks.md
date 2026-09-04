---

description: "Task list for fraud signal capture implementation"
---

# Tasks: Fraud Signal Capture

**Input**: Design documents from `/specs/030-fraud-signal-capture/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/data-schema.md, quickstart.md

**Tests**: Not included as dedicated pytest tasks — `services/api/tests/` has no existing automated-test convention
(only `__init__.py`); this feature is validated via `quickstart.md`'s manual scenarios against the local Docker
stack, matching how prior specs (013, 029) in this repo were verified.

**Organization**: Tasks are grouped by user story (US1 = P1, US2 = P2) per spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps task to spec.md's US1/US2

---

## Phase 1: Setup

- [X] T001 Create migration `supabase/migrations/20260903000002_fraud_signal_capture.sql`: `fraud_signals` table
  per data-model.md — `id UUID PK DEFAULT gen_random_uuid()`, `user_id UUID NULL REFERENCES auth.users(id) ON
  DELETE SET NULL` (references `auth.users`, not `profiles` — corrected during Phase 3 runtime review: the
  `signup` event fires before any `profiles` row exists, so a `profiles` FK rejected every signup signal),
  `event_type TEXT NOT NULL CHECK (event_type IN ('signup','login','ride_posted','booking_created'))`,
  `hashed_device_id TEXT NULL`, `hashed_ip TEXT NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`; indexes
  on `(hashed_device_id) WHERE hashed_device_id IS NOT NULL`, `(hashed_ip)`, `(user_id, created_at)`; `ALTER TABLE
  fraud_signals ENABLE ROW LEVEL SECURITY` with no public policies (service-role only, same posture as
  `match_events`/`driver_location_history`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: Must complete before Phase 3.

- [X] T002 Add `fraud_signal_hmac_secret: str = ""` field to `Settings` in `services/api/app/core/config.py`,
  alongside `internal_secret`/`webhook_secret` (same pattern, no Vault indirection per research.md R2).
- [X] T003 [P] Add `FRAUD_SIGNAL_HMAC_SECRET=generate_with__python_-c_"import secrets; print(secrets.token_hex(32))"`
  line to `services/api/.env.example`, matching the existing `WEBHOOK_SECRET` line's format.
- [X] T004 [P] Generate a real secret (`python -c "import secrets; print(secrets.token_hex(32))"`) and set
  `FRAUD_SIGNAL_HMAC_SECRET=<value>` in the local (gitignored) `services/api/.env` so local dev/testing can exercise
  hashing end-to-end.
- [X] T005 Create `services/api/app/services/fraud_signal_service.py` with `async def record_signal(event_type: str,
  user_id: uuid.UUID | None, device_id: str | None, ip_address: str | None) -> None`: mirrors
  `match_logging_service.persist_match_events`'s shape — HMAC-SHA256 (stdlib `hmac`/`hashlib`, keyed by
  `settings.fraud_signal_hmac_secret`) each of `device_id` (only if not `None`, else leave `hashed_device_id` as
  SQL `NULL`) and `ip_address` (if `None` — should not happen per spec but guard anyway — log a skip and return,
  since `hashed_ip` is `NOT NULL` and there's nothing meaningful to store), then `INSERT INTO fraud_signals
  (user_id, event_type, hashed_device_id, hashed_ip) VALUES (...)` via `asyncpg` raw SQL (`get_pool()` from
  `app.core.database`, no ORM). Wrap the whole body in `try/except Exception` logging
  `logger.error(json.dumps({"event": "fraud_signal_persist_failure", "error": str(exc), "event_type": event_type}))`
  — must never raise into the caller (FR-005, FR-006, NFR-002). Depends on: T001, T002.

**Checkpoint**: Table and service exist — user story work can begin.

---

## Phase 3: User Story 1 - Trust-relevant events are tagged with a hashed device/IP signal (Priority: P1) 🎯 MVP

**Goal**: Sign-up, login, ride-posting, and booking-creation each produce a `fraud_signals` row carrying the
hashed device ID and hashed IP.

**Independent Test**: Perform sign-up, login, and booking creation from the same simulated device/IP; query
`fraud_signals` directly and confirm one row per event, matching hashed values, no raw value anywhere (quickstart.md
Scenarios 1-5).

### Backend

- [X] T006 [US1] In `services/api/app/api/auth/router.py`, extend `verify_otp`: add `request: Request` (already
  imported) and `background_tasks: BackgroundTasks` (add to the `fastapi` import) parameters; after
  `auth_service.verify_otp(...)` succeeds, call `background_tasks.add_task(fraud_signal_service.record_signal,
  event_type="signup", user_id=uuid.UUID(result["user"]["id"]), device_id=request.headers.get("x-device-id"),
  ip_address=request.client.host if request.client else None)` before returning `result`. Import
  `fraud_signal_service` from `app.services` and `uuid` from stdlib. **Runtime review caught a bug**: `result` is a
  plain `dict` (`auth_service.verify_otp` returns `dict`, not a `SessionResponse` object) — `result.user.id` raised
  `AttributeError` on every signup; fixed to `result["user"]["id"]`.
- [X] T007 [US1] In the same file, extend `sign_in_with_password` identically — `event_type="login"`, same
  `request`/`background_tasks` params, fired after `auth_service.sign_in_with_password(...)` succeeds, using
  `result["user"]["id"]` (same dict-not-object fix as T006).
- [X] T008 [P] [US1] In `services/api/app/api/rides/router.py`, extend `create_ride`: add `request: Request` and
  `background_tasks: BackgroundTasks` params (add `Request`, `BackgroundTasks` to the `fastapi` import); after
  `ride_service.create_ride(...)` succeeds (before the final `return`), call
  `background_tasks.add_task(fraud_signal_service.record_signal, event_type="ride_posted", user_id=driver_id,
  device_id=request.headers.get("x-device-id"), ip_address=request.client.host if request.client else None)`.
  `driver_id` is already computed at the top of the handler. Import `fraud_signal_service` from `app.services`.
- [X] T009 [P] [US1] In `services/api/app/api/bookings/router.py`, extend `book_ride`: add `request: Request` and
  `background_tasks: BackgroundTasks` params (add `Request`, `BackgroundTasks` to the `fastapi` import); after
  `create_booking(...)` succeeds (before building the `JSONResponse`), call
  `background_tasks.add_task(fraud_signal_service.record_signal, event_type="booking_created",
  user_id=passenger_id, device_id=request.headers.get("x-device-id"), ip_address=request.client.host if
  request.client else None)`. `passenger_id` is already computed at the top of the handler. Import
  `fraud_signal_service` from `app.services`.

### Frontend (`apps/main`)

- [X] T010 [P] [US1] Create `apps/main/src/lib/device-id.ts` exporting `getDeviceId(): string | null` — on first
  call, reads a UUID from `localStorage` key `triplyy_device_id`; if absent, generates one with
  `crypto.randomUUID()` and persists it; guarded with `typeof window === "undefined"` (SSR) and `try/catch`
  (private browsing / storage disabled) returning `null` in either case, per research.md R5/R7 ("stable per-install
  identifier", never blocks the request when unavailable).
- [X] T011 [US1] In `apps/main/src/lib/api/auth.ts`, attach `"X-Device-Id": getDeviceId() ?? ""` (omit the header
  key entirely when `null`, don't send an empty string — mirror existing conditional-header patterns in this repo)
  to the `fetch` calls inside `verifyOtp` and `signInWithPassword`. Import `getDeviceId` from `../device-id`.
  Depends on: T010.
- [X] T012 [P] [US1] In `apps/main/src/lib/api/rides.ts`, attach the same `X-Device-Id` header to the `fetch` call
  inside `createRide`. Depends on: T010.
- [X] T013 [P] [US1] In `apps/main/src/app/(passenger)/rides/[id]/page.tsx`, attach the same `X-Device-Id` header
  to the inline `postBooking` function's `fetch(...)` call (~line 575). Depends on: T010.

**Checkpoint**: Run quickstart.md Scenarios 1-5 against the local stack — signup/login/ride-post/booking each
produce a row, hashes match across accounts sharing a device/IP, no raw value is ever stored, missing device header
never blocks the request.

---

## Phase 4: User Story 2 - Signal capture never degrades the request it instruments (Priority: P2)

**Goal**: Confirm the instrumentation added in US1 truly never blocks, slows, or fails the four requests it rides
on — this phase is verification of a property already built into US1's design (`BackgroundTasks` +
`record_signal`'s own `try/except`), not new application code.

**Independent Test**: Break the signal-store write path and confirm the four instrumented endpoints still succeed
normally (quickstart.md Scenario 6).

- [X] T014 [US2] Code-review `fraud_signal_service.record_signal` (T005) and all four call sites (T006-T009):
  confirm the DB write is fully inside the `try/except`, confirm no handler `await`s the background task or
  otherwise blocks on its completion before returning its response (the `background_tasks.add_task(...)` call
  itself must be fire-and-forget, matching `match_logging_service.persist_match_events`'s call sites in
  `search/router.py`). Confirmed: all four sites call `background_tasks.add_task(...)` (never `await
  record_signal(...)` directly), and `record_signal`'s entire body — including the `INSERT` — is wrapped in one
  `try/except Exception`.
- [X] T015 [US2] Manually execute quickstart.md Scenario 6 against the local stack: temporarily break the
  `fraud_signals` write path (e.g. rename the table), repeat a signup, confirm the request still returns 200/201
  normally with no `fraud_signals` row created and a `fraud_signal_persist_failure` line in the API logs; restore
  the table afterward. Confirmed: renamed the table, ran signup — API returned `200` with a full valid session,
  logs showed `{"event": "fraud_signal_persist_failure", "event_type": "signup", "error": "relation
  \"fraud_signals\" does not exist"}`, row count unaffected after restoring the table.

**Checkpoint**: Both user stories verified independently.

---

## Phase 5: Polish

- [X] T016 Run quickstart.md Scenarios 1, 2, 3, 4, 5, and 7 end-to-end against the local Docker stack (Scenario 6
  covered by T015) and confirm all pass as documented. Results:
  - **Scenario 1** ✅ signup produced a row with non-null distinct `hashed_device_id`/`hashed_ip` and the correct
    `user_id`.
  - **Scenario 2** ✅ for `login` (full runtime pass); `ride_posted`/`booking_created` confirmed by code review only
    — local dev has no OSRM instance configured, so `POST /api/v1/rides` 503s before reaching any application code
    (pre-existing environment gap, unrelated to this feature); `create_ride`/`book_ride`'s `record_signal` call
    sites were verified correct by inspection (same `user_id`-from-dict pattern as the working `login`/`signup`
    sites, no attribute-access risk).
  - **Scenario 3** ✅ two accounts signed up with the identical `X-Device-Id` produced identical `hashed_device_id`
    (and `hashed_ip`) values.
  - **Scenario 4** ✅ zero rows matched a `LIKE '%qa-raw-value-check%'` search across both hash columns.
  - **Scenario 5** ✅ a signup with no `X-Device-Id` header succeeded normally with `hashed_device_id IS NULL` and
    `hashed_ip` populated.
  - **Scenario 7** ✅ confirmed by diff — the only changes to all three routers are added parameters, added
    imports, and the inserted `background_tasks.add_task(...)` calls; no `return`/response-body statement changed,
    so response shape is byte-identical with or without the new header, matching Scenario 6's live proof that the
    normal response is unaffected even when signal persistence fails outright.

---

## Dependencies & Execution Order

- **Setup (T001)**: No dependencies.
- **Foundational (T002-T005)**: T002/T003/T004 have no dependencies on each other or T001 and can run in parallel;
  T005 depends on T001 (schema) and T002 (settings field). Phase 2 as a whole blocks Phase 3.
- **US1 (T006-T013)**: All depend on T005. Backend: T006 and T007 share a file (sequential); T008 and T009 are
  each in their own file and parallel-safe with T006/T007 and each other. Frontend: T010 has no backend
  dependency and can start any time; T011/T012/T013 each depend on T010 but are parallel-safe with each other
  (three different files).
- **US2 (T014-T015)**: Depend on US1 being complete (nothing to verify otherwise).
- **Polish (T016)**: Depends on US1 and US2 both complete.

## Parallel Example: Phase 2 + Phase 3

```bash
# Phase 2, once T001/T002 land:
Task: "Add FRAUD_SIGNAL_HMAC_SECRET line to services/api/.env.example"
Task: "Set a real FRAUD_SIGNAL_HMAC_SECRET value in local services/api/.env"

# Phase 3, once T005 lands:
Task: "Extend create_ride in services/api/app/api/rides/router.py"
Task: "Extend book_ride in services/api/app/api/bookings/router.py"
Task: "Create apps/main/src/lib/device-id.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (T001) → Phase 2 (T002-T005) → Phase 3 (T006-T013).
2. **STOP and VALIDATE**: run quickstart.md Scenarios 1-5.
3. This alone closes the roadmap's data-collection gap #3 — US2 only hardens confidence in a property the
   `BackgroundTasks` design already provides.

### Incremental Delivery

1. Setup + Foundational → schema and service ready.
2. US1 → signal capture live on all four request paths → validate → this is the deliverable the roadmap needs.
3. US2 → resilience verification (no new code expected to be needed if T005/T006-T009 were built correctly).
4. Polish → full quickstart pass.

---

## Notes

- No `services/ai` changes (spec Out-of-Scope: modeling is a separate, later roadmap item).
- No admin/passenger/driver UI changes anywhere in this task list (spec Out-of-Scope).
- Google OAuth sign-in remains an undetected "login" event (research.md R6) — no task addresses this; it's a
  documented gap, not a bug.
- Commit after each phase checkpoint.
