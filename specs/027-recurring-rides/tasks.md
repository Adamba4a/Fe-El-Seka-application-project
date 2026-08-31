---

description: "Task list for Recurring Rides implementation"
---

# Tasks: Recurring Rides

**Input**: Design documents from `specs/027-recurring-rides/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/recurring-rides-api.md, quickstart.md

**Tests**: No dedicated automated API test suite exists in this repo (per plan.md Technical Context — no OSRM locally) — validation is via the `quickstart.md` direct-service-layer scenarios, referenced as dedicated tasks at the end of each story.

**Organization**: Tasks are grouped by user story (from spec.md) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US3)
- File paths are relative to the repository root (`D:\Business\Fe El Seka app`)

## Path Conventions

Per plan.md Project Structure: `services/api/app/{models,services,api}` (FastAPI backend), `apps/main/src` (single passenger+driver frontend), `supabase/migrations/` (schema).

---

## Phase 1: Setup

**Purpose**: Confirm environment readiness — no new dependencies are required for this feature.

- [X] T001 Verify Technical Context per plan.md: no new Python or Node packages are needed (existing FastAPI/asyncpg/Pydantic v2 and Next.js 14/Tailwind/shadcn stack covers this feature); confirm the local Supabase stack and `services/api` (`uvicorn`) start cleanly per `quickstart.md` prerequisites.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema and shared model changes every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Write migration `supabase/migrations/<timestamp>_recurring_ride_definitions.sql` per `data-model.md`: `CREATE TYPE recurring_definition_status AS ENUM ('active','ended')`; `CREATE TABLE recurring_ride_definitions` with all columns from data-model.md (`id, driver_id, vehicle_id, origin_coordinates, origin_address, destination_coordinates, destination_address, departure_time, weekdays smallint[], total_seats, price_per_seat, notes, status, created_at, updated_at`) plus `CHECK (array_length(weekdays, 1) > 0)` (FR-002); `ALTER TABLE rides ADD COLUMN recurring_ride_definition_id uuid NULL REFERENCES recurring_ride_definitions(id) ON DELETE SET NULL`; a partial unique index `uq_rides_recurring_instance_per_date ON rides (recurring_ride_definition_id, (departure_datetime::date)) WHERE recurring_ride_definition_id IS NOT NULL` (idempotent generation, NFR-001); RLS policy `driver_read_own_recurring_definitions` mirroring `driver_read_own_rides`.
- [X] T003 Apply the migration from T002 to the local Supabase stack and verify the new type/table/column/index/RLS policy all exist as expected.
- [X] T004 [P] Create `services/api/app/models/recurring_ride.py`: `RecurringRideDefinitionCreateRequest`, `RecurringRideDefinitionResponse`, `RecurringRideDefinitionUpdateRequest`, `RecurringRideDefinitionDetailResponse` (definition + instances) per `contracts/recurring-rides-api.md`.

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Driver Defines a Recurring Ride (Priority: P1) 🎯 MVP

**Goal**: A driver defines one recurring ride (route + selected weekdays + departure time + seat count) and the system generates bookable day instances for a rolling forward window without the driver re-posting.

**Independent Test**: Driver creates a recurring ride definition selecting 2+ days of the week; confirm a bookable day instance exists on each of the next occurrences of those selected days, and that a repeat generation tick does not create duplicates.

### Implementation for User Story 1

- [X] T005 [US1] Implement `create_definition` in new `services/api/app/services/recurring_ride_service.py`: reject empty `weekdays` (FR-002, `400`), apply the same driver-eligibility checks `ride_service.create_ride` already uses (FR-010, `403` if ineligible), insert a `recurring_ride_definitions` row with `status='active'`.
- [X] T006 [US1] Implement `generate_upcoming_instances` in `recurring_ride_service.py`: for each `active` definition whose driver/vehicle is currently eligible, for each selected weekday, ensure a `rides` row exists for every occurrence within the rolling 2-week window (research.md Decision 2) that doesn't already have one; for each newly-created row compute OSRM route data (research.md Decision 4), copy `total_seats`/`price_per_seat`/`notes` from the definition, set `recurring_ride_definition_id`, insert with `status='scheduled'`; rely on the T002 unique index as an idempotency backstop (NFR-001).
- [X] T007 [US1] Implement `edit_definition` in `recurring_ride_service.py` (FR-011): update the definition's route/`departure_time`/`total_seats`/`price_per_seat`/`notes`; propagate the new values to not-yet-generated future instances (nothing to do, they don't exist yet) and to already-generated instances with zero confirmed bookings that haven't passed the existing ride-edit cutoff window; leave instances with ≥1 confirmed booking untouched; `403` if the definition is `ended`.
- [X] T008 [US1] Implement `list_definitions` and `get_definition` (definition + its generated instances) in `recurring_ride_service.py` per `contracts/recurring-rides-api.md` GET endpoints.
- [X] T009 [US1] Create `services/api/app/api/rides/recurring_router.py`: `POST /rides/recurring` (T005), `GET /rides/recurring` (T008), `GET /rides/recurring/{definition_id}` (T008), `PATCH /rides/recurring/{definition_id}` (T007), each behind the existing driver auth dependency.
- [X] T010 [US1] Mount `recurring_router` in `services/api/app/main.py`; start `recurring_ride_generation_loop()` via `asyncio.create_task(...)` alongside the existing background loops (`driver_reminder_loop`, `booking_expiry_loop`, etc.), calling T006 on a fixed interval.
- [X] T011 [P] [US1] Enforce FR-012 eligibility-based visibility/bookability for recurring instances. Actual scope was broader than originally described (search/listing lives outside `ride_service.py`, and "unbookable" requires its own gate): added shared helpers `recurring_instance_visibility_sql()` + `is_driver_vehicle_eligible()` to `services/api/app/services/ride_service.py`; applied the visibility SQL fragment to `services/api/app/services/candidate_service.py`'s `_stage1_query` (passenger `POST /search/rides`) and `services/api/app/api/search/router.py`'s `GET /search/nearby`; applied the single-row eligibility check as a booking-time gate in `services/api/app/services/booking_service.py`'s `create_booking` (422 `ride_not_schedulable` for a zero-booking ineligible instance). One-off rides and any instance with ≥1 confirmed booking are unaffected.
- [X] T012 [P] [US1] Add a "Recurring" mode toggle to the driver ride-creation flow in `apps/main/src/app/(driver)/rides/new/`, posting to `POST /rides/recurring` (T009) when selected.
- [X] T013 [P] [US1] Add driver UI `apps/main/src/app/(driver)/rides/recurring/`: list of the driver's recurring definitions, a detail page showing its generated instances grouped/labeled as belonging to the series (FR-009 driver side), and an edit form calling `PATCH /rides/recurring/{id}` (T009).
- [X] T014 [US1] Run `quickstart.md` Scenario 1 (definition generates instances, idempotent regeneration) and Scenario 4 (edit propagation, eligibility lapse/restore) end-to-end; confirm all pass conditions.

**Checkpoint**: User Story 1 is fully functional and testable independently — recurring definitions generate, edit, and hide/reveal instances correctly.

---

## Phase 4: User Story 2 - Passenger Books a Single Day Instance (Priority: P1)

**Goal**: A passenger searches for and books a specific day instance of a recurring ride through the exact same search/booking flow used for a one-off ride.

**Independent Test**: Search for rides on a date matching one of a recurring ride's active days; confirm that day's instance appears in results and can be booked exactly as a one-off ride, independently of any other day's instance.

### Implementation for User Story 2

- [X] T015 [US2] Extend the passenger-facing ride detail view (existing route under `apps/main/src/app/(passenger)/rides/[id]/`) to show a "part of a recurring series" indicator plus the definition's other active days when `ride.recurring_ride_definition_id` is set (FR-009 passenger side) — read-only, does not alter the booking action.
- [X] T016 [US2] Verify the existing `GET /rides` search endpoint and `create_booking` flow require zero code changes for generated instances (FR-004/FR-005) — they are plain `rides` rows already covered by every existing query/mutation; confirm via a direct service-layer check, no code change expected beyond T011's ineligibility filter.
- [X] T017 [US2] Run `quickstart.md` Scenario 2 end-to-end; confirm a generated instance is searchable and bookable via the unmodified flow, and that booking one day instance does not affect a sibling day instance's seat availability.

**Checkpoint**: User Stories 1 AND 2 both work independently — passengers can find and book specific day instances.

---

## Phase 5: User Story 3 - Driver Cancels a Single Day's Instance (Priority: P1)

**Goal**: A driver cancels one specific day's instance via the existing cancellation mechanism without ending the recurring series; ending the series only stops future generation and never cancels already-generated instances.

**Independent Test**: Cancel one specific day's instance of a recurring ride with other upcoming instances; confirm that instance shows as cancelled with normal cancellation consequences while the series keeps generating for its other selected days/weeks; then end the series and confirm no further instances generate while all existing instances remain untouched.

### Implementation for User Story 3

- [X] T018 [US3] Implement `end_definition` in `recurring_ride_service.py` (FR-008): set `status='ended'`; idempotent — ending an already-ended definition is a no-op returning the current state; no mutation of any existing `rides` row.
- [X] T019 [US3] Add `POST /rides/recurring/{definition_id}/end` to `recurring_router.py` (T018).
- [X] T020 [US3] Verify the existing `POST /rides/{ride_id}/cancel` endpoint requires zero code changes when called directly on a generated instance's `ride_id` (FR-006/FR-007) — cancellation consequences and next-occurrence regeneration on the following loop tick already work unchanged since the instance is a plain `rides` row; confirm via `quickstart.md`.
- [X] T021 [P] [US3] Add an "End recurring series" action to the driver recurring-definition detail UI (`apps/main/src/app/(driver)/rides/recurring/`, from T013), calling T019; single-instance cancellation reuses the existing one-off ride cancel action already present on each instance's ride row.
- [X] T022 [US3] Run `quickstart.md` Scenario 3 end-to-end; confirm all pass conditions (cancellation isolated to one instance, weekday keeps regenerating, ending the series stops only future generation).

**Checkpoint**: All user stories are independently functional — the full recurring-rides feature works end-to-end.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T023 [P] Verify `recurring_ride_definitions` RLS policy (`driver_read_own_recurring_definitions`) matches the `rides.driver_read_own_rides` pattern via the Supabase dashboard or a direct SQL check, per `data-model.md`.
- [ ] T024 Run the full `quickstart.md` validation suite (all 4 scenarios) end-to-end against the local stack in one pass.
- [ ] T025 Confirm CI checks (typecheck/build/lint) pass for the `services/api` and `apps/main` changes.
- [ ] T026 [P] Add any new user-facing strings (recurring-mode toggle, recurring list/detail/edit UI, series indicator, "end series" action) to the message catalog (`en.json`/`ar.json`) and republish via `services/api/scripts/publish_message_catalog.py` before considering the UI text live.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion.
  - US1 must land first in practice (it produces the generation loop and definitions that US2/US3 act on), but is architecturally independent per Spec Kit convention — US2 and US3 assume US1's generated instances exist as test fixtures, not as a code dependency.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2). No dependencies on other stories.
- **User Story 2 (P2)**: Can start after Foundational (Phase 2); its independent test needs a generated instance to exist, which in practice means running after US1, but touches no US1 code.
- **User Story 3 (P1)**: Can start after Foundational (Phase 2); likewise needs a generated instance/definition to exist for its independent test, but its endpoints (T018/T019) and the reused `cancel_ride` path (T020) touch no US1/US2 code.

### Within Each User Story

- Services before endpoints; endpoints before UI; UI before the `quickstart.md` validation task.
- Story complete before moving to the next priority.

### Parallel Opportunities

- T004 (Foundational Pydantic models) can run in parallel with T002/T003 review, though T003 (apply migration) should land before any service code that queries the new table is exercised.
- T011, T012, T013 (US1) touch different files and can run in parallel once T005–T010 land.
- T021 (US3 UI) can run in parallel with T018–T020 (backend).
- T023 and T026 (Polish) can run in parallel with each other.

---

## Parallel Example: User Story 1

```bash
# Once T005-T010 are done, launch these together (different files):
Task: "Extend ride search query to filter ineligible-driver unbooked instances in services/api/app/services/ride_service.py"
Task: "Add Recurring mode toggle in apps/main/src/app/(driver)/rides/new/"
Task: "Add recurring definition list/detail/edit UI in apps/main/src/app/(driver)/rides/recurring/"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: Run `quickstart.md` Scenarios 1 and 4 independently.
5. Deploy/demo if ready — drivers can already define recurring rides and have instances auto-generate, even before passenger-facing indicators (US2) or single-day cancellation UI (US3) exist, since generated instances are already searchable/bookable/cancellable through pre-existing one-off-ride code paths.

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready.
2. Add User Story 1 → validate → deploy/demo (MVP!).
3. Add User Story 2 → validate → deploy/demo (adds the passenger-facing series indicator).
4. Add User Story 3 → validate → deploy/demo (adds explicit single-day/end-series driver UI).
5. Each story adds value without breaking previous stories.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- Because day instances reuse the existing `rides`/booking/cancellation code paths untouched (per plan.md Decision 3), US2 and US3 are mostly UI-indicator and end-of-series work — the heavy lifting is in US1's generation service and loop.
- Commit after each task or logical group.
- Stop at any checkpoint to validate story independently.
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence.
