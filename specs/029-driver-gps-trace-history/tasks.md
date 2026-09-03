# Tasks: Driver GPS Trace History

**Input**: Design documents from `specs/029-driver-gps-trace-history/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/data-schema.md, quickstart.md

**Tests**: Not requested in the feature specification — no test tasks generated. Validation is via
`quickstart.md`'s manual scenarios (Polish phase).

**Organization**: Tasks are grouped by user story (US1 = P1, US2 = P2) per spec.md, enabling US1 to
ship as a standalone MVP before US2's retention job is added.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- File paths are exact — this is a small, single-service backend change (`services/api` only).

---

## Phase 1: Setup

**Purpose**: Create the new table this entire feature is built on.

- [X] T001 Create migration `supabase/migrations/20260903000001_driver_gps_trace_history.sql`: `driver_location_history` table (`id` UUID PK `gen_random_uuid()`, `ride_id` UUID NOT NULL FK→`rides(id)` ON DELETE CASCADE, `driver_id` UUID NOT NULL FK→`profiles(id)` ON DELETE CASCADE, `location` `geometry(Point,4326)` NOT NULL, `recorded_at` TIMESTAMPTZ NOT NULL, `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()); indexes on `(ride_id, recorded_at)` and `(recorded_at)`; `ALTER TABLE driver_location_history ENABLE ROW LEVEL SECURITY;` with no policies (service-role only, per data-model.md)
- [X] T002 Apply the migration locally (`supabase db reset` or `supabase migration up`) and confirm `driver_location_history` exists with the expected columns/indexes/RLS via `psql`/Supabase Studio

**Checkpoint**: Table exists locally, ready for the service layer.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared module both user stories add functions to.

**⚠️ CRITICAL**: Must be complete before Phase 3 or Phase 4 begin.

- [X] T003 Create `services/api/app/services/location_history_service.py` with module logger and imports (`asyncpg`, `uuid`, `datetime`, `asyncio`, `logging`), mirroring the header shape of `services/api/app/services/retraining_scheduler_service.py` and `match_logging_service.py` — no functions yet, just the module scaffold both stories below extend.

**Checkpoint**: Service module exists — US1 and US2 implementation tasks can proceed.

---

## Phase 3: User Story 1 - Every location ping during an active ride is preserved (Priority: P1) 🎯 MVP

**Goal**: Every GPS ping sent during an active ride is appended to `driver_location_history`, in
addition to the existing `driver_locations` upsert, without ever blocking or failing that upsert.

**Independent Test**: Send a sequence of location pings for one active ride, then query
`driver_location_history` directly. Confirm one row exists per ping received, in order, distinct from
the single current-position row in `driver_locations` (spec.md Independent Test; quickstart.md
Scenario 1).

### Implementation for User Story 1

- [X] T004 [US1] Implement `record_ping(pool, ride_id: uuid.UUID, driver_id: uuid.UUID, lat: float, lng: float, recorded_at: datetime) -> None` in `services/api/app/services/location_history_service.py`: acquires its own connection from the pool, runs a single `INSERT INTO driver_location_history (ride_id, driver_id, location, recorded_at) VALUES ($1, $2, ST_SetSRID(ST_MakePoint($4,$3),4326), $5)`, wraps the whole body in try/except that only logs on failure (never raises) — mirrors `match_logging_service.persist_match_events` exactly (research.md R2)
- [X] T005 [US1] In `services/api/app/api/rides/router.py`'s `update_driver_location` handler, after `location_service.upsert_location(...)` succeeds inside the `async with pool.acquire() as conn:` block, add `asyncio.create_task(location_history_service.record_ping(pool, ride_id, driver_id, payload.lat, payload.lng, payload.client_timestamp))` using the pool (not the request's `conn`, which closes when the `async with` block exits) — not awaited, so the response returns immediately; add the corresponding `from app.services import location_history_service` import and confirm `import asyncio` is present

**Checkpoint**: Run quickstart.md Scenarios 1–3 and 5 to confirm US1 works standalone — every ping is preserved, ordered, and non-blocking, with no change to the `POST /{ride_id}/location` response shape.

---

## Phase 4: User Story 2 - History older than 30 days is automatically removed (Priority: P2)

