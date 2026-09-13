---

description: "Task list for Ride Auto-Completion Timeout (031)"
---

# Tasks: Ride Auto-Completion Timeout

**Input**: Design documents from `/specs/031-ride-auto-completion/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: No automated test suite exists for `ride_service.py`'s status-transition functions today (see plan.md Technical Context); validation is manual via quickstart.md, referenced as tasks below instead of new test files.

**Organization**: Tasks are grouped by user story (from spec.md) to enable independent implementation and validation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Single backend service: `services/api/app/...` (Python/FastAPI, no ORM). Migration: `supabase/migrations/...`. See plan.md's Project Structure for the full file map.

---

## Phase 1: Setup

**Purpose**: Add the schema this feature needs before any service code touches it.

- [ ] T001 Create migration `supabase/migrations/20260913000001_ride_completion_source.sql` with `ALTER TABLE rides ADD COLUMN completion_source TEXT CHECK (completion_source = ANY (ARRAY['driver'::text, 'system'::text]));` (data-model.md)
- [ ] T002 Apply the migration to the local Supabase dev stack: `docker exec -i supabase_db_fe-el-seka psql -U postgres -d postgres -f -` fed from T001's file; verify with `\d rides` that the column and CHECK constraint exist

**Checkpoint**: Column exists locally — safe for service code in later phases to write to it.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend the two functions every user story reuses, and stand up the (initially empty) sweep loop that both stories will populate. No user story can be validated end-to-end until this phase is done.

**⚠️ CRITICAL**: US1 and US2 both call `start_ride()`/`complete_ride()` and both rely on the sweep loop skeleton — none of that can be split further without duplicating code, which research.md §3 explicitly rejects.

- [ ] T003 In `services/api/app/services/ride_service.py`, add `system_started_at: Optional[datetime] = None` parameter to `start_ride()`: when provided, use it in place of `now()` for the `started_at` value in the `UPDATE`, and skip the `now() < dep` early-start guard (research.md §3)
- [ ] T004 In `services/api/app/services/ride_service.py`, add `completion_source: str = "driver"` parameter to `complete_ride()` and include it in the `UPDATE rides SET ... completion_source = $n` (data-model.md Function Signature Changes)
- [ ] T005 In `services/api/app/services/ride_service.py`, harden `start_ride()`'s `UPDATE rides SET status = 'in_progress', ... WHERE id = $1` to `WHERE id = $1 AND status = 'scheduled'`; if the query returns no row, raise `RideServiceError("ride_not_editable", "Only scheduled rides can be started.", 409)` instead of assuming success (research.md §5)
- [ ] T006 In `services/api/app/services/ride_service.py`, harden `complete_ride()`'s `UPDATE rides SET status = 'completed', ... WHERE id = $1` to `WHERE id = $1 AND status = 'in_progress'`; if the query returns no row, raise `RideServiceError("ride_not_editable", "Only in-progress rides can be completed.", 409)` instead of assuming success (research.md §5)
- [ ] T007 In `services/api/app/services/ride_service.py`, add `async def sweep_stale_rides() -> int` (empty query results for now, returns 0) and `async def ride_timeout_sweep_loop() -> None` following the exact `while True: try/except/finally: await asyncio.sleep(600)` shape of `recurring_ride_generation_loop()` (research.md §1)
- [ ] T008 In `services/api/app/main.py`, wire the new loop alongside the existing ~12 background loops: import `ride_timeout_sweep_loop`, add `ride_timeout_sweep_task = asyncio.create_task(ride_timeout_sweep_loop())` next to `recurring_generation_task` (line ~99), and `ride_timeout_sweep_task.cancel()` in the matching shutdown block (line ~103)

**Checkpoint**: App starts, new loop runs every 10 minutes and no-ops (finds nothing yet), `start_ride`/`complete_ride` behave identically to before for every existing caller (default parameter values preserve current behavior) — safe to deploy on its own with zero behavior change.

---

## Phase 3: User Story 1 - Never-started ride gets auto-completed and charged (Priority: P1) 🎯 MVP

**Goal**: A `scheduled` ride more than 2 hours past `departure_datetime` is automatically finalized to `completed`, with the driver charged for confirmed cash bookings and the reservation released.

**Independent Test**: Backdate a booked ride's `departure_datetime` by >2h, wait for a sweep tick, confirm it reaches `completed`/`system` with commission charged and reservation released (quickstart.md Scenario 1); repeat with zero bookings and confirm the quiet close-out (Scenario 2).

### Implementation for User Story 1

- [ ] T009 [US1] In `sweep_stale_rides()` (`services/api/app/services/ride_service.py`), add the never-started query: `SELECT id, driver_id, departure_datetime FROM rides WHERE status = 'scheduled' AND departure_datetime < now() - interval '2 hours'` (research.md §2)
- [ ] T010 [US1] For each row from T009, inside its own `try/except RideServiceError` (so one failure doesn't block the tick — NFR-003), call `await start_ride(ride_id, driver_id, system_started_at=departure_datetime)` then `await complete_ride(ride_id, driver_id, completion_source="system")`; log and continue on exception; increment the returned count on success
- [ ] T011 [US1] Validate against local dev per quickstart.md Scenario 1 (booked ride: charged, reservation released, booking completed, passenger notified) and Scenario 2 (unbooked ride: completed/system, reservation released, no charge, no notification)

**Checkpoint**: User Story 1 fully functional and independently testable — this alone already fixes the exact bug class that prompted this feature (recurring instances stuck `scheduled` past their date).

---

## Phase 4: User Story 2 - In-progress ride gets auto-completed (Priority: P1)

**Goal**: An `in_progress` ride left open longer than `route_duration_minutes × 2` (floor 2h) since `started_at` is automatically finalized to `completed` with the same consequences as a manual complete.

**Independent Test**: Start a ride, backdate `started_at` past its own grace window, wait for a sweep tick, confirm `completed`/`system` with normal consequences (quickstart.md Scenario 3); confirm a long-route ride within its window is left untouched (Scenario 4).

### Implementation for User Story 2

- [ ] T012 [US2] In `sweep_stale_rides()`, add the in-progress query: `SELECT id, driver_id FROM rides WHERE status = 'in_progress' AND started_at < now() - GREATEST(interval '2 hours', (COALESCE(route_duration_minutes, 0) * 2) * interval '1 minute')` (research.md §2)
- [ ] T013 [US2] For each row from T012, inside its own `try/except RideServiceError`, call `await complete_ride(ride_id, driver_id, completion_source="system")`; log and continue on exception; increment the returned count on success
- [ ] T014 [US2] Validate against local dev per quickstart.md Scenario 3 (overdue in-progress ride finalized) and Scenario 4 (long intercity route within its own grace window left `in_progress`)

**Checkpoint**: User Stories 1 and 2 both work independently and together — every stale ride, of either kind, now self-resolves.

---

## Phase 5: User Story 3 - Auto-completions are auditable (Priority: P2)

**Goal**: Every completed ride's `completion_source` correctly distinguishes a driver's manual tap from the sweep, queryable after the fact.

**Independent Test**: Auto-complete one ride via the sweep and manually complete another as a driver; query both and confirm `completion_source` differs correctly (quickstart.md Scenario 6).

### Implementation for User Story 3

- [ ] T015 [US3] Confirm the existing driver-facing "Complete ride" API route (wherever it calls `ride_service.complete_ride(...)`) passes no `completion_source` override, so the `"driver"` default from T004 applies — no code change expected, this is a verification pass over the route handler
- [ ] T016 [US3] Validate against local dev per quickstart.md Scenario 6: `SELECT completion_source, count(*) FROM rides WHERE status = 'completed' GROUP BY completion_source` shows `'system'` rows from Phase 3/4 testing and `'driver'` for a manually completed ride; pre-existing completed rides show `NULL`

**Checkpoint**: All three user stories independently functional; completion source is fully auditable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the guard rails that protect every story above.

- [ ] T017 Validate the concurrency guard per quickstart.md Scenario 5: backdate a ride, cancel it as the driver moments before a sweep tick, confirm the sweep's `start_ride`/`complete_ride` calls raise `RideServiceError` (caught by the per-ride try/except from T010/T013) rather than resurrecting or corrupting the already-cancelled ride
- [ ] T018 Review `sweep_stale_rides()` log output (from T007/T010/T013) over a few real ticks against local dev to confirm the `completed=%d` count line only appears when work was actually done, matching the quiet-tick behavior of `recurring_ride_generation_loop()`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (column must exist before `complete_ride` writes to it) — BLOCKS both user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — no dependency on US2/US3
- **User Story 2 (Phase 4)**: Depends on Foundational — no dependency on US1/US3 (can be built in parallel with Phase 3 by a second developer, since both only add a branch inside the shared `sweep_stale_rides()`, in different query blocks)
- **User Story 3 (Phase 5)**: Depends on Foundational (T004) and benefits from Phase 3/4 having produced at least one system-completed ride to verify against, but adds no new production code of its own
- **Polish (Phase 6)**: Depends on Phase 3 and Phase 4 both being done (needs real sweep behavior to validate against)

### Parallel Opportunities

- T001/T002 have no parallel counterpart (single migration file, single apply step)
- T003–T006 touch the same file (`ride_service.py`) sequentially; T007/T008 touch different files and could run in parallel with each other but not with T003–T006 (T007's loop calls the function T003–T006 modify)
- Once Phase 2 is complete, Phase 3 (T009–T011) and Phase 4 (T012–T014) touch the same function (`sweep_stale_rides()`) in different query blocks — coordinate to avoid merge conflicts if worked on simultaneously; otherwise do them sequentially (P1 → P1, in either order)
- Phase 5 has no code dependency conflicts with Phase 3/4 and can start as soon as Foundational lands, though its validation (T016) is more meaningful after Phase 3/4 exist

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (migration) + Phase 2 (foundational extensions + empty loop)
2. Complete Phase 3 (User Story 1 — never-started rides)
3. **STOP and VALIDATE**: run quickstart.md Scenarios 1 and 2 against local dev
4. This alone already fixes the bug class that motivated this feature (stale unbooked `scheduled` instances) — Phase 4 (in-progress timeout) can follow as a fast-follow increment

### Incremental Delivery

1. Setup + Foundational → app runs with the new loop as a no-op, zero behavior change for existing flows
2. Add User Story 1 → validate → this is the MVP
3. Add User Story 2 → validate → both timeout paths now live
4. Add User Story 3 → validate → auditability confirmed
5. Phase 6 polish → concurrency guard and logging confirmed under real conditions

---

## Notes

- No new tests directory tasks — this codebase has no existing automated tests for `ride_service.py`'s transition functions; validation is the manual quickstart.md walkthrough referenced above.
- Do not start Phase 2 before Phase 1's migration is applied locally — `complete_ride()`'s `UPDATE` will fail against a database missing the `completion_source` column.
- Per project convention, do not apply the Phase 1 migration to prod during this implementation pass — that is a separate, explicit deploy step.
