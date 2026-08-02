# Tasks: Admin Operations (Full)

**Input**: Design documents from `specs/015-admin-operations/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Not requested in the feature specification — no test tasks are generated. Validation is
via `quickstart.md`'s four end-to-end scenarios (Polish phase).

**Organization**: Tasks are grouped by user story (US1–US4, matching `spec.md`'s P1–P4 priorities) so
each can be implemented, tested, and shipped independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Maps the task to US1/US2/US3/US4 from `spec.md`
- File paths are exact, per `plan.md`'s Project Structure

---

## Phase 1: Setup

**Purpose**: The one net-new dependency this phase requires.

- [X] T001 [P] Add `recharts` to `apps/admin/package.json` dependencies (per `research.md` §2 — no charting library exists in `apps/admin` today)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one piece of shared logic two of the four stories (US1, US4) both require — computing period/date-range boundaries in a fixed reference timezone (FR-024).

**⚠️ CRITICAL**: T003–T007 (US1) and T019–T023 (US4) both depend on T002.

- [X] T002 [P] Create `services/api/app/utils/period.py` with `get_period_range(period: Literal["today","7d","30d","90d"]) -> tuple[datetime, datetime]` (Africa/Cairo reference timezone via `zoneinfo.ZoneInfo("Africa/Cairo")`, per `research.md` §4) and `get_trend_granularity(start: date, end: date) -> Literal["day","week"]` (`"week"` when `(end - start) > 60 days`, else `"day"`, per FR-018)

**Checkpoint**: Foundation ready — US2 and US3 have no dependency on this phase and can start immediately; US1 and US4 can start once T002 is done.

---

## Phase 3: User Story 1 - Platform Operations Dashboard (Priority: P1) 🎯 MVP

**Goal**: Admin-selectable-period KPI tiles + daily trend charts on the dashboard home screen, replacing the current 4 static tiles (FR-001–004).

**Independent Test**: `quickstart.md` Scenario 1 — seed mixed activity across a 7-day window, load the dashboard, verify every KPI/chart matches a direct DB count/sum and recomputes correctly across all four period presets.

### Implementation for User Story 1

- [X] T003 [US1] Implement `get_kpis(conn, period)` and `get_daily_trend(conn, period, metric)` in `services/api/app/services/dashboard_service.py` (FR-001, FR-002; uses `period.py` from T002; `users_by_role` is a point-in-time total per data-model.md, not period-scoped)
- [X] T004 [US1] Implement `GET /overview` in `services/api/app/api/admin/dashboard_router.py` per `contracts/api.md` (FR-001–004; `400 validation_error` for an invalid `period`; depends on T003)
- [X] T005 [US1] Register `dashboard_router` in `services/api/app/main.py` under `prefix="/api/admin/dashboard"`, alongside the existing admin router registrations (depends on T004)
- [X] T006 [P] [US1] Create `apps/admin/src/lib/api/admin-dashboard.ts` — fetch wrapper for `GET /api/admin/dashboard/overview?period=` per `contracts/api.md` (contract-driven; can be written in parallel with T003–T005)
- [X] T007 [US1] Rebuild `apps/admin/src/app/(dashboard)/page.tsx`: period selector (today/7d/30d/90d), KPI tiles, `recharts` trend charts for `rides_completed` and `commission_collected_egp`, and KPI-tile deep links to verification/moderation/user-list screens (FR-001–004; depends on T006)

**Checkpoint**: US1 is fully functional and independently testable/demoable.

---

## Phase 4: User Story 2 - Complete User Management (Priority: P2)

**Goal**: Searchable/filterable/paginated user list and a unified per-user detail view with suspend/reinstate, replacing the flat unfiltered table (FR-005–011).

**Independent Test**: `quickstart.md` Scenario 2 — seed 25+ users, search/filter/paginate the list, open a detail view and confirm all sections populate in one request, suspend/reinstate and confirm the audit log, and confirm admin-role accounts cannot be suspended.

### Implementation for User Story 2

- [X] T008 [US2] Add `GET /` to `services/api/app/api/admin/users_router.py`: search (`q` against `display_name`/`email`, `ILIKE`), filter (`role`, `status`), pagination — per `contracts/api.md` (FR-005–007)
- [X] T009 [US2] Add `GET /{user_id}` to `services/api/app/api/admin/users_router.py`: unified detail view composing profile + ride/booking history + ratings received + reports (filed by/against) + wallet-if-driver, per `data-model.md`'s payload shape — empty sections return empty arrays/zeroed aggregates, not errors (FR-008; same file as T008, sequential)
- [X] T010 [US2] Extend `suspend_user()` in `services/api/app/api/admin/users_router.py`: insert a `role == 'admin'` guard (`403 forbidden`) before the existing `verification_status` checks, and add a structured log entry (admin identity, action type, target user, duration) matching `moderation_service.py`'s `logger.info(json.dumps({...}))` pattern (FR-009, NFR-006; same file, sequential after T009)
- [X] T011 [P] [US2] Extend `apps/admin/src/lib/api/admin-users.ts`: add `list(token, {q, role, status, page})` and `getDetail(token, userId)` functions per `contracts/api.md`, alongside the existing `suspend()`/`reinstate()` (contract-driven; can be written in parallel with T008–T010)
- [X] T012 [P] [US2] Rebuild `apps/admin/src/app/(dashboard)/users/page.tsx`: search box, role filter, verification-status filter, pagination (FR-005–007; depends on T011)
- [X] T013 [P] [US2] Create `apps/admin/src/app/(dashboard)/users/[user_id]/page.tsx`: unified detail view (profile, rides/bookings, ratings, reports, wallet-if-driver), suspend/reinstate action with the suspend control hidden entirely for `role = 'admin'` targets (FR-008–011; depends on T011)

**Checkpoint**: US1 and US2 both independently functional.

---

## Phase 5: User Story 3 - Enhanced Verification Queue Tooling (Priority: P3)

**Goal**: Search and pending-age visibility on the verification queue/history, plus discoverable manual unlock, on top of the existing approve/reject workflow (FR-012–016).

**Independent Test**: `quickstart.md` Scenario 3 — seed submissions of varying ages, confirm the >24h one is flagged, search queue/history by applicant name, filter history by outcome, and unlock a 3-attempt-exhausted user.

### Implementation for User Story 3

- [X] T014 [US3] Extend `get_queue()` in `services/api/app/api/admin/verification_router.py`: add `q` search param (`ILIKE` against joined `profiles.display_name`/`email`) and compute `pending_seconds`/`is_aged` (`> 86400`) per row (FR-012, FR-013)
- [X] T015 [US3] Extend `get_history()` in `services/api/app/api/admin/verification_router.py`: add `q` search param and `outcome` filter (`approved`/`rejected`) (FR-013, FR-014; same file, sequential after T014)
- [X] T016 [P] [US3] Extend `apps/admin/src/lib/api/admin-verification.ts`: add the new `q`/`outcome` query params to the existing queue/history client calls per `contracts/api.md` (contract-driven; can be written in parallel with T014–T015)
- [X] T017 [P] [US3] Extend `apps/admin/src/app/(dashboard)/verification/page.tsx`: add a search box and a visual "pending >24h" flag per submission (FR-012, FR-013; depends on T016)
- [X] T018 [P] [US3] Extend `apps/admin/src/app/(dashboard)/verification/history/page.tsx`: add a search box, an outcome filter, and an "unlock for re-submission" action for locked users that calls the existing `POST /users/{user_id}/unlock` endpoint (FR-013, FR-014, FR-015; depends on T016)

**Checkpoint**: US1, US2, and US3 all independently functional.

---

## Phase 6: User Story 4 - Financial Reporting & Driver Balance Oversight (Priority: P4)

**Goal**: Date-range commission/revenue report with CSV export, plus a sortable driver balance overview flagging at-risk drivers (FR-017–021).

**Independent Test**: `quickstart.md` Scenario 4 — seed ledger entries across drivers over 2 weeks, verify report totals match ledger sums, verify the balance list sorts ascending with a never-topped-up driver showing 0.00/at-risk, and verify the CSV export's totals match the on-screen report exactly.

### Implementation for User Story 4

- [ ] T019 [US4] Implement `get_report(conn, start, end)`, `get_driver_balances(conn)`, and `stream_report_csv(conn, start, end)` in `services/api/app/services/financial_report_service.py` (FR-017–021; uses `period.py`'s `get_trend_granularity` from T002; `get_driver_balances` `LEFT JOIN`s `driver_wallets` from `profiles` so wallet-less drivers appear at 0.00/at-risk per data-model.md)
- [ ] T020 [US4] Implement `GET /report`, `GET /report/export` (`StreamingResponse`, `media_type="text/csv"`, no server-side file), and `GET /drivers/balances` in `services/api/app/api/admin/financial_router.py` per `contracts/api.md` (FR-017–021, NFR-007; depends on T019)
- [ ] T021 [US4] Register `financial_router` in `services/api/app/main.py` under `prefix="/api/admin/financial"` (depends on T020)
- [ ] T022 [P] [US4] Create `apps/admin/src/lib/api/admin-financial.ts` — fetch wrappers for `GET /report`, `GET /report/export`, `GET /drivers/balances` per `contracts/api.md` (contract-driven; can be written in parallel with T019–T021)
- [ ] T023 [US4] Create `apps/admin/src/app/(dashboard)/financial/page.tsx`: date-range picker, commission/credits/debits/net-revenue totals, `recharts` trend, driver balance table (sorted ascending, at-risk flag), CSV export button (FR-017–021; depends on T022)

**Checkpoint**: All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation and NFR verification across all four stories.

- [ ] T024 [P] Run `quickstart.md` Scenarios 1–4 end-to-end against a locally seeded environment; confirm every step's expected outcome
- [ ] T025 [P] Verify NFR-001 (≤500ms p95, dashboard/reports) and NFR-002 (≤300ms p95, user search) against a ~50,000-profile seeded dataset; if `ILIKE` search on `profiles.display_name`/`email` is slow at that scale, add a `pg_trgm` GIN index as a follow-up (not required to ship this phase, per NFR-002's target being the acceptance bar, not a specific index)
- [ ] T026 Confirm every endpoint added/extended in this phase (`dashboard_router`, `financial_router`, and the new `users_router`/`verification_router` endpoints) rejects a non-admin caller with `403 forbidden` (FR-022, NFR-005)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: No dependency on Setup; only blocks US1 and US4 (US2 and US3 don't use `period.py`).
- **US1 (Phase 3)**: Depends on T002 (Foundational).
- **US2 (Phase 4)**: No dependency on Foundational or on US1 — can start immediately after Setup.
- **US3 (Phase 5)**: No dependency on Foundational or on US1/US2 — can start immediately after Setup.
- **US4 (Phase 6)**: Depends on T002 (Foundational).
- **Polish (Phase 7)**: Depends on all four user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Depends only on T002. Fully independent of US2/US3/US4.
- **US2 (P2)**: No dependency on any other story.
- **US3 (P3)**: No dependency on any other story.
- **US4 (P4)**: Depends only on T002. Fully independent of US1/US2/US3.

All four stories touch disjoint router files (`dashboard_router.py` / `users_router.py` /
`verification_router.py` / `financial_router.py`) and disjoint frontend routes, so they can be
implemented in any order or fully in parallel once T001–T002 are done.

### Within Each User Story

- Backend service → router → `main.py` registration is sequential (same-file/import-order
  dependency).
- Frontend API-client wrappers are contract-driven (per `contracts/api.md`) and can be written in
  parallel with the backend implementation, not after it.
- Frontend pages depend on their story's API-client wrapper, not on the backend being finished first.

### Parallel Opportunities

- T001 and T002 (different files/domains).
- Within US1: T006 in parallel with T003–T005.
- Within US2: T011 in parallel with T008–T010; T012 and T013 in parallel with each other (once T011 is done).
- Within US3: T016 in parallel with T014–T015; T017 and T018 in parallel with each other (once T016 is done).
- Within US4: T022 in parallel with T019–T021.
- T024 and T025 in Polish.
- Across stories: US1, US2, US3, US4 can all be staffed and built in parallel by different developers once T001–T002 are done.

---

## Parallel Example: User Story 2

```bash
# Backend (sequential, same file) and frontend client (parallel, contract-driven) start together:
Task: "Add GET / to services/api/app/api/admin/users_router.py (search/filter/paginate)"
Task: "Extend apps/admin/src/lib/api/admin-users.ts with list() and getDetail()"

