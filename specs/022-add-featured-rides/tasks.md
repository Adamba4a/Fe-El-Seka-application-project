# Tasks: Featured Rides

**Input**: Design documents from `specs/022-add-featured-rides/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Not explicitly requested in the spec; the quickstart.md "Automated coverage" section documents expected pytest targets, so unit/integration test tasks are included as part of each backend story (not as a separate mandatory TDD gate — implementation tasks are not blocked on writing tests first).

**Organization**: Tasks are grouped by user story (matching spec.md's P1/P2/P3) to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact and repo-relative

## Path Conventions

- Backend: `services/api/app/...`, `services/api/tests/...`
- Passenger app: `apps/main/src/...`
- Admin app: `apps/admin/src/...`
- Migrations: `supabase/migrations/...`

---

## Phase 1: Setup

- [X] T001 [P] Verify local dev stack runs cleanly with no new dependencies required: local Supabase, `services/api` (uvicorn), `apps/main` and `apps/admin` (`pnpm dev`). No package.json/pyproject.toml changes are needed for this feature.

**Checkpoint**: Dev environment confirmed ready; no new tooling to install.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema changes required by every user story (both the passenger read in US1 and the admin write in US2 depend on the `rides` columns added here).

- [X] T002 Create migration `supabase/migrations/20260825000001_add_featured_rides.sql`: add `rides.is_featured boolean not null default false`, `rides.featured_at timestamptz`, `rides.featured_by uuid references profiles(id)`; add partial index `idx_rides_featured_upcoming` on `rides (departure_datetime) WHERE is_featured = true AND status = 'scheduled'`. Apply the migration to the local Supabase instance and verify the three columns and index exist (per data-model.md, quickstart.md step 1). ✅ Applied to local Supabase (`supabase migration up`) and verified 2026-08-25: `is_featured`/`featured_at`/`featured_by` columns and `idx_rides_featured_upcoming` confirmed via `\d rides`; `GET /api/v1/rides/featured` smoke-tested against the live local DB (401 for unauthenticated, no 500). Not yet applied to remote.

**Checkpoint**: `rides` table extended — both US1 (read) and US2 (write) can now proceed independently and in parallel.

---

## Phase 3: User Story 1 - Passenger discovers a Featured ride (Priority: P1) 🎯 MVP

**Goal**: The passenger find-a-ride landing page shows currently bookable Featured rides, computed fresh on load, and tapping one opens the existing ride detail/booking screen unchanged.

**Independent Test**: Seed a ride with `is_featured = true` directly via SQL (no admin UI needed yet), load the passenger landing page, confirm it appears with correct route/time/price/seats and disappears once it stops being eligible (full, cancelled, or departed) or is unfeatured via SQL.

### Implementation

- [X] T003 [P] [US1] Add `FeaturedRideItem` and `FeaturedRidesResponse` pydantic models to `services/api/app/models/ride.py`, matching the shape in `contracts/passenger-rides-featured.md` (`ride_id`, `origin_address`, `destination_address`, `departure_datetime`, `price_per_seat`, `available_seats`).
- [X] T004 [US1] Implement `list_featured_rides()` in `services/api/app/services/ride_service.py`: query `rides` where `is_featured = true AND status = 'scheduled' AND departure_datetime > now() AND available_seats > 0`, ordered by `departure_datetime ASC` (FR-004/FR-012, derived visibility rule in data-model.md). Depends on T002, T003.
- [X] T005 [US1] Add `GET /featured` route to `services/api/app/api/rides/router.py`, declared **before** the `/{ride_id}` route (per contracts/passenger-rides-featured.md, same convention as `/pending-bookings-count`), gated by `Depends(get_current_user)`, calling `ride_service.list_featured_rides()` and returning `FeaturedRidesResponse`. Depends on T004.
- [X] T006 [P] [US1] Unit tests for `list_featured_rides()` in `services/api/tests/unit/test_featured_rides.py`: covers FR-003 eligibility filter (excludes non-`scheduled`, past-departure, and zero-seat rides) and FR-012 ordering (soonest departure first). Depends on T004.
- [X] T007 [P] [US1] Integration tests for `GET /rides/featured` in `services/api/tests/integration/test_rides_featured.py`: authenticated success with results, empty-array response, 401 when unauthenticated. Depends on T005.
- [X] T008 [P] [US1] Add `fetchFeaturedRides()` to `apps/main/src/lib/api/search.ts`, calling `GET /rides/featured` and typed per the contract response shape.
- [X] T009 [US1] Create `apps/main/src/components/bookings/FeaturedRidesSection.tsx`: renders the fetched Featured rides (route, departure date/time, price, seats — FR-008), with an empty state (FR-011), and navigates to the ride's existing detail/booking screen on tap. Depends on T008. ⚠️ Deviation from the original task text: does NOT reuse `RideCard` — that component is built around the AI search-match shape (driver info, match score, walk-distance/overlap %) and doesn't even render origin/destination text, so it can't satisfy FR-008's route display without fabricating fields. Built a new lightweight card in this file instead, styled to match `AvailableRideCard`/`bookings/page.tsx` conventions.
- [X] T010 [US1] Restructure `apps/main/src/app/(passenger)/search/page.tsx` into a landing page: fetch Featured rides once on mount/navigation only (no polling, per Clarifications 2026-08-25) and render `FeaturedRidesSection` instead of opening the map/pin-drop flow immediately. Depends on T009. Implemented via a `mode: "landing" | "search"` state — the existing map/pin-drop flow (form + results) is preserved byte-for-byte in behavior under `"search"` mode for T018/US3 to wire a button into next; it is not reachable from the UI in this pass except via the pre-existing sessionStorage results-restore path, which is intentional per the phase-3-only scope.

**Checkpoint**: User Story 1 is independently functional and testable — passengers see and can open Featured rides (curated manually via SQL until US2 ships the admin UI).

---

## Phase 4: User Story 2 - Admin marks/unmarks a ride as Featured (Priority: P2)

**Goal**: An admin can toggle a ride's Featured status from the existing admin Rides UI, with eligibility enforcement and an audit trail.

**Independent Test**: As an admin, feature an eligible ride via the admin UI/API and confirm it appears in `GET /rides/featured`; attempt to feature an ineligible ride and confirm a `409 not_eligible` rejection; unfeature a ride and confirm it disappears; confirm an `admin_audit_logs` row is created for each action.

### Implementation

- [ ] T011 [P] [US2] Create migration `supabase/migrations/20260825000002_add_ride_id_to_admin_audit_logs.sql`: add nullable `admin_audit_logs.ride_id uuid references rides(id)`; drop and recreate the `action_type` CHECK constraint (currently `CHECK (action_type IN ('approved', 'rejected', 'suspended', 'reinstated', 'unlocked'))` from `20260614000004_create_admin_audit_logs.sql`) to add `'ride_featured'` and `'ride_unfeatured'` (per data-model.md). Apply to the local Supabase instance and verify.
- [ ] T012 [US2] Extend `append_log()` in `services/api/app/services/audit_service.py` to accept an optional `ride_id: str | None = None` parameter and include it in the inserted `admin_audit_logs` row when provided. Depends on T011.
- [ ] T013 [US2] Add `POST /{ride_id}/feature` and `POST /{ride_id}/unfeature` handlers to `services/api/app/api/admin/rides_router.py` (raw-SQL pattern matching existing handlers), per `contracts/admin-rides-featured.md`: `feature` enforces FR-003 eligibility (`404 not_found` / `409 not_eligible` with the specific reason), sets `is_featured`/`featured_at`/`featured_by`, and calls `audit_service.append_log(..., ride_id=ride_id, action_type="ride_featured", target_user_id=<ride's driver_id>)`; `unfeature` has no eligibility check and logs `action_type="ride_unfeatured"`. Depends on T002, T012.
- [ ] T014 [US2] Extend the `GET /` (list) and `GET /{ride_id}` (detail) SQL SELECTs and response dicts in `services/api/app/api/admin/rides_router.py` to include `is_featured`, `featured_at`, and `featured_by_display_name` (joined from `profiles`, matching the existing `driver_display_name` join pattern). Depends on T002.
- [ ] T015 [P] [US2] Integration tests for the feature/unfeature endpoints in `services/api/tests/integration/test_admin_rides_featured.py`: success responses, `404 not_found`, `409 not_eligible` (per-reason messages), and verification that an `admin_audit_logs` row is created with the correct `ride_id`/`action_type`. Depends on T013.
- [ ] T016 [P] [US2] Add `featureRide()` and `unfeatureRide()` calls to `apps/admin/src/lib/api/admin-rides.ts`, calling the two new admin endpoints.
- [ ] T017 [US2] Add a Featured indicator/toggle to `apps/admin/src/app/(dashboard)/rides/page.tsx` (list) and `apps/admin/src/app/(dashboard)/rides/[ride_id]/page.tsx` (detail), wired to T016, surfacing the `409 not_eligible` message to the admin when a toggle is rejected. Depends on T016.

**Checkpoint**: User Story 1 and User Story 2 together are fully functional — admins can curate Featured rides directly from the UI, with no manual DB edits needed.

---

## Phase 5: User Story 3 - Passenger uses "Find a Ride" button (Priority: P3)

**Goal**: The landing page's "Find a Ride" button opens today's existing pin-drop map search flow, completely unchanged.

**Independent Test**: From the landing page, tap "Find a Ride" and confirm the existing origin/destination map search opens and behaves exactly as it does today (unchanged mechanics).

### Implementation

- [ ] T018 [US3] Add a "Find a Ride" primary-action button to the landing page built in T010 (`apps/main/src/app/(passenger)/search/page.tsx`) that mounts the existing `RideSearchForm` + map + bottom-sheet combination unchanged (no logic changes to `apps/main/src/components/bookings/RideSearchForm.tsx`). Depends on T010.
- [ ] T019 [US3] Manual verification (quickstart.md step 4): confirm the pin-drop map search flow behaves identically to its pre-feature behavior after being relocated behind the "Find a Ride" button. Depends on T018.

**Checkpoint**: All three user stories are independently functional. Full feature complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T020 [P] Run the full `quickstart.md` validation end-to-end (all 6 scenarios), including the auto-drop edge case (FR-004) and empty state (FR-011).
- [ ] T021 [P] Add any new UI strings introduced (Featured section heading, empty state copy, admin toggle labels/rejection messages) to `apps/main` and `apps/admin` message catalogs (`en.json`/`ar.json`) and republish per `services/api/scripts/publish_message_catalog.py`, consistent with this repo's existing localization convention.
- [ ] T022 Run `pnpm lint` and `pnpm typecheck` for `apps/main` and `apps/admin`, and `ruff`/`mypy`/`pytest` for `services/api`.

---

## Dependencies & Execution Order

- **Setup (T001)**: No dependencies.
- **Foundational (T002)**: Depends on T001 (environment ready). Blocks all of Phase 3 and the `rides`-column-dependent tasks in Phase 4.
- **User Story 1 (T003–T010)**: Depends only on T002. Fully independent of US2/US3 — can be built, tested, and demoed on its own (Featured rides curated via SQL).
- **User Story 2 (T011–T017)**: Depends only on T002 (does not depend on US1's frontend work). Can be developed in parallel with US1 by a different engineer; the admin UI simply becomes the mechanism to set the flag that US1 already reads.
- **User Story 3 (T018–T019)**: Depends on T010 (the landing page must exist first) — this is a sequencing dependency, not a functional one; T018's actual work is minimal.
- **Polish (T020–T022)**: Depends on all prior phases being complete.

```text
Setup (T001) → Foundational (T002) ─┬─→ US1 (T003-T010) → US3 (T018-T019) ─┐
                                     └─→ US2 (T011-T017) ────────────────────┴─→ Polish (T020-T022)
```

## Parallel Example: User Story 1

```text
# After T002 (Foundational) completes:
T003 [P] Add FeaturedRideItem/FeaturedRidesResponse models
T008 [P] Add fetchFeaturedRides() to apps/main lib/api/search.ts
# T003 and T008 touch unrelated files and have no dependency on each other — run in parallel.
# T004 depends on T003; T005 depends on T004; T006/T007 depend on T005 and each other's files differ, so [P].
```

## Parallel Example: User Story 2

```text
# After T002 (Foundational) completes:
T011 [P] Create admin_audit_logs migration
T016 [P] Add featureRide()/unfeatureRide() to apps/admin lib/api/admin-rides.ts
# T011 and T016 touch unrelated files — run in parallel.
# T012 depends on T011; T013 depends on T002+T012; T014 depends only on T002 (can run alongside T012/T013).
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001).
2. Complete Phase 2: Foundational (T002) — **CRITICAL**, blocks everything else.
3. Complete Phase 3: User Story 1 (T003–T010).
4. **STOP and validate**: Seed a Featured ride via SQL, confirm it surfaces correctly on the passenger landing page and opens the correct booking screen, confirm it drops off when it becomes ineligible.
5. Deploy/demo if ready — this alone proves the passenger-facing value, even before admins have a UI to set the flag.

### Incremental Delivery

1. Setup + Foundational → US1 → **checkpoint** (passenger-visible value, SQL-curated) → US2 → **checkpoint** (admin-curated, full write path) → US3 → **checkpoint** (map search relocated behind a button) → Polish.
2. Each user-story checkpoint is independently testable and independently shippable per the Independent Test criteria stated in that phase.

### Parallel Team Strategy

With Foundational (T002) complete, US1 (T003–T010, passenger read path) and US2 (T011–T017, admin write path) have no file overlap and can be built simultaneously by two engineers; US3 (T018–T019) is a small follow-on to US1's landing page.

## Notes

- `[P]` tasks touch different files and have no unmet dependency on another incomplete task in this list.
- Each user story phase is independently completable and testable, per spec.md's Independent Test criteria.
- Commit after each task or logical group, per this repo's normal workflow.
- Avoid: vague tasks, same-file conflicts within a `[P]` group, and skipping the Foundational migration before starting story work.
