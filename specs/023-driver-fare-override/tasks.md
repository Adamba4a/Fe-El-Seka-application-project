---

description: "Task list for Driver Fare Override (Capped)"
---

# Tasks: Driver Fare Override (Capped)

**Input**: Design documents from `/specs/023-driver-fare-override/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rides-api.md, quickstart.md

**Tests**: Included — the codebase has an established pytest suite (`services/api/tests/unit/`,
`services/api/tests/integration/`) and the constitution's Quality Standards require all implementations
to be testable, so each user story includes matching test tasks.

**Organization**: Tasks are grouped by user story (spec.md priorities) so each can be implemented and
validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to spec.md's user stories — US1 (driver sets price at creation), US2 (out-of-band
  rejection), US3 (driver adjusts price on edit), US4 (admin visibility)

## Path Conventions

Backend-only feature (see plan.md Structure Decision). All paths are under `services/api/`, plus one
migration under `supabase/migrations/`.

---

## Phase 1: Setup

**Purpose**: The one piece of shared infrastructure every story needs before any code change: the new
column.

- [X] T001 Create migration `supabase/migrations/<timestamp>_add_fair_price_per_seat.sql` adding
      `rides.fair_price_per_seat NUMERIC(10,2)`, backfilling it from `price_per_seat` for existing rows,
      then setting it `NOT NULL` (data-model.md §Migration — three-step pattern for a safe NOT NULL add)

**Checkpoint**: Migration file exists, ready to apply.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core changes every user story phase below depends on — the pricing helper, the new
request/response fields, and the column being live in the local DB.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Apply migration T001 to the local Supabase stack (`supabase db reset` or equivalent per
      project convention) and confirm `rides.fair_price_per_seat` exists and is backfilled
- [X] T003 [P] Add `MAX_MARKUP_RATE = 0.30` and `calculate_max_price(fair_price_per_seat)` helper to
      `services/api/app/services/pricing_service.py`; add `max_price_per_seat_egp` field to
      `FareEstimateResponse` in `services/api/app/models/route.py`, populated in `calculate_fare`
      (research.md §1)
- [X] T004 [P] Add `final_price_per_seat: Optional[float] = None` to `CreateRideRequest` and
      `EditRideRequest` in `services/api/app/models/ride.py`; add `fair_price_per_seat: str` to
      `RideResponse` (contracts/rides-api.md)
- [X] T005 Add `fair_price_per_seat` to `_RIDE_COLS` and `_to_response` in
      `services/api/app/services/ride_service.py` so every ride read (list/detail/create/edit response)
      includes it

**Checkpoint**: Column live, helper available, models updated — user story implementation can now begin.

---

## Phase 3: User Story 1 - Driver sets a price when creating a ride (Priority: P1) 🎯 MVP

**Goal**: A driver creating a ride sees the fair price and max price, and can publish at any price in
that range (or omit it and default to the fair price).

**Independent Test**: `POST /api/v1/rides` with no `final_price_per_seat` → ride's `price_per_seat`
equals `fair_price_per_seat`. `POST /api/v1/rides` with a mid-range `final_price_per_seat` → ride is
created with that exact price, `fair_price_per_seat` also present and correct.

### Tests for User Story 1

- [X] T006 [P] [US1] Unit test `calculate_max_price` (rounding matches fair-price convention, several
      fair-price values) in `services/api/tests/unit/test_pricing_service.py`
- [X] T007 [P] [US1] Integration test: create ride with no price → defaults to fair price; create ride
      with mid-band price → persisted exactly; response includes both `fair_price_per_seat` and
      `price_per_seat` in `services/api/tests/integration/test_rides_fare_override.py`

### Implementation for User Story 1

- [X] T008 [US1] Update `ride_service.create_ride` in `services/api/app/services/ride_service.py` to
      accept a driver-chosen final price, default it to the fair price when omitted (FR-007), and
      persist both `fair_price_per_seat` and `price_per_seat` in the `INSERT` (extends the existing
      `_RIDE_COLS`/`INSERT` from T005)
- [X] T009 [US1] Update `POST /api/v1/rides` in `services/api/app/api/rides/router.py` to pass
      `payload.final_price_per_seat` through to `ride_service.create_ride` alongside the existing
      `fare.per_seat_price_egp` (fair price) and `fare.max_price_per_seat_egp` (from T003)

**Checkpoint**: User Story 1 is fully functional — drivers can create rides at the fair price or any
valid markup, independent of band enforcement (US2) or edit support (US3).

---

## Phase 4: User Story 2 - System rejects an out-of-band price (Priority: P1)

**Goal**: Any driver-submitted price outside `[fair_price, max_price]` is rejected server-side with the
valid range, on both create and (later, US3) edit.

**Independent Test**: `POST /api/v1/rides` with a price below fair price and separately above max price
→ both rejected 400 `price_out_of_band` with the range in the message; exact boundary values (`fair_price`
and `max_price`) are accepted.

### Tests for User Story 2

- [X] T010 [P] [US2] Integration tests: below-fair rejected, above-max rejected, exact-boundary values
      (fair and max) accepted, in `services/api/tests/integration/test_rides_fare_override.py`

### Implementation for User Story 2

- [X] T011 [US2] Add band validation to `ride_service.create_ride` (after T008): raise
      `RideServiceError("price_out_of_band", ...)` with the fair/max range in the message when the
      resolved final price falls outside `[fair_price, max_price]` (FR-005, NFR-001, research.md §2) —
      depends on T008 (same function)

**Checkpoint**: Creation-time band enforcement is complete and server-side-authoritative, satisfying
SC-003 for the create path.

---

## Phase 5: User Story 3 - Driver adjusts price when editing an existing ride (Priority: P2)

**Goal**: A driver editing a published ride can change its final price (bounded by the current band), and
if a seat-count edit shifts the band such that the old price no longer fits, the edit is rejected unless
a new in-band price is supplied — never silently repriced.

**Independent Test**: Edit a ride's price to a new in-band value → saved. Edit `total_seats` such that the
old price still fits the recomputed band → price unchanged. Edit `total_seats` such that the old price no
longer fits → rejected without a new price, succeeds with one.

### Tests for User Story 3

- [X] T012 [P] [US3] Integration tests: direct price edit within band succeeds; direct price edit
      out-of-band rejected; `total_seats` edit that keeps old price in-band leaves `price_per_seat`
      unchanged; `total_seats` edit that pushes old price out-of-band is rejected without a new price and
      succeeds with one, in `services/api/tests/integration/test_rides_fare_override_edit.py`

### Implementation for User Story 3

- [X] T013 [US3] In `ride_service.edit_ride` (`services/api/app/services/ride_service.py`), handle a
      supplied `final_price_per_seat` on its own: validate it against the ride's current
      `fair_price_per_seat`/max band before adding it to `sets` (mirrors T011's validation)
- [X] T014 [US3] Replace the existing `total_seats`-triggered silent price overwrite (the block reading
      `if ride.get("price_source") == "system" and ride["route_distance_km"] is not None: ...` around
      line ~401) with the re-banding logic from research.md §4: recompute `fair_price_per_seat` and the
      new band; if the ride's current final price still fits, update only
      `fair_price_per_seat`/cost-breakdown columns; if it doesn't, require the request's
      `final_price_per_seat` to be supplied and in-band, else raise `price_out_of_band` (FR-008) — depends
      on T013 (same function, overlapping `sets`/validation logic)
- [X] T015 [US3] Update `PATCH /api/v1/rides/{ride_id}` in `services/api/app/api/rides/router.py` to pass
      `payload.final_price_per_seat` through to `ride_service.edit_ride`

**Checkpoint**: Edit-time pricing is fully functional and independently testable, satisfying FR-008 and
SC-003 for the edit path.

---

## Phase 6: User Story 4 - Admin sees both fair price and driver's final price (Priority: P3)

**Goal**: Admins can see a ride's fair price, final price, and markup percentage in the admin panel
without consulting any other system.

**Independent Test**: `GET /api/admin/rides/{id}` for a ride created with a markup → response includes
`fair_price_per_seat`, `price_per_seat`, `markup_egp`, and `markup_percentage`, all numerically consistent.

### Tests for User Story 4

- [X] T016 [P] [US4] Integration test: admin list + detail responses include the four price fields with
      correct values, in `services/api/tests/integration/test_admin_rides_fare_override.py`

### Implementation for User Story 4

- [X] T017 [US4] Extend the list and detail response dicts in
      `services/api/app/api/admin/rides_router.py` (same hand-built-dict pattern already used there, see
      the existing `"price_per_seat": str(r["price_per_seat"])` lines) to add `fair_price_per_seat`,
      `markup_egp` (`price_per_seat - fair_price_per_seat`), and `markup_percentage`
      (`round(markup_egp / fair_price_per_seat * 100)`, guarding `fair_price_per_seat > 0` per
      data-model.md's edge-case note) — FR-010

**Checkpoint**: All four user stories are independently functional. SC-004 is satisfied.

---

## Phase 7: Cross-Cutting - Commission Scales with Markup (FR-011)

**Purpose**: Not tied to a single user story — this changes what the platform actually collects whenever
*any* story above results in a ride with a markup. Must ship alongside the user-facing stories for FR-011
compliance, but is independently testable via the wallet ledger rather than any UI/API response.

- [ ] T018 Update the `max_commission` reservation calculation in `ride_service.create_ride`
      (`services/api/app/services/ride_service.py`, near the `check_available_balance`/`create_reservation`
      calls) to add the markup term `(final_price_per_seat - fair_price_per_seat) * total_seats * 0.20`
      on top of the existing `fuel_cost*0.20 + distance_fee + safety_margin` (research.md §3) — depends on
      T008/T011 (final price and fair price both resolved by then)
- [ ] T019 Update `commission_service.deduct_commission` in
      `services/api/app/services/commission_service.py` to add `markup_commission_per_seat =
      (price_per_seat - fair_price_per_seat) * COMMISSION_RATE` to `per_seat_commission` before computing
      each booking's `commission_amount` (research.md §3) — requires `ride` dict passed into this
      function to include `fair_price_per_seat` and `price_per_seat` (already true once T005 lands)
- [ ] T020 [P] Integration test: complete a ride created with a markup through to `completed` with a
      confirmed booking; assert the `COMMISSION_DEBIT` ledger amount equals the cost-basis commission
      plus the markup commission term (quickstart.md scenario 9), in
      `services/api/tests/integration/test_commission_fare_override.py`

**Checkpoint**: FR-011 is satisfied — platform commission revenue scales with driver markup.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all stories.

- [ ] T021 Run `services/api` pytest suite in full to confirm no regressions in existing pricing/ride/
      commission tests
- [ ] T022 Run all 10 `quickstart.md` scenarios end-to-end against the local `docker compose up --build`
      stack
- [ ] T023 [P] Update `services/api` OpenAPI-visible docstrings/response examples for the changed
      endpoints if the project generates API docs from them (check `services/api/app/api/rides/router.py`
      and `admin/rides_router.py` for existing docstring conventions before adding new ones)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (needs the migration file to apply) — BLOCKS all user
  stories
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational + T008 (adds validation to the same `create_ride`
  function US1 modifies) — cannot run fully in parallel with US1's T008, but its test task (T010) can be
  written in parallel
- **User Story 3 (Phase 5)**: Depends on Foundational only for its own band-validation task (T013); does
  not require US1/US2 to be complete, though it reuses the same `price_out_of_band` error introduced in
  T011 — implement error handling once, reuse across create and edit
- **User Story 4 (Phase 6)**: Depends on Foundational only (reads `fair_price_per_seat` from T005) — fully
  independent of US1/US2/US3's validation logic
- **Cross-Cutting Commission (Phase 7)**: Depends on US1 (T008, for `final_price_per_seat` on create) —
  can run any time after Phase 3
- **Polish (Phase 8)**: Depends on all preceding phases

### Within Each User Story

- Tests before implementation where both are listed
- US2's implementation (T011) depends on US1's (T008) — same function, sequential
- US3's two implementation tasks (T013, T014) are sequential — same function, overlapping logic
- US4 (T017) has no dependency on US1/US2/US3 beyond Phase 2

### Parallel Opportunities

- T006 and T007 (US1 tests) in parallel with each other
- T010 (US2 test) can be written in parallel with T008/T009 (US1 implementation), even though T011 (US2
  implementation) must wait for T008
- T012 (US3 test) in parallel with US1/US2 work
- T016 (US4 test) and T017 (US4 implementation) have no cross-story dependency — the whole of Phase 6 can
  run in parallel with Phases 3–5 once Phase 2 is done
- T020 (commission test) in parallel with Phase 8 tasks once T018/T019 land

---

## Parallel Example: Foundational Phase

```bash
# After T002 (migration applied), these two touch different files:
Task: "Add MAX_MARKUP_RATE + calculate_max_price() to pricing_service.py"
Task: "Add final_price_per_seat / fair_price_per_seat fields to models/ride.py"
```

## Parallel Example: Across User Stories (after Phase 2)

```bash
# US4 is fully independent of US1/US2/US3 validation logic:
Task: "Extend admin/rides_router.py with fair price, markup fields (T017)"
# ...while US1's core create-ride change proceeds separately:
Task: "Update ride_service.create_ride to accept and default final price (T008)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (migration file)
2. Complete Phase 2: Foundational (migration applied, pricing helper, model fields, response field)
3. Complete Phase 3: User Story 1 — drivers can create rides at fair price or a chosen markup
4. **STOP and VALIDATE**: Run T007's integration test; confirm both default and explicit-price creation
   work
5. Note: without Phase 4 (US2), the band is *displayable* but not yet *enforced* — do not ship Phase 3
   alone to production; US2 is P1 for exactly this reason (spec: "without enforcement, this is just
   'drivers can override the fare'")

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 + US2 together → the two P1 stories, since US2 depends on US1's code — this is the real minimum
   shippable increment, satisfying SC-002 and SC-003
3. US3 → edit support (FR-008 compliance)
4. US4 → admin visibility (FR-010, SC-004)
5. Phase 7 → commission correctness (FR-011) — should land before production use, since it's a revenue
   correctness issue, not purely additive UX
6. Phase 8 → full-suite validation

### Recommended Grouping

Because US1 and US2 share one function (`create_ride`) and one validation branch, implement them as a
single unit (T006–T011) rather than strictly sequentially story-by-story. US3, US4, and Phase 7 are each
genuinely independent of that unit and of each other.