# Once the client wrapper (T011) is done, both pages can proceed in parallel:
Task: "Rebuild apps/admin/src/app/(dashboard)/users/page.tsx"
Task: "Create apps/admin/src/app/(dashboard)/users/[user_id]/page.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (US1 — dashboard).
3. **STOP and VALIDATE**: Run `quickstart.md` Scenario 1 independently.
4. Deploy/demo — the dashboard alone is a complete, shippable improvement over the current 4 static tiles.

### Incremental Delivery

1. Setup + Foundational → ready.
2. US1 (dashboard) → validate → deploy (MVP).
3. US2 (user management) → validate → deploy.
4. US3 (verification tooling) → validate → deploy.
5. US4 (financial reporting) → validate → deploy.
6. Polish (Phase 7) → final cross-cutting validation.

Each story ships independently and in any order after Setup/Foundational — priority order (P1→P4)
is recommended but not required by any technical dependency.

### Parallel Team Strategy

With four developers, after Setup + Foundational:
- Developer A: US1 (T003–T007)
- Developer B: US2 (T008–T013)
- Developer C: US3 (T014–T018)
- Developer D: US4 (T019–T023)

All four touch disjoint files and can integrate independently.

---

## Notes

- [P] tasks touch different files and have no dependency on an incomplete task.
- [Story] labels map every implementation task to its `spec.md` user story for traceability.
- No test tasks were generated — tests were not requested in `spec.md`; `quickstart.md`'s scenarios
  (T024) are the validation mechanism for this phase.
- Commit after each task or logical group, per standing project convention.
- Stop at any checkpoint to validate a story independently before continuing.
