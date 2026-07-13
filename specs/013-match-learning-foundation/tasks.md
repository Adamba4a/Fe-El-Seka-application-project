# Tasks: Match Learning Foundation

**Input**: Design documents from `specs/013-match-learning-foundation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/data-schema.md, quickstart.md

**Tests**: Not explicitly requested in the spec — no dedicated test-task subsections. Each user
story phase ends with a task that runs the relevant `quickstart.md` scenarios as its independent
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

- [X] T001 Create `supabase/migrations/20260714000001_phase13_match_learning.sql` with a header comment describing scope (search_sessions, match_events, match_outcomes, ranking_config), per `plan.md` Source Code section

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The four new tables. All three user stories require the schema to exist first.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add `match_outcome_transition` ENUM (`'requested','accepted','rejected','completed','cancelled','rated'`) and the `search_sessions` table (columns + `(passenger_id, created_at DESC)` index) to `supabase/migrations/20260714000001_phase13_match_learning.sql`, per `data-model.md`
- [X] T003 Add the `match_events` table (columns + `(search_id)` index + `(candidate_ride_id, passenger_id, created_at DESC)` index) to `supabase/migrations/20260714000001_phase13_match_learning.sql`, per `data-model.md` — depends on T002 (FK to `search_sessions`)
- [X] T004 Add the `match_outcomes` table (columns + `(match_event_id, transition_at ASC)` index) to `supabase/migrations/20260714000001_phase13_match_learning.sql`, per `data-model.md` — depends on T003 (FK to `match_events`) and T002 (uses the ENUM)
- [X] T005 [P] Add the `ranking_config` singleton table, seed row (`exploration_rate = 0.1250`), and `updated_at` trigger (mirroring `pricing_config`'s trigger pattern) to `supabase/migrations/20260714000001_phase13_match_learning.sql`, per `data-model.md`
- [X] T006 Enable RLS with no public policies on all four new tables (`search_sessions`, `match_events`, `match_outcomes`, `ranking_config`) in `supabase/migrations/20260714000001_phase13_match_learning.sql` — depends on T002-T005
- [X] T007 Apply the migration locally (`supabase db reset` or `supabase migration up`) and verify all four tables and the enum exist — depends on T006

**Checkpoint**: Schema exists. All user stories can now begin.

---

## Phase 3: User Story 1 - Every shown candidate is logged with its full context (Priority: P1) 🎯 MVP

**Goal**: Every candidate returned in a search response (AI-scored or fallback-derived) gets a
`match_events` row with its exact feature vector, rank, and score; every subsequent booking-lifecycle
transition for that candidate is linked back to it.

**Independent Test**: Run a passenger search, query `match_events` directly and confirm one row per
returned candidate with full context; book one of the candidates and confirm the resulting
transitions appear as linked `match_outcomes` rows (`quickstart.md` Scenarios 1-3).

### Implementation for User Story 1

- [X] T008 [P] [US1] Create `services/api/app/services/match_logging_service.py` with `persist_match_events(search_ctx, ranked_candidates, score_map, ai_scored, model_version) -> None`: inserts one `search_sessions` row and one `match_events` row per candidate (feature vector snapshot, rank position, predicted score, `ai_scored` flag, `model_version`), per `plan.md` and `data-model.md`
- [X] T009 [US1] Add `record_outcome(conn, ride_id, passenger_id, transition_type, metadata) -> None` to `services/api/app/services/match_logging_service.py`, implementing the most-recent-match-event correlation lookup from `research.md` R1 — depends on T008 (same file)
- [X] T010 [US1] In `services/api/app/api/search/router.py`'s `search_rides()`, fire `asyncio.create_task(match_logging_service.persist_match_events(...))` immediately before returning the response, covering both the AI-ranked path (`ai_active = True`) and the fallback `overlap_pct` sort path (`ai_active = False`, `ai_scored = False`) — depends on T008
- [X] T011 [US1] In `services/api/app/services/booking_service.py`'s `create_booking()`, call `match_logging_service.record_outcome(conn, ride_id, passenger_id, 'requested', {"booking_id": ...})` inside the existing transaction, alongside the existing `_insert_audit_log()` call — depends on T009
- [X] T012 [US1] In `services/api/app/services/booking_service.py`'s `confirm_booking()`, call `record_outcome(conn, ..., 'accepted', {"booking_id": ...})` inside the existing transaction — depends on T009
- [X] T013 [US1] In `services/api/app/services/booking_service.py`'s `reject_booking()`, call `record_outcome(conn, ..., 'rejected', {"booking_id": ..., "reason": reason})` in the cancellation branch (and skip/omit for the premium-fallback-to-confirmed branch, which is an acceptance not a rejection) — depends on T009
- [X] T014 [US1] In `services/api/app/services/booking_service.py`'s `cancel_booking()`, call `record_outcome(conn, ..., 'cancelled', {"booking_id": ..., "cancelled_by": caller_role, "reason": reason})` inside the existing transaction — depends on T009
- [X] T015 [US1] In `services/api/app/services/booking_service.py`'s `complete_ride_bookings()`, call `record_outcome(conn, ..., 'completed', {"booking_id": ...})` for each completed booking row — depends on T009
- [X] T016 [US1] Run `quickstart.md` Scenarios 1-3 locally and confirm `match_events`/`match_outcomes` rows match the expected shape — depends on T010, T011, T012, T013, T014, T015

**Checkpoint**: User Story 1 is fully functional and independently testable — every search is logged, every booking transition is linked back to it.

---

## Phase 4: User Story 2 - Ranking occasionally surfaces non-top candidates (Priority: P2)

**Goal**: A configurable fraction (~10-15%) of searches return a non-pure-top-score order, and every
match-event records whether its position came from exploration or pure ranking.

**Independent Test**: Force `exploration_rate = 1.0`, run several searches with ≥3 feasible
candidates, and confirm exactly one candidate per search is promoted to rank 1 and flagged
`exploration_selected = true` (`quickstart.md` Scenario 4); confirm the rate is adjustable without a
restart (`quickstart.md` Scenario 6).

**Depends on**: User Story 1 (exploration flags are meaningless without the logging path already
recording them — matches spec.md's stated story dependency).

### Implementation for User Story 2

- [X] T017 [P] [US2] Create `services/api/app/services/ranking_config_service.py` with `init_ranking_config()`, `ranking_config_refresh_loop()`, `get_exploration_rate() -> float`, mirroring `services/api/app/services/pricing_service.py`'s singleton-config-table + cached-refresh-loop pattern
- [X] T018 [US2] Add `apply_exploration(ranked_candidates) -> tuple[list, str | None]` to `services/api/app/services/ranking_config_service.py`, implementing the single-swap epsilon-greedy algorithm from `research.md` R2 (promote one uniformly-random candidate from positions 2..N to position 1 with probability `get_exploration_rate()`) — depends on T017
- [X] T019 [US2] Wire `ranking_config_service.init_ranking_config()` and `asyncio.create_task(ranking_config_service.ranking_config_refresh_loop())` into `services/api/app/main.py`'s `lifespan()`, alongside the existing `pricing_config` startup/shutdown calls — depends on T017
- [X] T020 [US2] In `services/api/app/api/search/router.py`'s `search_rides()`, call `ranking_config_service.apply_exploration()` on the final ranked candidate list (both AI and fallback paths, per FR-006/FR-007) before the T010 logging call, so the promoted candidate's final `rank_position` is what gets logged — depends on T018, T010
- [X] T021 [US2] Extend `match_logging_service.persist_match_events()` (from T008) to accept and persist the `exploration_selected` flag/promoted-candidate-id produced by T020 — depends on T008, T020
- [X] T022 [US2] Run `quickstart.md` Scenarios 4 and 6 locally and confirm the exploration distribution matches the configured rate and updates without a restart — depends on T020, T021

**Checkpoint**: User Stories 1 and 2 both work independently — exploration is visible in logged data and tunable without a deploy.

---

## Phase 5: User Story 3 - Logging never degrades the search experience (Priority: P3)

**Goal**: Search response time and correctness are unaffected regardless of whether event logging
succeeds, fails, or is slow.

**Independent Test**: Simulate the logging path failing entirely and confirm the search endpoint
still returns correct results within its existing performance target (`quickstart.md` Scenario 5).

### Implementation for User Story 3

- [X] T023 [US3] Wrap all DB calls inside `match_logging_service.persist_match_events()` in try/except so any failure is caught and logged as structured JSON (matching the existing `ai_search_fallback`/`ai_prediction_call` logging convention in `services/api/app/api/search/router.py` and `services/api/app/services/ai_client.py`), never raised out of the `asyncio.create_task` — depends on T008
- [X] T024 [US3] Review `services/api/app/api/search/router.py`'s `search_rides()` to confirm the logging task from T010 is never `await`ed and that a `task.add_done_callback` (or equivalent) logs any unexpected exception without affecting the response already sent — depends on T010, T023
- [X] T025 [US3] Run `quickstart.md` Scenario 5 (simulate a persistence-path failure) locally and confirm the search response is unaffected and the failure is visible in logs — depends on T023, T024

**Checkpoint**: All three user stories are independently functional. Feature is launch-ready.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and observability groundwork for the Phase 13 items this feature feeds (046-049).

- [X] T026 [P] Add structured JSON logging for `match_event_persist_failure` (from T023) and `exploration_applied` (from T018/T020) events, following the existing `ai_prediction_call`/`ai_search_fallback` log-event naming convention, for future observability (feeds Phase 13 item 049)
- [X] T027 [P] Update `docs/implementation-roadmap.md` to mark Phase 13 items 044 (match-event-instrumentation) and 045 (ranking-exploration-strategy) complete
- [X] T028 Run the full `quickstart.md` validation (all 6 scenarios) end-to-end as a final regression pass — depends on all prior phases

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational only. No dependency on US2/US3.
- **User Story 2 (Phase 4)**: Depends on Foundational **and** User Story 1 (spec.md states this explicitly — exploration flags are meaningless without US1's logging path already in place).
- **User Story 3 (Phase 5)**: Depends on Foundational and touches the logging path built in US1 (T008, T010) — implemented last since it hardens what US1 built, but is conceptually independent of US2.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### Parallel Opportunities

- T005 (`ranking_config` table) can run in parallel with T002-T004 (the other three tables) within Foundational — different table, no FK relationship.
- T008 (create `match_logging_service.py`) and T017 (create `ranking_config_service.py`) can run in parallel — different files, no shared dependency.
- T026 and T027 in Polish can run in parallel — different files.

---

## Parallel Example: Foundational Phase

```bash
# T005 can run alongside T002-T004 (independent table definitions in the same migration file,
# but non-overlapping sections — coordinate via sequential edits if working solo):
Task: "Add ranking_config table + seed row + trigger to the migration file"
```

## Parallel Example: Kicking off US1 and US2 service scaffolding together

```bash
Task: "Create services/api/app/services/match_logging_service.py with persist_match_events()"
Task: "Create services/api/app/services/ranking_config_service.py with init_ranking_config()"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (all four tables — CRITICAL, blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run `quickstart.md` Scenarios 1-3 independently
5. This alone satisfies the feature's core Business Objective — real outcome data starts accumulating even before exploration ships.

### Incremental Delivery

1. Setup + Foundational → schema ready
2. User Story 1 → validate → this is already deployable and valuable on its own (logging-only, pure top-score ranking preserved)
3. User Story 2 → validate → exploration goes live, counterfactual data starts accumulating
4. User Story 3 → validate → hardening pass confirms nothing above ever risked the search path
5. Polish → observability + roadmap bookkeeping

### Suggested Ship Order

Given US2 explicitly depends on US1, and US3 is a hardening pass over US1's own logging path, the
natural implementation order is strictly sequential: **US1 → US2 → US3**, not parallelized across
stories — unlike a typical spec-kit feature, this one does not have independently-staffable stories
after Foundational.

---

## Notes

- [P] tasks touch different files or non-overlapping sections and have no completed-task dependency.
- [Story] labels map every Phase 3+ task to US1/US2/US3 for traceability back to spec.md.
- Commit after each task or logical group.
- Stop at each phase checkpoint to validate independently before continuing.
- `services/ai` and both Next.js apps (`apps/main`) are untouched by this feature — no tasks reference them.