**Goal**: A recurring job permanently deletes `driver_location_history` rows older than a rolling
30-day window, idempotently, regardless of whether a prior run was missed.

**Independent Test**: Insert history rows with a `recorded_at` older than 30 days, run the retention
job, and confirm those rows are deleted while rows within the last 30 days remain (spec.md Independent
Test; quickstart.md Scenario 4).

### Implementation for User Story 2

- [X] T006 [US2] Implement `purge_expired(pool) -> int` in `services/api/app/services/location_history_service.py`: runs `DELETE FROM driver_location_history WHERE recorded_at < now() - interval '30 days'`, returns the deleted row count, wrapped in try/except that logs and returns `0` on failure (never raises) — depends on T003
- [X] T007 [US2] Implement `location_history_retention_loop(pool)` in `services/api/app/services/location_history_service.py`: `while True: try: deleted = await purge_expired(pool); log deleted count except Exception: log.exception(...); await asyncio.sleep(86400)` — mirrors `retraining_scheduler_service.retraining_scheduler_loop` exactly (research.md R3) — depends on T006
- [X] T008 [US2] In `services/api/app/main.py`'s `lifespan`, add `location_history_retention_task = asyncio.create_task(location_history_service.location_history_retention_loop(pool))` alongside the existing 12 background-loop registrations, and `location_history_retention_task.cancel()` in the shutdown sequence before `await close_pool()`; add the `from app.services.location_history_service import location_history_retention_loop` import — depends on T007

**Checkpoint**: Run quickstart.md Scenario 4 to confirm the retention job purges correctly and is
idempotent (NFR-003) — both user stories now work together end-to-end.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across both stories.

- [X] T009 Run quickstart.md Scenarios 1–5 end-to-end against the local stack (not just per-story spot checks) and confirm all pass — validated directly against the local Postgres container (see implementation notes below); all 5 pass.
- [X] T010 [P] Update `docs/implementation-roadmap.md`'s "2026-09-03 Data-Collection Audit" entry for gap #1 — unblocked by merging `028-loyalty-points` into `main` (which brought the audit section onto this branch); gap #1 now marked closed by this feature.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup (T001/T002) — creates the shared service module file.
- **User Story 1 (Phase 3)**: Depends on Foundational (T003) and the table from Setup (T001/T002). No dependency on User Story 2.
- **User Story 2 (Phase 4)**: Depends on Foundational (T003) and the table from Setup (T001/T002). No dependency on User Story 1 — can be built and tested independently, though both stories edit the same service-module file so should not be worked on concurrently by two people without coordination.
- **Polish (Phase 5)**: Depends on both User Story 1 and User Story 2 being complete.

### Within Each User Story

- T004 before T005 (the router call site needs `record_ping` to exist).
- T006 before T007 before T008 (each layer calls the one before it).

### Parallel Opportunities

- T001 and T003 touch different files (migration vs. service module) and have no functional
  dependency on each other, but T002 (verifying the migration) should follow T001.
- T010 (documentation) can run in parallel with T009 (manual validation) — different files, no
  dependency.
- User Stories 1 and 2 are logically independent (per spec.md) but both add functions to the same
  `location_history_service.py` file, so sequential implementation (as ordered above, US1 then US2) is
  recommended over parallel work on the same file.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002).
2. Complete Phase 2: Foundational (T003).
3. Complete Phase 3: User Story 1 (T004–T005).
4. **STOP and VALIDATE**: Run quickstart.md Scenarios 1–3 and 5.
5. This alone closes the "unrecoverable once overwritten" problem from the Business Objective — every
   ping from this point forward is preserved, even before retention (US2) exists.

### Incremental Delivery

1. Setup + Foundational → table and service module ready.
2. Add User Story 1 → validate independently → this is the MVP; data collection has already started.
3. Add User Story 2 → validate independently → storage growth is now bounded and PDPL-conscious.
4. Polish → full quickstart pass + roadmap doc update.

---

## Notes

- No tests were requested for this feature (see Tests note above); validation is manual via
  quickstart.md, per Success Criteria SC-001–SC-004 in spec.md.
- Commit after each task or logical group, consistent with prior specs in this repo.
- Per the sequential-planning approach agreed for specs 029/030, do not begin any of these tasks
  without a separate, explicit user go-ahead for implementation.
