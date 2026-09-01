---

description: "Task list for Loyalty Points implementation"
---

# Tasks: Loyalty Points

**Input**: Design documents from `specs/028-loyalty-points/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/loyalty-points-api.md, quickstart.md

**Tests**: No dedicated automated API test suite convention exists for this kind of feature in this repo (per Specs 026/027 precedent) — validation is via the `quickstart.md` direct-service-layer scenarios, referenced as dedicated tasks at the end of each story.

**Organization**: Tasks are grouped by user story (from spec.md) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- File paths are relative to the repository root (`D:\Business\Fe El Seka app`)

## Path Conventions

Per plan.md Project Structure: `services/api/app/{models,services,api}` (FastAPI backend), `apps/main/src` (passenger+driver frontend), `apps/admin/src` (admin frontend), `supabase/migrations/` (schema).

---

## Phase 1: Setup

**Purpose**: Confirm environment readiness — no new dependencies are required for this feature.

- [X] T001 Verify Technical Context per plan.md: no new Python or Node packages are needed (existing FastAPI/asyncpg/Pydantic v2 and Next.js 14/Tailwind/shadcn stack covers this feature); confirm the local Supabase stack and `services/api` (`uvicorn`) start cleanly per `quickstart.md` prerequisites.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, shared account/ledger primitives, and Pydantic models every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Write migration `supabase/migrations/20260901000002_loyalty_points.sql` per `data-model.md`: `CREATE TYPE loyalty_account_role AS ENUM ('passenger','driver')`; `CREATE TYPE loyalty_transaction_reason AS ENUM ('ride_completed_earn','redemption_spend','redemption_refund','ride_reversal_clawback','admin_adjustment')`; `CREATE TYPE loyalty_reward_type AS ENUM ('free_ride','discount','car_maintenance','voucher')`; `CREATE TYPE loyalty_audience AS ENUM ('passenger','driver','both')`; `CREATE TYPE loyalty_fulfillment_mode AS ENUM ('instant','manual')`; `CREATE TYPE loyalty_redemption_status AS ENUM ('pending','fulfilled','rejected')`; `CREATE TABLE loyalty_points_accounts` (`id, user_id, role, balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0), created_at, updated_at`, `UNIQUE(user_id, role)`); `CREATE TABLE loyalty_points_transactions` (`id, account_id, delta, reason, ride_id, booking_id, redemption_request_id, balance_after, created_at`) with index `(account_id, created_at DESC)`; `CREATE TABLE loyalty_reward_catalog` (`id, type, title, description, audience, point_cost INTEGER NOT NULL CHECK (point_cost > 0), fulfillment_mode, active BOOLEAN NOT NULL DEFAULT true, created_by, created_at, updated_at`); `CREATE TABLE loyalty_redemption_requests` (`id, account_id, catalog_entry_id, points_spent, fulfillment_mode, status, ride_id, booking_id, fulfilled_by, fulfilled_at, rejection_reason, created_at`) with partial index `(status, created_at ASC) WHERE status = 'pending'`; RLS policies mirroring `driver_wallets`/`car_maintenance_rewards` (owner-read on accounts/transactions/redemption_requests, public-read on active catalog entries, no client write).
- [X] T003 [P] In the same migration file (T002): seed `platform_settings` rows `loyalty_free_ride_point_cost` (`"500"`), `loyalty_free_ride_max_fare_egp` (`"100.00"`), `loyalty_discount_point_cost` (`"200"`), `loyalty_discount_percentage` (`"10"`), `loyalty_car_maintenance_point_cost` (`"3000"`), `loyalty_passenger_earn_points_per_egp_fare` (`"1"`) via `INSERT ... ON CONFLICT (key) DO NOTHING`; seed the 3 system `loyalty_reward_catalog` rows (`free_ride`, `discount`, `car_maintenance` — `created_by NULL`, `point_cost` matching the seeded settings above, `fulfillment_mode` = `'instant'` for `free_ride`/`discount`, `'manual'` for `car_maintenance`).
- [X] T004 In the same migration file (T002): for every existing `driver_wallets` row, `INSERT INTO loyalty_points_accounts (user_id, role, balance) SELECT driver_id, 'driver', ROUND(car_maintenance_savings_egp) FROM driver_wallets` (1:1 EGP→points conversion per clarify Q1); for every `status='PENDING'` row in `car_maintenance_rewards`, insert a matching `loyalty_redemption_requests` row (`catalog_entry_id` = the seeded `car_maintenance` entry, `points_spent = amount_egp`, `status='pending'`, `fulfillment_mode='manual'`) — per research.md Decision 2, `FULFILLED` rows stay in `car_maintenance_rewards` as an archival record and are not migrated.
- [X] T005 Apply the migration from T002-T004 to the local Supabase stack and verify all types/tables/indexes/RLS policies/seed rows/migrated data exist as expected.
- [X] T006 [P] Add `redemption_request_id UUID NULL REFERENCES loyalty_redemption_requests(id)` to `admin_audit_logs` via a second migration `supabase/migrations/20260901000003_add_redemption_request_to_audit_logs.sql`, following the `withdrawal_request_id` precedent (no `action_type` CHECK change needed).
- [X] T007 [P] Add `loyalty_points_earned`, `loyalty_redemption_fulfilled`, `loyalty_redemption_rejected`, `loyalty_threshold_reached` to `notification_event_type` via `ALTER TYPE ... ADD VALUE IF NOT EXISTS` in a third migration `supabase/migrations/20260901000004_loyalty_notification_types.sql`.
- [X] T008 [P] Create `services/api/app/models/loyalty.py`: Pydantic schemas for `LoyaltyBalanceResponse`, `LoyaltyTransactionItem`/`LoyaltyTransactionsResponse`, `LoyaltyCatalogEntryResponse`, `LoyaltyRedeemResponse`, `AdminLoyaltyQueueItem`/`AdminLoyaltyQueueResponse`, `AdminLoyaltyCatalogCreateRequest`/`UpdateRequest`, per `contracts/loyalty-points-api.md`.
- [X] T009 Create `services/api/app/services/loyalty_service.py` with the shared account/ledger primitives every story depends on: `get_or_create_account(conn, user_id, role)`, `get_account_with_lock(conn, user_id, role)` (mirrors `wallet_service.get_wallet_with_lock`), `credit_points(conn, account, delta, reason, **refs)` (inserts a `loyalty_points_transactions` row, updates `balance`), `debit_points(conn, account, delta, reason, **refs)` (same, `GREATEST(balance - delta, 0)` floor for clawback-type reasons; raises on insufficient balance for spend-type reasons), `get_ledger_page(conn, account_id, page)` (mirrors `wallet_service.get_ledger_page`).

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Passenger Earns and Redeems Points for a Ride (Priority: P1) 🎯 MVP

**Goal**: A passenger automatically accumulates points on completed rides and redeems them at booking time for a free ride (capped) or a fare discount.

**Independent Test**: Complete several paid rides as a passenger, confirm the points balance increases after each; book a new ride redeeming points for a free ride or discount and confirm the fare charged reflects it.

### Implementation for User Story 1

- [X] T010 [US1] Implement `award_passenger_points(conn, account, booking_id, ride_id, fare_paid_egp)` in `loyalty_service.py`: reads `loyalty_passenger_earn_points_per_egp_fare` from `platform_settings`, computes `floor(fare_paid_egp * rate)`, calls `credit_points(..., reason='ride_completed_earn')` (FR-001).
- [X] T011 [US1] Wire T010 into `services/api/app/services/booking_service.py`'s `complete_ride_bookings()`: for each booking transitioned to `completed`, call `loyalty_service.get_or_create_account(conn, passenger_id, 'passenger')` then `award_passenger_points(...)`, enqueue a `loyalty_points_earned` notification event.
- [X] T012 [US1] Implement `list_catalog(conn, role, only_affordable=False)` in `loyalty_service.py`: returns `active` entries where `audience IN (role, 'both')`, each annotated with whether the caller's current balance meets `point_cost` (FR-004 acceptance scenario 4's locked/unavailable display).
- [X] T013 [US1] Implement `redeem_for_booking(conn, account, catalog_entry_id, ride, booking_fare_egp)` in `loyalty_service.py` for `free_ride`/`discount` entries only (FR-004/FR-005): under `get_account_with_lock`, verify `catalog_entry.type IN ('free_ride','discount')` (else `409`), verify no active sponsored/other discount already applied to the booking (FR-005a, `409 loyalty_redemption_conflict`), verify sufficient balance (`409 insufficient_points`), `debit_points(..., reason='redemption_spend')`, insert a `fulfilled` `loyalty_redemption_requests` row (`ride_id`/`booking_id` set), compute the adjusted fare (`free_ride`: `MIN(booking_fare_egp, loyalty_free_ride_max_fare_egp)` charged as zero up to the cap, passenger pays the remainder above it; `discount`: `booking_fare_egp * (1 - loyalty_discount_percentage/100)`).
- [X] T014 [US1] Extend `POST /rides/{ride_id}/bookings` in the existing booking-creation router: accept optional `loyalty_redemption_catalog_entry_id`, call T013 inside the same transaction as booking creation before the fare is finalized, include `loyalty_redemption` in the response per `contracts/loyalty-points-api.md`.
- [X] T015 [US1] Implement `reverse_points(conn, account, ride_id, booking_id, points)` in `loyalty_service.py` (FR-014): `debit_points(..., reason='ride_reversal_clawback')` with the `GREATEST` floor already built into T009's `debit_points`; wire into the existing booking cancellation/refund/fraud-flagging code path(s) in `booking_service.py` for bookings that previously earned points.
- [X] T016 [US1] Create `services/api/app/api/loyalty/loyalty_router.py`: `GET /api/v1/loyalty/balance`, `GET /api/v1/loyalty/transactions`, `GET /api/v1/loyalty/catalog` (T012), behind `get_current_passenger`/`get_current_driver` (role resolved from `profile["role"]`); mount in `services/api/app/main.py`.
- [X] T017 [P] [US1] Add `apps/main/src/app/(passenger)/loyalty/` — balance + transaction history page, per `contracts/loyalty-points-api.md`.
- [X] T018 [P] [US1] Add a points-redemption step to the passenger booking flow (existing booking creation UI under `apps/main/src/app/(passenger)/rides/`): show free-ride/discount options from T016's catalog endpoint with locked/unavailable state below threshold (FR-004 scenario 4), call T014 on booking submit.
- [X] T019 [US1] Run `quickstart.md` Scenario 1 (earn on completion), Scenario 2 (capped free-ride redemption), and Scenario 7 (reversal capped at balance) end-to-end; confirm all pass conditions.

**Checkpoint**: User Story 1 is fully functional and testable independently — passengers earn and redeem points for rides.

---

## Phase 4: User Story 2 - Driver Earns Points and Redeems for Car-Maintenance Credit (Priority: P2)

**Goal**: A driver accumulates points from the existing distance-fee mechanism (now expressed as points instead of an EGP counter) and redeems them for car-maintenance credit through the existing admin fulfillment queue, generalized.

**Independent Test**: Complete several rides as a driver, confirm the points balance increases proportionally to distance driven, redeem once the threshold is reached, and confirm the redemption appears in the admin fulfillment queue.

### Implementation for User Story 2

- [X] T020 [US2] Implement `award_driver_points(conn, driver_id, distance_fee_amount_egp)` in `loyalty_service.py`, replacing `car_maintenance_service.accumulate_and_maybe_grant()`: `get_account_with_lock(conn, driver_id, 'driver')`, `credit_points(..., reason='ride_completed_earn')` for `floor(distance_fee_amount_egp)` points 1:1 (FR-002, research.md Decision 6) — no threshold-triggered auto-grant (Q2: redemption is driver-initiated, not automatic).
- [X] T021 [US2] Update `services/api/app/services/commission_service.py`'s `deduct_commission()`: replace the call to `car_maintenance_service.accumulate_and_maybe_grant()` with `loyalty_service.award_driver_points(conn, driver_id, total_distance_fee)`.
- [X] T022 [US2] Implement `redeem_catalog_entry(conn, account, catalog_entry_id)` in `loyalty_service.py` for non-inline entries (`car_maintenance` and `voucher` types — used by both US2 and US3): under `get_account_with_lock`, reject `catalog_entry.type IN ('free_ride','discount')` (`409` — those redeem via T013's booking flow only), verify sufficient balance, `debit_points(..., reason='redemption_spend')`, insert a `loyalty_redemption_requests` row with `status` = `'fulfilled'` if `fulfillment_mode='instant'` or `'pending'` if `'manual'`.
- [X] T023 [US2] Add `POST /api/v1/loyalty/catalog/{catalog_entry_id}/redeem` to `loyalty_router.py` (T022), returning `{redemption_request_id, status, points_spent, balance_after}`.
- [X] T024 [US2] Implement `list_pending_queue(conn, page, limit)`, `fulfill_request(conn, redemption_request_id, admin_id)`, `reject_request(conn, redemption_request_id, admin_id, reason)` in `loyalty_service.py`, generalizing `car_maintenance_service.list_pending_queue`/`fulfill_reward`: `fulfill_request` mirrors the existing no-wallet-mutation fulfill (points already deducted at redeem time), writes `admin_audit_logs` (`action_type='approved'`, `redemption_request_id` set), enqueues `loyalty_redemption_fulfilled` notification; `reject_request` sets `status='rejected'`, calls `credit_points(..., reason='redemption_refund')` to refund `points_spent` (FR-012), writes `admin_audit_logs` (`action_type='rejected'`), enqueues `loyalty_redemption_rejected` notification.
- [X] T025 [US2] Create `services/api/app/api/admin/loyalty_router.py`: `GET /api/v1/admin/loyalty/queue` (T024 list), `POST /api/v1/admin/loyalty/queue/{id}/fulfill` (T024), `POST /api/v1/admin/loyalty/queue/{id}/reject` (T024), behind `get_current_admin`; mount in `main.py`. Remove `services/api/app/api/admin/car_maintenance_router.py` and its mount, and delete `services/api/app/services/car_maintenance_service.py` (fully superseded by T020/T022/T024 — no remaining callers).
- [X] T026 [P] [US2] Update `apps/main/src/app/(driver)/wallet/page.tsx`'s car-maintenance widget to link to a new `apps/main/src/app/(driver)/wallet/loyalty/` page (balance + transaction history + a "Redeem for car-maintenance credit" action calling T023 when eligible).
- [X] T027 [P] [US2] Replace `apps/admin/src/app/(dashboard)/car-maintenance/page.tsx` with `apps/admin/src/app/(dashboard)/loyalty/queue/page.tsx`: pending-queue table (T025 `GET`), fulfill/reject actions with a reason field for reject.
- [X] T028 [US2] Run `quickstart.md` Scenario 3 (accumulate → manual redeem → admin fulfill) and Scenario 5 (admin reject → refund) end-to-end; confirm all pass conditions, including that the T004-migrated driver balances/pending requests behave identically to newly-created ones.

**Checkpoint**: User Stories 1 AND 2 both work independently — passengers and drivers each earn and redeem points through their respective flows.

---

## Phase 5: User Story 3 - Passengers and Drivers Redeem Points for Vouchers (Priority: P3)

**Goal**: Both roles browse a shared, audience-filtered voucher catalog and redeem points for a voucher, instantly for standard vouchers or via the manual queue for flagged ones.

**Independent Test**: An admin publishes a voucher; a passenger or driver with sufficient points redeems it; confirm it appears in their redemption history and their points balance decreases by its cost.

### Implementation for User Story 3

- [X] T029 [US3] Verify T012's `list_catalog` and T022's `redeem_catalog_entry` already fully cover `voucher`-type entries with no code change (they were written type-agnostic in Phase 4) — confirm via a direct service-layer check that audience filtering (FR-007) and instant-vs-manual resolution (clarify answer) both work correctly for `voucher` rows.
- [X] T030 [US3] Verify NFR-002/FR-011's no-double-spend guarantee holds under concurrent voucher redemption: two simultaneous `redeem_catalog_entry` calls against an account with exactly one voucher's `point_cost` in balance — confirm via `get_account_with_lock`'s `SELECT ... FOR UPDATE` serializing the two transactions, one succeeds and one returns `409 insufficient_points`.
- [X] T031 [P] [US3] Add a voucher browse/redeem section to `apps/main/src/app/(passenger)/loyalty/` (T017) and `apps/main/src/app/(driver)/wallet/loyalty/` (T026): list `voucher`-type catalog entries (T016's `GET /catalog`), redeem action (T023), show redeemed vouchers (including retired ones, FR edge case) in transaction history.
- [X] T032 [US3] Run `quickstart.md` Scenario 4 (instant voucher redemption) and Scenario 6 (concurrent redemption, no double-spend) end-to-end; confirm all pass conditions.

**Checkpoint**: All user-facing stories (US1–US3) are independently functional.

---

## Phase 6: User Story 4 - Admin Manages the Loyalty Program (Priority: P4)

**Goal**: An admin creates/edits/retires vouchers, configures program-wide point costs/caps/percentages through the same admin screen, and works the fulfillment queue (queue endpoints already built in US2).

**Independent Test**: Create a voucher, edit its point cost, retire it; separately review and fulfill/reject a pending redemption request from the operations queue.

### Implementation for User Story 4

- [X] T033 [US4] Implement `create_voucher`, `update_catalog_entry`, `retire_catalog_entry` in `loyalty_service.py` (FR-008): `create_voucher` inserts a `type='voucher'` row; `update_catalog_entry` allows full field edits for `voucher` rows, but for the 3 system entries (`free_ride`/`discount`/`car_maintenance`) restricts edits to `point_cost` (writing to both the `loyalty_reward_catalog` row and the paired `platform_settings` key) plus — for `free_ride` — `loyalty_free_ride_max_fare_egp` and — for `discount` — `loyalty_discount_percentage` (FR-008a, research.md Decision 3); `retire_catalog_entry` sets `active=false` (soft retirement — in-flight redemptions still resolve, FR edge case).
- [X] T034 [US4] Add `GET /api/v1/admin/loyalty/catalog`, `POST /api/v1/admin/loyalty/catalog`, `PATCH /api/v1/admin/loyalty/catalog/{id}`, `DELETE /api/v1/admin/loyalty/catalog/{id}` (soft-retire) to `admin/loyalty_router.py` (T033), behind `get_current_admin`.
- [X] T035 [US4] Add `apps/admin/src/app/(dashboard)/loyalty/catalog/page.tsx`: table of all catalog entries (system + vouchers) with create/edit/retire actions; the system entries' edit form additionally exposes `loyalty_free_ride_max_fare_egp` (`free_ride` row) and `loyalty_discount_percentage` (`discount` row) per FR-008a acceptance scenario 1a ("on the loyalty program admin screen").
- [X] T036 [P] [US4] Add a `Loyalty` nav entry in `apps/admin/src/app/(dashboard)/layout.tsx` linking to both `loyalty/queue` (T027) and `loyalty/catalog` (T035), replacing the removed `car-maintenance` nav entry.
- [X] T037 [US4] Run `quickstart.md`'s remaining verification (voucher create/edit/retire via the admin catalog screen, settings field edit taking effect immediately per FR-008a acceptance 1a) and Scenario 8 (dual-role separate balances) end-to-end.

**Checkpoint**: All four user stories are independently functional — the full loyalty points feature works end-to-end.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T038 [P] Verify RLS policies on all 4 new tables (owner-read on accounts/transactions/redemption_requests, public-read on active catalog entries) via the Supabase dashboard or a direct SQL check, per `data-model.md`.
- [ ] T039 Run the full `quickstart.md` validation suite (all 8 scenarios) end-to-end against the local stack in one pass.
- [ ] T040 Confirm CI checks (typecheck/build/lint) pass for `services/api`, `apps/main`, and `apps/admin` changes.
- [ ] T041 [P] Add all new user-facing strings (loyalty balance/history/catalog/redeem UI in both apps, admin catalog+queue screens) to the message catalog (`en.json`/`ar.json`) and republish via `services/api/scripts/publish_message_catalog.py` before considering the UI text live.
- [ ] T042 Confirm no remaining references to `car_maintenance_service`/`car_maintenance_router` exist anywhere in `services/api` (grep check) after T025's removal.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion.
  - US1 and US2 are architecturally independent of each other (separate roles, separate accounts) but both depend on the Phase 2 primitives.
  - US3 depends on US2's `redeem_catalog_entry`/`list_catalog` (T012, T022) already existing (built type-agnostic in Phase 4) — it adds no new backend logic, only verification + UI.
  - US4's queue-fulfillment surface (admin `fulfill`/`reject`) is built in US2 (T024/T025); US4 adds catalog CRUD + settings-editing on top.
- **Polish (Phase 7)**: Depends on all four user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2). No dependencies on other stories.
- **User Story 2 (P2)**: Can start after Foundational (Phase 2). No dependencies on US1 (separate role/account); shares no code with US1 except the Phase 2 primitives.
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) in principle, but its independent test needs an admin-published voucher and US2's generic redeem endpoint (T022/T023) to exist — practically sequenced after US2.
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) in principle, but its queue-review independent test needs a pending request, which requires US2's redemption flow — practically sequenced after US2.

### Within Each User Story

- Service logic before endpoints; endpoints before UI; UI before the `quickstart.md` validation task.
- Story complete before moving to the next priority.

### Parallel Opportunities

- T003/T004 (seed data, migrated data) are part of the same T002 migration file and must be written together, but T006/T007 (separate migration files) can be authored in parallel with T002-T004.
- T008 (Pydantic models) can run in parallel with T002-T007.
- T017, T018 (US1 frontend) can run in parallel with each other once T014/T016 land.
- T026, T027 (US2 frontend) can run in parallel with each other once T023/T025 land.
- T031 (US3 frontend) can run in parallel with T029/T030 (US3 verification).
- T036 (US4 nav) can run in parallel with T033-T035.
- T038 and T041 (Polish) can run in parallel with each other.

---

## Parallel Example: User Story 1

```bash
# Once T009-T016 are done, launch these together (different files):
Task: "Add passenger loyalty balance+history page in apps/main/src/app/(passenger)/loyalty/"
Task: "Add points-redemption step to passenger booking flow in apps/main/src/app/(passenger)/rides/"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories, includes the car-maintenance→points data migration).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: Run `quickstart.md` Scenarios 1, 2, and 7 independently.
5. Deploy/demo if ready — passengers already earn and redeem points, even before the driver car-maintenance generalization (US2), vouchers (US3), or admin catalog/settings UI (US4) exist. Note: driver-side data migration (T004) still needs to ship alongside Foundational regardless of US2's timing, since it's a one-time schema/data change tied to the migration file, not to US2's code.

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (includes data migration).
2. Add User Story 1 → validate → deploy/demo (MVP! passenger earn/redeem).
3. Add User Story 2 → validate → deploy/demo (driver earn/redeem, admin queue live, `car_maintenance_service` removed).
4. Add User Story 3 → validate → deploy/demo (vouchers for both roles).
5. Add User Story 4 → validate → deploy/demo (admin catalog CRUD + settings editing).
6. Each story adds value without breaking previous stories.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps task to specific user story for traceability.
- T022 (`redeem_catalog_entry`) is written type-agnostic in US2 and reused unchanged by US3 (vouchers) — this is why US3 has no new service-layer tasks, only verification + UI.
- T024/T025 (admin queue fulfill/reject) are built in US2 (needed for car-maintenance's Independent Test) and reused unchanged by US4's manual-voucher case.
- Commit after each task or logical group.
- Stop at any checkpoint to validate story independently.
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence.
