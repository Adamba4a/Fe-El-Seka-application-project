---

description: "Task list for Sponsored Groups implementation"
---

# Tasks: Sponsored Groups

**Input**: Design documents from `specs/026-sponsored-groups/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: No dedicated automated API test suite exists in this repo (per plan.md Technical Context) — validation is via the `quickstart.md` scenarios, referenced as dedicated tasks at the end of each story.

**Organization**: Tasks are grouped by user story (from spec.md) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- File paths are relative to the repository root (`D:\Business\Fe El Seka app`)

## Path Conventions

Per plan.md Project Structure: `services/api/app/{models,services,api}` (FastAPI backend), `apps/main/src` (passenger frontend), `apps/admin/src` (admin frontend), `supabase/migrations/` (schema).

---

## Phase 1: Setup

**Purpose**: Confirm environment readiness — no new dependencies are required for this feature.

- [X] T001 Verify Technical Context per plan.md: no new Python or Node packages are needed (existing FastAPI/asyncpg/Pydantic v2 and Next.js 14/Tailwind/shadcn stack covers this feature); confirm the local Supabase stack and `services/api` (`uvicorn`) start cleanly per `quickstart.md` prerequisites.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema and shared model changes every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Write migration `supabase/migrations/<timestamp>_sponsored_groups.sql` per `data-model.md`: `ALTER TABLE groups ADD COLUMN is_sponsored boolean NOT NULL DEFAULT false`, `funded_balance_egp numeric(12,2) NOT NULL DEFAULT 0.00`, `dashboard_contact_user_id uuid NULL REFERENCES profiles(id)` + `CHECK (NOT is_sponsored OR type IN ('company','university'))` + `CHECK (funded_balance_egp >= 0.00)`; `ALTER TABLE bookings ADD COLUMN payment_source text NOT NULL DEFAULT 'CASH' CHECK (payment_source IN ('CASH','SPONSORED'))`; three separate `ALTER TYPE ledger_entry_type ADD VALUE 'SPONSORED_RIDE_CREDIT'` / `'SPONSORED_RIDE_REVERSAL'` / `'WITHDRAWAL_DEBIT'` statements (each must be its own statement/transaction per Postgres enum-alter rules — do not combine with a statement that uses the new value); `CREATE TABLE withdrawal_requests` with all columns from data-model.md (`id, driver_id, amount_egp, payout_reference, status, rejection_reason, reviewed_by, reviewed_at, ledger_entry_id, created_at, updated_at`) plus the three indexes (`uq_withdrawal_one_pending_per_driver`, `idx_withdrawal_pending_queue`, `idx_withdrawal_driver_history`) and RLS policies mirroring `wallet_topup_requests` (`driver_read_own_withdrawal_request`, `driver_insert_own_withdrawal_request`, no UPDATE/DELETE policy).
- [X] T003 Apply the migration from T002 to the local Supabase stack and verify all new columns/table/enum values/indexes/RLS policies exist as expected.
- [X] T004 [P] Extend `services/api/app/models/group.py`: add `is_sponsored: bool`, `funded_balance_egp: Decimal`, `dashboard_contact_user_id: Optional[UUID]` to `GroupSummary`/`GroupDetailResponse`; add new request/response schemas `SponsoredGroupCreateRequest`, `AddFundsRequest`, `AddFundsResponse`, `DashboardContactRequest`, `SponsorshipDashboardResponse` per `contracts/api.md`.
- [X] T005 [P] Extend `services/api/app/models/wallet.py`: add `SPONSORED_RIDE_CREDIT`, `SPONSORED_RIDE_REVERSAL`, `WITHDRAWAL_DEBIT` to `LedgerEntryType(str, Enum)`.
- [X] T006 [P] Create `services/api/app/models/withdrawal.py`: `WithdrawalSubmitRequest`, `WithdrawalResponse`, `WithdrawalHistoryItem`, `AdminWithdrawalQueueItem`, `AdminWithdrawalApproveResponse`, `AdminWithdrawalRejectRequest`/`Response` — mirrors `wallet_topup.py`'s shape in reverse, per `contracts/api.md`.

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Admin Creates and Funds a Sponsored Group (Priority: P1) 🎯 MVP

**Goal**: An admin can create a sponsored group tied to a domain with a funded balance, top it up later, and auto-upgrading an existing non-sponsored domain group instead of duplicating it.

**Independent Test**: Admin creates a sponsored group tied to a domain and sets a funded balance; confirm the balance is visible on the group's record. Repeat against an existing non-sponsored domain group and confirm in-place upgrade, not a duplicate.

### Implementation for User Story 1

- [X] T007 [US1] Implement `create_or_upgrade_sponsored_group` in new `services/api/app/services/sponsored_group_service.py`: if no group exists for the domain, create one with `is_sponsored=true` and the given `funded_balance_egp`; if a non-sponsored group exists for the domain, upgrade it in place (set `is_sponsored=true`, apply the funded balance) instead of creating a second record (FR-003, research.md §1); if an already-sponsored group exists for the domain, raise `409 already_sponsored`.
- [X] T008 [US1] Implement `add_funds` in `services/api/app/services/sponsored_group_service.py`: lock the group row `FOR UPDATE`, increment `funded_balance_egp` by the requested amount (FR-002); `404` unknown group, `422` if the group is not sponsored.
- [X] T009 [US1] Create `services/api/app/api/admin/sponsored_groups_router.py` with `POST /api/admin/sponsored-groups` (calls T007) and `POST /api/admin/sponsored-groups/{group_id}/add-funds` (calls T008), both behind `get_current_admin` per `contracts/api.md`.
- [X] T010 [US1] Mount `sponsored_groups_router` in `services/api/app/main.py` alongside the existing `admin_wallet_topup_router`.
- [X] T011 [P] [US1] Add admin UI page `apps/admin/src/app/sponsored-groups/page.tsx`: form to create-or-auto-upgrade a sponsored group by domain + initial funded balance, and an add-funds action on an existing sponsored group.
- [X] T012 [US1] Run `quickstart.md` Scenario 1 (auto-upgrade an existing domain group to sponsored) end-to-end; confirm both pass conditions (in-place upgrade, `409` on repeat).

**Checkpoint**: User Story 1 is fully functional and testable independently — sponsored groups can be created and funded via admin.

---

## Phase 4: User Story 2 - Member Books a Free Sponsored Ride (Priority: P1)

**Goal**: A domain-verified member of a sponsored group books a seat with no cash step; the company's balance is debited, the driver is credited net-of-commission immediately, and the cash-ride commission-reservation pipeline is bypassed entirely.

**Independent Test**: Seed a funded sponsored group and a group-scoped ride (can be done directly against the schema from Phase 2/3 without any US1 UI); have a domain-verified member book a seat; confirm the group's balance decreases by the full seat price, the driver's wallet increases by seat price minus commission, and no cash/reservation step occurred.

### Implementation for User Story 2

- [X] T013 [P] [US2] Extend `create_booking` in `services/api/app/services/booking_service.py`: after the existing group-membership check, branch when the ride's group has `is_sponsored=true` — lock the group row `FOR UPDATE` in the same transaction as the seat claim, compute `total_seat_price`, reject with `422 insufficient_funded_balance` if the balance can't cover it (no seats claimed, FR-008), else debit `groups.funded_balance_egp`, compute the driver's net-of-commission credit using the same per-seat formula `commission_service.deduct_commission` uses, credit the driver's wallet via `wallet_service.increment_balance`, insert a `SPONSORED_RIDE_CREDIT` ledger entry (`ride_id`, `booking_id`), and set the booking's `payment_source='SPONSORED'` (research.md §4).
- [X] T014 [P] [US2] Extend `create_ride` in `services/api/app/services/ride_service.py`: extend the existing group-membership lookup to also select `g.is_sponsored`; when true, skip `check_available_balance`/`create_reservation` entirely — no wallet lock, no `commission_reservations` row (research.md §6).
- [X] T015 [US2] Extend `complete_ride` in `services/api/app/services/ride_service.py`: filter the `confirmed_bookings` query that feeds `deduct_commission` with `AND payment_source = 'CASH'`; leave `complete_ride_bookings` (the status-transition query) unchanged (research.md §5).
- [X] T016 [US2] Extend the booking-cancellation flow in `services/api/app/services/booking_service.py`: when cancelling a `payment_source='SPONSORED'` booking, run the inverse of T013 in the same transaction — lock the group row, credit `groups.funded_balance_egp` back by the seat price, debit the driver's wallet via `wallet_service.decrement_balance` (negative-balance tolerant), insert a `SPONSORED_RIDE_REVERSAL` ledger entry referencing the same `booking_id` (research.md §11, FR-010).
- [X] T017 [US2] Run `quickstart.md` Scenarios 2, 3, 4, 5 (automatic settlement, insufficient-balance rejection, no double-charge at completion, cancellation reversal) end-to-end; confirm all pass conditions.

**Checkpoint**: User Stories 1 AND 2 both work independently — sponsored bookings settle automatically end-to-end without touching the cash-ride commission pipeline.

---

## Phase 5: User Story 3 - Driver Withdraws Earned Balance (Priority: P1)

**Goal**: A driver submits a withdrawal request against their wallet balance; an admin reviews, approves (debiting the wallet) or rejects it.

**Independent Test**: A driver with a positive available wallet balance (from cash rides alone — no dependency on US1/US2) submits a withdrawal request at or below that balance; an admin approves it; confirm the wallet balance is debited by the approved amount.

### Implementation for User Story 3

- [X] T018 [US3] Implement `services/api/app/services/withdrawal_service.py`: `submit_request` (validates requested amount against `balance_egp - reserved_egp`, relies on the DB partial-unique-index for one-pending-per-driver, `409 pending_request_exists` on conflict), `list_driver_history`, `list_pending_queue` (oldest-first), `approve_request` (re-validates available balance under the wallet's row lock at approval time — `409 insufficient_balance_at_approval` if it no longer covers the amount, per research.md §10 — else debits the wallet and inserts a `WITHDRAWAL_DEBIT` ledger entry), `reject_request` (mandatory `reason`) — mirrors `wallet_topup_service.py` in reverse.
- [X] T019 [P] [US3] Create `services/api/app/api/wallet_withdrawals/router.py`: `POST /api/wallet/withdrawals` and `GET /api/wallet/withdrawals` (driver-facing, `get_current_user`), calling T018.
- [X] T020 [P] [US3] Create `services/api/app/api/admin/withdrawal_router.py`: `GET /api/admin/withdrawal-requests`, `GET /api/admin/withdrawal-requests/history`, `POST /api/admin/withdrawal-requests/{request_id}/approve`, `POST /api/admin/withdrawal-requests/{request_id}/reject` — mirrors `admin_wallet_topup_router.py`, calling T018.
- [X] T021 [US3] Mount both `wallet_withdrawals_router` and `admin_withdrawal_router` in `services/api/app/main.py`.
- [X] T022 [P] [US3] Add admin UI page `apps/admin/src/app/withdrawal-requests/page.tsx`, mirroring the existing wallet-topup-requests admin page (pending queue, history, approve/reject actions).
- [X] T023 [US3] Run `quickstart.md` Scenarios 7, 8 (one pending withdrawal at a time; approval re-checks balance at review time) end-to-end; confirm all pass conditions.

**Checkpoint**: User Stories 1, 2, AND 3 all work independently — drivers can withdraw wallet balance via admin review.

---

## Phase 6: User Story 4 - Company Views Sponsorship Dashboard (Priority: P2)

**Goal**: A sponsored group's designated, already-verified-member dashboard contact can view a read-only summary of remaining funded balance and sponsored activity; no one else can.

**Independent Test**: Designate an existing member as a sponsored group's dashboard contact; produce a few sponsored bookings (via US2); confirm that contact's dashboard shows the correct balance/activity while a non-designated member is denied access.

### Implementation for User Story 4

- [X] T024 [US4] Extend `services/api/app/services/group_service.py`: add `set_dashboard_contact(group_id, admin_id, user_id)` validating the target is an existing row in `group_memberships` for that group (`422 not_a_group_member` if not, per FR-020/research.md §12) — mirrors the validation pattern in `transfer_ownership`.
- [X] T025 [US4] Extend `services/api/app/services/group_service.py`: add `get_sponsorship_dashboard(group_id, requesting_user_id)` returning `funded_balance_egp`, `member_count`, and recent `SPONSORED_RIDE_CREDIT`/`SPONSORED_RIDE_REVERSAL` ledger activity for the group; `403` if the requester is not `dashboard_contact_user_id`, `404` if the group is not found or not sponsored.
- [X] T026 [US4] Add `POST /api/admin/sponsored-groups/{group_id}/dashboard-contact` to `services/api/app/api/admin/sponsored_groups_router.py` (calls T024).
- [X] T027 [US4] Add `GET /api/groups/{group_id}/sponsorship-dashboard` to the existing `services/api/app/api/groups/router.py` (calls T025).
- [X] T028 [P] [US4] Extend `apps/admin/src/app/sponsored-groups/page.tsx` (from T011) with a dashboard-contact assignment control, selecting from the group's existing members.
- [X] T029 [P] [US4] Add read-only page `apps/main/src/app/(passenger)/sponsorship-dashboard/[groupId]/page.tsx`: displays funded balance and recent sponsored activity, gated to the signed-in dashboard contact.
- [X] T030 [US4] Run `quickstart.md` Scenario 6 (dashboard contact must already be a member; non-contact gets `403`) end-to-end; confirm all pass conditions.

**Checkpoint**: User Stories 1–4 all work independently — sponsoring organizations can view their dashboard.

---

## Phase 7: User Story 5 - Remove Departed Member's Sponsored Access (Priority: P2)

**Goal**: Removing a member from a sponsored group (existing Groups/024 capability) immediately cuts off their ability to book further sponsored rides, without affecting their historical bookings.

**Independent Test**: Remove a member from a sponsored group; confirm they can no longer book rides scoped to that group, while their already-completed bookings remain unaffected.

### Implementation for User Story 5

- [X] T031 [US5] Manually verify FR-021 against the T013 sponsored-booking branch: remove a member from a sponsored group via the existing Groups (024) owner/admin removal flow, confirm the existing group-membership check in `create_booking` (which runs before the sponsorship branch) already rejects further booking attempts from the removed member, and confirm their prior completed sponsored bookings remain unaffected in the driver's ledger and the company dashboard (T025). No code change is expected — this story reuses Spec 024's existing capability entirely.

**Checkpoint**: All user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T032 [P] Verify `withdrawal_requests` RLS policies match `wallet_topup_requests` exactly (driver-own SELECT/INSERT only, no UPDATE/DELETE policy) via the Supabase dashboard or a direct SQL check, per `data-model.md` RLS Summary.
- [X] T033 Run the full `quickstart.md` validation suite (all 8 scenarios) end-to-end against the local stack in one pass.
- [X] T034 Confirm CI checks (typecheck/build/lint) pass for the `services/api`, `apps/main`, and `apps/admin` changes.
- [X] T035 [P] Add any new user-facing strings (sponsored-group admin UI, withdrawal UI, company dashboard) to the message catalog (`en.json`/`ar.json`) and republish via `services/api/scripts/publish_message_catalog.py` before considering the UI text live.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **User Stories (Phase 3–7)**: All depend on Foundational completion.
  - US1, US2, US3 (all P1) have no dependencies on each other and can proceed in parallel if staffed, or sequentially in the order below for a single implementer.
  - US4 (P2) depends on US2 existing (needs sponsored bookings to display) and reuses the admin UI page created in US1 (T011).
  - US5 (P2) is verification-only and depends on US2's booking branch (T013) existing.
- **Polish (Phase 8)**: Depends on all desired user stories being complete.

### Recommended Implementation Order

1. Setup → Foundational (T001–T006)
2. US1 (T007–T012) — 🎯 MVP checkpoint
3. US2 (T013–T017)
4. US3 (T018–T023)
5. US4 (T024–T030)
6. US5 (T031)
7. Polish (T032–T035)

### Within Each User Story

- Services before routers before UI before verification.
- Tasks touching the same file (e.g., T007+T008 in `sponsored_group_service.py`; T013+T016 in `booking_service.py`; T014+T015 in `ride_service.py`; T024+T025 in `group_service.py`) are sequential, not parallel, even when not both explicitly marked.

### Parallel Opportunities

- Foundational: T004, T005, T006 (different model files) can run in parallel once T002/T003 are underway.
- US1: T011 (admin UI) can run in parallel with T007–T010 (backend).
- US2: T013 (`booking_service.py`) and T014 (`ride_service.py` create_ride) touch different files and can run in parallel; T015 must follow T014 (same file), T016 must follow T013 (same file).
- US3: T019 and T020 (different router files) can run in parallel once T018 is done; T022 (admin UI) can run in parallel with all backend US3 tasks.
- US4: T028 and T029 (different frontend files) can run in parallel once their respective backend endpoints (T026, T027) exist.
- Polish: T032 and T035 can run in parallel with T033/T034.

---

## Parallel Example: Foundational Phase

```bash
# After T002 (migration written) and T003 (migration applied):
Task: "Extend services/api/app/models/group.py with sponsorship fields + new request/response schemas"
Task: "Extend services/api/app/models/wallet.py LedgerEntryType enum"
Task: "Create services/api/app/models/withdrawal.py"
```

## Parallel Example: User Story 2

```bash
Task: "Extend create_booking in services/api/app/services/booking_service.py with sponsored-settlement branch"
Task: "Extend create_ride in services/api/app/services/ride_service.py to skip reservation for sponsored groups"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (schema + shared models — CRITICAL, blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run quickstart.md Scenario 1 independently
5. Deploy/demo if ready — a funded, addressable sponsorship account exists even before booking logic

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → validate (Scenario 1) → MVP demo
3. Add US2 → validate (Scenarios 2–5) → sponsored bookings settle end-to-end
4. Add US3 → validate (Scenarios 7–8) → drivers can cash out
5. Add US4 → validate (Scenario 6) → sponsor visibility
6. Add US5 → verify (no new code) → risk mitigation confirmed
7. Polish → full quickstart.md pass (T033), CI green (T034)

---

## Notes

- [P] tasks = different files, no unresolved dependency on an incomplete task.
- [Story] label maps each task to its user story for traceability; Setup/Foundational/Polish tasks carry no story label by design.
- No automated test suite exists in this repo (per plan.md) — `quickstart.md` scenarios are the acceptance mechanism, referenced as explicit verification tasks at the end of each story phase.
- Avoid: parallelizing same-file edits across tasks (see Dependencies note above), scope creep beyond the FRs in spec.md.
