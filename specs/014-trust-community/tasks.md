# Tasks: Trust & Community

**Input**: Design documents from `specs/014-trust-community/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Not explicitly requested in the spec — no dedicated test-task subsections. Each user
story phase ends with a task that runs the relevant `quickstart.md` scenario as its independent
validation.

**Organization**: Tasks are grouped by user story (spec.md priorities P1/P2/P3) to enable
independent implementation and testing of each.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps the task to US1/US2/US3 from spec.md
- File paths are exact and relative to the repository root

---

## Phase 1: Setup

**Purpose**: Create the migration file this feature will build on.

- [X] T001 Create `supabase/migrations/20260729000001_phase10_trust_community.sql` with a header
  comment describing scope (`ratings`, `reports`, `moderation_config`, `admin_audit_logs` extension,
  `profiles` rating-aggregate columns), per `plan.md` Source Code section

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema all three user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add `report_category`, `report_status`, `report_resolution_action`, and `rater_role`
  ENUMs to `supabase/migrations/20260729000001_phase10_trust_community.sql`, per `data-model.md`
- [X] T003 Add the `ratings` table (columns, `CHECK (stars BETWEEN 1 AND 5)`,
  `CHECK (char_length(comment) <= 500)`, `UNIQUE (booking_id, rater_id)`, `(ratee_id, created_at
  DESC)` index) to `supabase/migrations/20260729000001_phase10_trust_community.sql`, per
  `data-model.md` — depends on T002 (uses `rater_role`)
- [X] T004 Add the `reports` table (columns, `CHECK (reported_user_id != reporter_id)`, `CHECK
  (char_length(description) BETWEEN 1 AND 1000)`, `(status, created_at DESC)`,
  `(reported_user_id, created_at DESC)`, `(reporter_id, created_at DESC)` indexes) to
  `supabase/migrations/20260729000001_phase10_trust_community.sql`, per `data-model.md` — depends
  on T002 (uses `report_category`/`report_status`/`report_resolution_action`)
- [X] T005 [P] Add the `moderation_config` singleton table, seed row (`rating_floor = 3.0,
  rating_window = 10, rating_min_count = 5, report_count_threshold = 3, report_window_days = 30`),
  and an `updated_at` trigger (mirroring `ranking_config`'s trigger pattern from
  `20260714000001_phase13_match_learning.sql`) to
  `supabase/migrations/20260729000001_phase10_trust_community.sql`, per `data-model.md`
- [X] T006 Add `rating_avg NUMERIC(3,2)` (nullable) and `rating_count INTEGER NOT NULL DEFAULT 0`
  columns to `profiles` via `ALTER TABLE` in
  `supabase/migrations/20260729000001_phase10_trust_community.sql`, per `data-model.md` R6
- [X] T007 Extend `admin_audit_logs` in
  `supabase/migrations/20260729000001_phase10_trust_community.sql`: `DROP` the existing
  `action_type` CHECK constraint and `ADD` a replacement including `'warned'`, and add a nullable
  `report_id UUID REFERENCES reports(id) ON DELETE SET NULL` column, per `research.md` R2 —
  depends on T004 (FK to `reports`)
- [X] T008 Enable RLS on `ratings`, `reports`, and `moderation_config` in
  `supabase/migrations/20260729000001_phase10_trust_community.sql`: party-scoped `SELECT` only on
  `ratings`/`reports` (no client `INSERT`/`UPDATE`/`DELETE`), no client policies at all on
  `moderation_config` (service-role only, mirroring `ranking_config`), per `data-model.md` Row
  Level Security — depends on T003, T004, T005
- [X] T009 Apply the migration locally (`supabase db reset` or `supabase migration up`) and verify
  the two new tables, the singleton config table, the extended `admin_audit_logs` constraint, and
  the new `profiles` columns all exist — depends on T006, T007, T008

**Checkpoint**: Schema exists. All user stories can now begin.

---

## Phase 3: User Story 1 - Mutual Post-Ride Rating (Priority: P1) 🎯 MVP

**Goal**: Passengers and drivers can rate each other after a completed booking; ratings are
double-blind until both parties have rated or 14 days pass; aggregates are exposed on the user's
own profile; AI-matched bookings feed the `rated` outcome signal.

**Independent Test**: Complete a booking between a test passenger and driver; submit a rating as
each party; verify both persist, aggregates update, duplicate/invalid submissions are rejected, and
reveal timing matches FR-008 (`quickstart.md` Scenario 1).

### Implementation for User Story 1

- [ ] T010 [P] [US1] Create `services/api/app/services/rating_service.py` with
  `submit_rating(conn, booking_id, rater_id, stars, comment) -> dict`: validates the booking is
  `completed` (FR-003), the rater is a party to it (FR-004), no existing rating for
  `(booking_id, rater_id)` (FR-005), and no more than 14 days have elapsed since the ride's
  `completed_at` (FR-011); inserts the rating row and recalculates the ratee's `profiles.rating_avg`/
  `rating_count` in the same transaction (FR-006, NFR-002), per `data-model.md` and `contracts/api.md`
- [ ] T011 [US1] Add `get_own_rating_summary(conn, user_id) -> dict` to
  `services/api/app/services/rating_service.py`: returns `rating_avg`/`rating_count` (`null` average
  when count is 0, FR-010) and an anonymized comment list excluding rater identity (FR-007) and any
  rating not yet revealed per the FR-008 double-blind rule (counterpart-rated OR 14 days elapsed) —
  depends on T010 (same file)
- [ ] T012 [US1] In `services/api/app/services/rating_service.py`'s `submit_rating()`, call
  `match_logging_service.record_outcome(conn, ride_id, passenger_id, 'rated', {"stars": stars})`
  when a linked `match_outcomes` row exists for the booking (FR-009), reusing the correlation
  lookup pattern from `013-match-learning-foundation`'s `match_logging_service.py` — depends on T010
- [ ] T013 [US1] Create `services/api/app/api/ratings/router.py` with `POST /ratings` and
  `GET /profiles/{user_id}/rating` per `contracts/api.md`, including the `403` restriction that
  `user_id` must equal the authenticated caller — depends on T010, T011, T012
- [ ] T014 [US1] Register the ratings router in `services/api/app/main.py` — depends on T013
- [ ] T015 [US1] In `services/api/app/services/booking_service.py`'s `complete_ride_bookings()`,
  enqueue a `notification_events` row per completed booking prompting both parties to rate,
  reusing the existing `notification_dispatcher.py` delivery path (`research.md` R5) — depends on T009
- [ ] T016 [P] [US1] Add the post-ride rating prompt and own-rating view under
  `apps/main/src/app/(passenger)/ratings/` — depends on T014
- [ ] T017 [P] [US1] Add the post-ride rating prompt and own-rating view under
  `apps/main/src/app/(driver)/ratings/` — depends on T014
- [ ] T018 [US1] Run `quickstart.md` Scenario 1 locally and confirm rating submission, duplicate
  rejection, non-completed-booking rejection, non-party rejection, and double-blind reveal all
  behave as specified — depends on T015, T016, T017

**Checkpoint**: User Story 1 is fully functional and independently testable — ratings work
end-to-end without reporting or moderation existing yet.

---

## Phase 4: User Story 2 - Reporting a Safety Concern (Priority: P2)

**Goal**: Either party to a ride can report a safety/conduct concern against the other, with no
automatic restriction on the reported user beyond queue visibility.

**Independent Test**: As a passenger with a `confirmed`/`completed` booking, submit a report
against the driver; verify it persists with `status = open`, rejects non-party/self-report/missing-
field submissions, and imposes no immediate restriction on the reported user (`quickstart.md`
Scenario 2).

**Depends on**: Foundational schema only (Phase 2) — does not require User Story 1 to be complete,
per spec.md's stated story independence.

### Implementation for User Story 2

- [ ] T019 [P] [US2] Create `services/api/app/services/report_service.py` with
  `submit_report(conn, ride_id, booking_id, reporter_id, reported_user_id, category, description) ->
  dict`: validates the reporter was a party to the ride/booking and is not reporting themselves
  (FR-013), category and description are present (FR-014), and the ride is `in_progress` or
  `completed` (FR-015); inserts the report row with `status = 'open'`, per `data-model.md` and
  `contracts/api.md`
- [ ] T020 [US2] Add `get_own_reports(conn, user_id) -> list[dict]` to
  `services/api/app/services/report_service.py`, returning status-only history excluding resolution
  fields (FR-016) — depends on T019 (same file)
- [ ] T021 [US2] Create `services/api/app/api/reports/router.py` with `POST /reports` and
  `GET /reports/mine` per `contracts/api.md` — depends on T019, T020
- [ ] T022 [US2] Register the reports router in `services/api/app/main.py` — depends on T021
- [ ] T023 [P] [US2] Add the "Report a concern" entry point (category selector + description) under
  `apps/main/src/app/(passenger)/ratings/` — depends on T022
- [ ] T024 [P] [US2] Add the "Report a concern" entry point under
  `apps/main/src/app/(driver)/ratings/` — depends on T022
- [ ] T025 [US2] Run `quickstart.md` Scenario 2 locally and confirm report submission, rejection
  cases, and the soft-flag-only behavior (FR-017 — no restriction on the reported user immediately
  after filing) all behave as specified — depends on T023, T024

**Checkpoint**: User Stories 1 and 2 both work independently — reporting doesn't require ratings
to exist, and vice versa.

---

## Phase 5: User Story 3 - Admin Safety Moderation Queue (Priority: P3)

**Goal**: Admins can see open reports and auto-flagged users, take warn/suspend/dismiss actions on
reports, and reinstate suspended users — all traceable via the existing audit log.

**Independent Test**: As an admin, view the queue, take a warn action (no state change) and a
suspend action (blocks ride/booking creation) on two different users, then reinstate the suspended
one (`quickstart.md` Scenario 3).

**Depends on**: User Story 2 (reports must exist to populate the queue) for full end-to-end
testing, though the flagged-users half (FR-019) only depends on Foundational schema plus ratings
(US1) or reports (US2) data existing — consistent with spec.md's "payoff of Stories 1 and 2" framing.

### Implementation for User Story 3

- [ ] T026 [P] [US3] Create `services/api/app/services/moderation_service.py` with
  `init_moderation_config()`, `moderation_config_refresh_loop()`, and
  `get_flagging_thresholds() -> dict`, mirroring
  `services/api/app/services/ranking_config_service.py`'s singleton-config-table + cached-refresh-
  loop pattern (`research.md` R3)
- [ ] T027 [US3] Add `list_flagged_users(conn) -> list[dict]` to
  `services/api/app/services/moderation_service.py`, implementing FR-019: rolling average over the
  most recent `rating_window` ratings below `rating_floor` (with at least `rating_min_count`
  ratings received), OR `report_count_threshold`+ reports within `report_window_days` — depends on
  T026 (same file)
- [ ] T028 [P] [US3] Extend `services/api/app/services/audit_service.py`'s `append_log()` with an
  optional `report_id: str | None = None` parameter, passed through to the new
  `admin_audit_logs.report_id` column
- [ ] T029 [US3] Add `resolve_report(conn, report_id, admin_id, action, reason) -> dict` to
  `services/api/app/services/moderation_service.py`: for `warn`, calls
  `audit_service.append_log(..., 'warned', ..., report_id=report_id, reason=reason)` with no
  account state change; for `suspend`, sets `profiles.verification_status = 'suspended'` (FR-021,
  FR-024) and calls `append_log(..., 'suspended', ..., report_id=report_id, reason=reason)`; for
  `dismiss`, no account state change; all three mark the report `resolved`/`dismissed` and enqueue a
  `notification_events` row informing the affected user without exposing reporter identity (FR-025)
  — depends on T027, T028
- [ ] T030 [US3] Add `reinstate_user(conn, user_id, admin_id, reason) -> dict` to
  `services/api/app/services/moderation_service.py`: sets `profiles.verification_status = 'verified'`
  (FR-022), calls `audit_service.append_log(..., 'reinstated', ...)`, enqueues a `notification_events`
  row — depends on T029 (same file)
- [ ] T031 [US3] Create `services/api/app/api/admin/moderation_router.py` with
  `GET /admin/moderation/queue`, `GET /admin/moderation/flagged`,
  `POST /admin/moderation/reports/{report_id}/review`,
  `POST /admin/moderation/reports/{report_id}/resolve`,
  `POST /admin/moderation/users/{user_id}/reinstate`, mirroring
  `services/api/app/api/admin/verification_router.py`'s shape and `get_current_admin` auth (FR-018,
  FR-020, FR-026) — depends on T027, T029, T030
- [ ] T032 [US3] Register the moderation router in `services/api/app/main.py`; wire
  `moderation_service.init_moderation_config()` and
  `asyncio.create_task(moderation_service.moderation_config_refresh_loop())` into the `lifespan()`
  function alongside the existing `pricing_config`/`ranking_config` startup calls — depends on
  T026, T031
- [ ] T033 [P] [US3] Add the moderation queue screen (open reports + flagged users, report detail,
  resolve action, reinstate action) under `apps/admin/src/app/(dashboard)/moderation/` — depends on
  T032
- [ ] T034 [US3] Run `quickstart.md` Scenario 3 locally and confirm queue listing, flagged-user
  surfacing, warn/suspend/dismiss/reinstate actions, non-admin rejection, and outcome notifications
  all behave as specified — depends on T033

**Checkpoint**: All three user stories are independently functional. Feature is launch-ready.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and documentation for Phase 10 (specs 032/033/034).

- [ ] T035 [P] Review RLS policies on `ratings` and `reports` against NFR-005: confirm a rater/
  reporter sees only their own submissions/history, a ratee sees only their own aggregate and
  anonymized comments (never rater identity), and a reported user has no visibility into reports
  filed against them
- [ ] T036 [P] Add structured JSON logging for each moderation action (admin identity, action type,
  target user, reason, duration) in `services/api/app/services/moderation_service.py`, per NFR-006
  and consistent with the existing observability convention used by `audit_service.py`/
  `verification_router.py`
- [ ] T037 [P] Update `docs/implementation-roadmap.md` to mark Phase 10 specs 032
  (ratings-system), 033 (reporting-system), and 034 (safety-moderation) complete
- [ ] T038 Run the full `quickstart.md` validation (all 3 scenarios) end-to-end as a final
  regression pass — depends on all prior phases

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 (Ratings) and US2 (Reporting) have no dependency on each other and can proceed in parallel
  - US3 (Moderation) depends on report data existing (US2) for a fully populated queue, though its
    flagged-users half only needs Foundational + rating or report data from either story
- **Polish (Phase 6)**: Depends on all three user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — no dependency on US2/US3
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) — no dependency on US1/US3
- **User Story 3 (P3)**: Can start after Foundational (Phase 2); needs US2's `reports` data (and
  benefits from US1's `ratings` data) for a meaningful end-to-end demo of the queue

### Within Each User Story

- Service layer before router
- Router before frontend UI
- Backend + frontend before the story's `quickstart.md` validation task
- Story complete before moving to the next priority (if working sequentially)

### Parallel Opportunities

- T005 (moderation_config) can run alongside T003/T004 within Phase 2 (independent table
  definitions in the same migration file — coordinate via sequential edits if working solo)
- Once Foundational (Phase 2) completes, US1 and US2 can be built entirely in parallel by different
  developers; US3 can start its config/service scaffolding (T026) in parallel too, finishing its
  report-dependent pieces once US2 lands
- Frontend tasks for the same story across `(passenger)`/`(driver)` route groups (T016/T017,
  T023/T024) are always parallel-safe (different files)

---

## Parallel Example: Kicking off US1 and US2 service scaffolding together

```bash
# Once Phase 2 (Foundational) is complete, these can start in parallel:
Task: "Create services/api/app/services/rating_service.py with submit_rating(...)"
Task: "Create services/api/app/services/report_service.py with submit_report(...)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (Ratings)
4. **STOP and VALIDATE**: Run `quickstart.md` Scenario 1 independently
5. Deploy/demo if ready — ratings alone already unblock the `013-match-learning-foundation` `rated`
   outcome signal

### Incremental Delivery

1. Complete Setup + Foundational → schema ready
2. Add User Story 1 (Ratings) → validate → deploy/demo (MVP)
3. Add User Story 2 (Reporting) → validate → deploy/demo
4. Add User Story 3 (Moderation) → validate → deploy/demo
5. Each story adds value without breaking the previous ones

### Suggested Ship Order

P1 (Ratings) → P2 (Reporting) → P3 (Moderation), matching spec.md's stated priorities exactly —
moderation is explicitly "the payoff of Stories 1 and 2" and has the least standalone value until
there's report/rating data to act on.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- No test tasks were generated — not requested in the spec; `quickstart.md` scenarios serve as the
  per-story validation gate instead
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
