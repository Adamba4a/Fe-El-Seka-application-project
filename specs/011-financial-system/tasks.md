# Tasks: Financial System (Phase 8)

**Input**: Design documents from `specs/011-financial-system/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/api.md ✅ | contracts/frontend-pages.md ✅ | quickstart.md ✅

**Tests**: Not included — not explicitly requested in spec.md. Run `quickstart.md` validation scenarios manually after each story checkpoint.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies within the phase)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths included in all task descriptions

---

## Phase 1: Setup (Database Schema)

**Purpose**: Create all 4 migration SQL files that establish the Phase 8 schema. These are file-creation tasks only — no runtime dependencies between them. Apply all migrations with `supabase db push` after all 4 files exist.

- [x] T001 [P] Create `supabase/migrations/20260629000005_phase8_driver_wallets.sql` — `driver_wallets` table (`id UUID PK`, `driver_id UUID UNIQUE FK→users`, `balance_egp NUMERIC(12,2) DEFAULT 0`, `reserved_egp NUMERIC(12,2) DEFAULT 0 CHECK(>=0)`, `created_at`, `updated_at`); RLS: drivers SELECT own row, no INSERT/UPDATE policy (backend uses service role); admin SELECT all
- [x] T002 [P] Create `supabase/migrations/20260629000006_phase8_commission_reservations.sql` — `commission_reservations` table (`id UUID PK`, `wallet_id UUID FK→driver_wallets`, `driver_id UUID FK→users`, `ride_id UUID UNIQUE FK→rides`, `reserved_amount_egp NUMERIC(10,2) CHECK(>0)`, `created_at`); RLS: drivers SELECT own rows; `CREATE INDEX idx_commission_reservations_driver_id ON commission_reservations(driver_id)`
- [x] T003 [P] Create `supabase/migrations/20260629000007_phase8_driver_ledger.sql` — `ledger_entry_type` enum (`COMMISSION_DEBIT`, `ADMIN_CREDIT`, `ADMIN_DEBIT`); `driver_ledger_entries` table (`id UUID PK`, `wallet_id UUID FK→driver_wallets`, `driver_id UUID FK→users`, `type ledger_entry_type NOT NULL`, `amount_egp NUMERIC(10,2) CHECK(>=0)`, `ride_id UUID nullable FK→rides`, `booking_id UUID nullable FK→bookings`, `fuel_cost_egp_snapshot NUMERIC(10,2) nullable`, `created_by UUID nullable FK→users`, `note TEXT nullable`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`); `REVOKE UPDATE, DELETE ON driver_ledger_entries FROM authenticated, anon`; RLS: drivers SELECT own rows, passengers NO access, admin SELECT all
- [x] T004 [P] Create `supabase/migrations/20260629000008_phase8_indexes.sql` — admin wallet indexes (`wallet_id, created_at DESC`), balance index, orphan-detection comment
- [x] T005 Apply all Phase 8 migrations: `supabase db push` (run after T001–T004 are complete); verify all 4 tables exist and RLS + privilege grants are in place

**Checkpoint**: All 3 new tables exist in the database with correct RLS policies and privilege grants. `\d driver_wallets`, `\d commission_reservations`, `\d driver_ledger_entries` all return expected schemas.

---

## Phase 2: Foundational (Shared Backend Infrastructure)

**Purpose**: Core Pydantic schemas and the wallet service that ALL four user stories depend on. No user story work can begin until this phase is complete.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T006 Create `services/api/app/models/wallet.py` — Pydantic schemas: `LedgerEntryResponse` (all ledger fields, `amount_egp: Decimal`, `type: LedgerEntryType` enum), `WalletSummaryResponse` (`balance_egp`, `reserved_egp`, `available_egp` as computed `@property`), `WalletPageResponse` (`WalletSummaryResponse` + `entries: list[LedgerEntryResponse]` + `pagination`), `TopUpRequest` (`amount_egp: Decimal > 0`, `note: str | None`), `TopUpResponse`, `AdjustRequest` (`amount_egp: Decimal > 0`), `AdjustResponse`; all `Decimal` fields use `max_digits` and `decimal_places` constraints; import `Decimal` from Python standard library
- [x] T007 Implement `services/api/app/services/wallet_service.py` — functions: `get_or_create_wallet(conn, driver_id) → dict` (INSERT...ON CONFLICT DO NOTHING, then SELECT); `get_wallet_with_lock(conn, driver_id) → dict` (SELECT...FOR UPDATE — returns wallet row or creates then locks); `increment_balance(conn, wallet_id, amount: Decimal)` (UPDATE balance_egp += amount); `decrement_balance(conn, wallet_id, amount: Decimal)` (UPDATE balance_egp -= amount); `increment_reserved(conn, wallet_id, amount: Decimal)`; `decrement_reserved(conn, wallet_id, amount: Decimal)`; `insert_ledger_entry(conn, wallet_id, driver_id, entry_type, amount, *, ride_id=None, booking_id=None, fuel_cost_snapshot=None, created_by=None, note=None) → dict`; `get_ledger_page(conn, driver_id, page, per_page=50) → (list[dict], int)`; all `amount` parameters typed as `Decimal`; all arithmetic uses `Decimal` — never `float`

**Checkpoint**: `wallet_service.py` functions are importable and unit-testable against the migrated database schema with no errors.

---

## Phase 3: User Story 1 — Commission Deduction on Ride Completion (Priority: P1) 🎯 MVP

**Goal**: When a driver completes a ride, the platform automatically deducts proportional commission from their wallet for each confirmed booking, in the same atomic transaction as ride completion.

**Independent Test**: From `quickstart.md` Scenario 1 — create a 4-seat ride (`fuel_cost_egp = 40.00`), confirm 2 bookings, complete the ride, verify: reservation deleted, 2 `COMMISSION_DEBIT` entries of 2.00 EGP each, `balance_egp` decreased by 4.00, `reserved_egp` decreased by 8.00.

- [x] T008 [US1] Implement `services/api/app/services/commission_service.py` — functions: `deduct_commission(conn, ride_id, driver_id, fuel_cost_egp: Decimal, total_seat_count: int, completed_booking_ids: list[str])` — for each booking_id, compute `amount = ROUND(fuel_cost_egp * Decimal("0.20") / total_seat_count, 2)`, call `wallet_service.insert_ledger_entry(type=COMMISSION_DEBIT, ...)` and `wallet_service.decrement_balance(...)`; `release_reservation(conn, ride_id, driver_id)` — DELETE from `commission_reservations` WHERE `ride_id`, call `wallet_service.decrement_reserved(...)` by the deleted amount; all inside the caller's transaction (no new transaction started here)
- [x] T009 [US1] Extend `services/api/app/services/ride_service.py` `complete_ride()` — inside the existing transaction, after bookings transition to `completed`, collect confirmed booking IDs, read `ride.fuel_cost_egp` and `ride.total_seat_count`, call `commission_service.deduct_commission()`, call `commission_service.release_reservation()`; if ride has zero confirmed bookings, skip deduct_commission but still call release_reservation; ensure the wallet lock (`get_wallet_with_lock`) is acquired before any balance writes
- [x] T010 [US1] Extend `services/api/app/services/ride_service.py` `cancel_ride()` — inside the cancellation transaction, call `commission_service.release_reservation(conn, ride_id, driver_id)` after setting `rides.status = 'cancelled'`; no-op if no reservation exists (first cancellation attempt before ride creation completed)
- [x] T011 [US1] Extend `services/api/app/services/booking_service.py` booking-expiry cancellation path — N/A: the expiry loop cancels individual bookings only, never rides; no ride auto-cancellation path exists in the current codebase; T010's cancel_ride() covers all ride cancellation scenarios

**Checkpoint**: Complete a ride with 2 confirmed bookings via the API. Verify via `quickstart.md` Scenario 1 SQL checks: reservation deleted, correct ledger entries, wallet balances updated correctly. Roll back the transaction mid-deduction and verify the ride stays `in_progress` with no ledger entries created.

---

## Phase 4: User Story 2 — Admin Manually Tops Up Driver Wallet (Priority: P2)

**Goal**: An authenticated admin can credit a driver's wallet with a specified EGP amount through the admin panel, creating an immutable `ADMIN_CREDIT` ledger entry.

**Independent Test**: From `quickstart.md` Scenario 2 — `POST /admin/drivers/{id}/wallet/topup` with 200.00 EGP as admin; verify `ADMIN_CREDIT` entry in ledger; verify HTTP 403 when called with a driver JWT.

- [x] T012 [P] [US2] Create `services/api/app/api/admin/wallet_router.py` — `POST /admin/drivers/{driver_id}/wallet/topup` endpoint: validate `amount_egp > 0` (HTTP 422 if not); acquire wallet lock via `wallet_service.get_wallet_with_lock()`; call `wallet_service.increment_balance()` and `wallet_service.insert_ledger_entry(type=ADMIN_CREDIT, created_by=admin_user_id)`; return `TopUpResponse`; admin auth enforced via existing admin middleware; `POST /admin/drivers/{driver_id}/wallet/adjust` endpoint: validate `amount_egp > 0`; acquire wallet lock; check `amount_egp <= wallet.available_egp` (HTTP 422 with `DEBIT_EXCEEDS_AVAILABLE_BALANCE` if not, include `available_egp`, `balance_egp`, `reserved_egp` in error detail); call `wallet_service.decrement_balance()` and `wallet_service.insert_ledger_entry(type=ADMIN_DEBIT)`; return `AdjustResponse`
- [x] T013 Register `wallet_router` in `services/api/app/main.py` — imported as `admin_wallet_router` and mounted at `/api/admin/drivers` (actual registration is in main.py, not admin/__init__.py which is empty)
- [x] T014 [P] [US2] Create `apps/admin/src/components/wallet/AdminWalletSummary.tsx` — displays `balance_egp`, `reserved_egp`, `available_egp` as three labeled figures; formats all amounts with `Intl.NumberFormat` as EGP (`#,##0.00 EGP`); accepts wallet summary as props
- [x] T015 [P] [US2] Create `apps/admin/src/components/wallet/TopUpForm.tsx` — controlled form with `amount_egp` (number input, positive only) and `note` (text, optional); submit calls `POST /admin/drivers/{id}/wallet/topup`; on success show green toast with new balance; on error show inline validation message; calls parent `onSuccess` callback to trigger wallet refetch
- [x] T016 [P] [US2] Create `apps/admin/src/components/wallet/AdjustForm.tsx` — same structure as TopUpForm; shows hint "Max debit: {available_egp} EGP"; submit calls `POST /admin/drivers/{id}/wallet/adjust`; on 422 `DEBIT_EXCEEDS_AVAILABLE_BALANCE` show inline error with max allowable debit from response `detail.available_egp`
- [x] T017 [P] [US2] Create `apps/admin/src/components/wallet/AdminLedgerTable.tsx` — table of ledger entries; columns: Type (human-readable label), Amount (signed, coloured), Ride ID prefix, Note, Date; newest-first; no pagination for MVP (admin can scroll)
- [x] T018 [US2] Create `apps/admin/src/app/(dashboard)/drivers/[id]/wallet/page.tsx` — client component that fetches wallet data; renders `AdminWalletSummary`, inline accordion for `TopUpForm` and `AdjustForm`, and `AdminLedgerTable`; on mutation success, refetches wallet summary via `load()` callback

**Checkpoint**: Log in as admin, navigate to a driver's wallet page, top up 200.00 EGP, verify balance increases. Attempt top-up as a non-admin, verify HTTP 403. Attempt corrective debit exceeding available balance, verify HTTP 422 with correct max debit hint.

---

## Phase 5: User Story 3 — Driver Views Wallet Balance and Transaction History (Priority: P3)

**Goal**: A driver can see their total balance, reserved amount, available balance, and paginated transaction history from the driver app.

**Independent Test**: From `quickstart.md` Scenario 3 — `GET /drivers/me/wallet` returns correct three balance figures; entries ordered newest-first; non-driver JWT returns HTTP 403.

- [x] T019 [P] [US3] Create `services/api/app/api/wallet/__init__.py` — empty module init file
- [x] T020 [P] [US3] Create `services/api/app/api/wallet/router.py` — `GET /drivers/me/wallet` endpoint: extract `driver_id` from JWT; call `wallet_service.get_or_create_wallet()` (returns 0.00 balances if no wallet); call `wallet_service.get_ledger_page(page, per_page=50)`; compute `available_egp = balance_egp - reserved_egp`; return wallet dict; enforce driver role — HTTP 403 if not driver
- [x] T021 Register wallet router in `services/api/app/main.py` — included as `wallet_router` at prefix `/api/v1/drivers/me` with tag "wallet"
- [x] T022 [P] [US3] Create `apps/main/src/lib/api/wallet.ts` — `getWallet(token, page?): Promise<WalletResponse>`; `formatEgp(amount): string` using `Intl.NumberFormat` with EGP locale; typed `LedgerEntry` and `WalletResponse` interfaces
- [x] T023 [P] [US3] Create `apps/main/src/components/wallet/WalletBalanceCard.tsx` — available balance prominent; total and reserved as secondary; reserved row hidden when `reserved_egp === "0.00"`
- [x] T024 [P] [US3] Create `apps/main/src/components/wallet/LedgerEntryRow.tsx` and `LedgerEntryList.tsx` — type labels, signed colours, ride link for COMMISSION_DEBIT, relative timestamp; Load more button appends entries page by page
- [x] T025 [US3] Create `apps/main/src/app/(driver)/wallet/page.tsx` — client component; loads on mount; empty state message; refetches on `visibilitychange` event (tab regains focus)

**Checkpoint**: Open the driver wallet screen, verify all three balance figures are displayed correctly, verify paginated transaction list matches DB, verify a new driver sees empty state with 0.00 EGP.

---

## Phase 6: User Story 4 — Balance Enforcement at Ride Creation (Priority: P4)

**Goal**: When a driver creates a ride, the system atomically checks their available balance against the ride's max commission and, if sufficient, reserves the commission — preventing over-commitment across simultaneous rides.

**Independent Test**: From `quickstart.md` Scenarios 4 and 5 — set wallet to 10.00 EGP, create one ride (reservation 4.00), attempt second ride needing 8.00 EGP commission from 6.00 available — expect HTTP 422 `INSUFFICIENT_WALLET_BALANCE`; cancel first ride and verify reservation released.

- [x] T026 [US4] Add reservation functions to `services/api/app/services/commission_service.py` — `check_available_balance(wallet: dict, max_commission: Decimal) -> bool` returns `(wallet["balance_egp"] - wallet["reserved_egp"]) >= max_commission`; `create_reservation(conn, wallet_id, driver_id, ride_id, reserved_amount: Decimal)` — INSERT into `commission_reservations`, call `wallet_service.increment_reserved(conn, wallet_id, reserved_amount)`; both execute inside the caller's transaction
- [x] T027 [US4] Extend `services/api/app/services/ride_service.py` `create_ride()` — before the ride INSERT, within the same transaction: (1) compute `max_commission = ROUND(fuel_cost_egp * Decimal("0.20"), 2)`; (2) acquire wallet lock via `wallet_service.get_wallet_with_lock()` (creates wallet row if absent); (3) call `commission_service.check_available_balance(wallet, max_commission)` — if False, raise HTTP 422 with `error_code = "INSUFFICIENT_WALLET_BALANCE"` and detail `{available_egp, required_commission_egp, balance_egp, reserved_egp}`; (4) insert ride; (5) call `commission_service.create_reservation(conn, wallet_id, driver_id, ride_id, max_commission)`; steps 1–5 all inside one transaction so rollback on any step leaves no ride and no reservation

**Checkpoint**: Run `quickstart.md` Scenarios 4 and 5. Verify: single ride creation succeeds and reservation appears; over-balance attempt returns HTTP 422 with correct amounts; concurrent creation race condition test shows exactly one success and one 422.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Observability, navigation, and end-to-end validation across all stories.

- [ ] T028 [P] Verify structured log entries — in `wallet_service.py` and `commission_service.py`, ensure every write operation emits a structured log at INFO level per `contracts/api.md` (fields: `event`, `operation`, `driver_id`, `amount_egp`, `ride_id`, `booking_id`, `admin_actor_id`, `duration_ms`, `error`); use the existing logging pattern from `audit_service.py` as reference
- [ ] T029 [P] Add wallet link to `apps/admin/src/app/(dashboard)/drivers/[id]/page.tsx` — add a "Wallet" button/tab that navigates to `/drivers/{id}/wallet`; no behaviour changes to existing driver detail page
- [ ] T030 Run `quickstart.md` Scenario 6 (ledger immutability) — confirm UPDATE and DELETE on `driver_ledger_entries` return permission denied with the application database role; document result
- [ ] T031 Run `quickstart.md` Scenario 7 (corrective debit) + SC-006 integrity check SQL queries — verify all three wallet equations hold clean against local database; document any discrepancies

**Checkpoint**: All 7 `quickstart.md` scenarios pass. SC-006 integrity SQL returns 0 rows for discrepancies and 0 orphaned reservations.

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup — Migrations)
  └── Phase 2 (Foundational — wallet_service, Pydantic schemas)
        ├── Phase 3 (US1 — Commission Deduction) ← MVP stop point
        │     └── Phase 6 (US4 — Balance Enforcement) ← depends on commission_service from US1
        ├── Phase 4 (US2 — Admin Top-Up) ← independent of US1/US3
        └── Phase 5 (US3 — Driver Wallet View) ← independent of US1/US2
              
Phase 7 (Polish) ← depends on all 4 user stories complete
```

### User Story Dependencies

- **US1 (P1)**: Depends on Foundation only — no dependency on US2/US3
- **US2 (P2)**: Depends on Foundation only — no dependency on US1/US3
- **US3 (P3)**: Depends on Foundation only — no dependency on US1/US2
- **US4 (P4)**: Depends on Foundation + US1 — needs `commission_service.py` with reservation functions

### Within Each Phase

- Models/schemas before services
- Services before API routers
- API routers before frontend pages
- Frontend components before pages

### Parallel Opportunities

- **Phase 1**: T001/T002/T003/T004 — all in parallel (4 separate SQL files)
- **Phase 4 (US2)**: T014/T015/T016/T017 — all in parallel after T012 is registered (4 separate component files)
- **Phase 5 (US3)**: T019/T020/T022/T023/T024 — all in parallel after T021 registers the router
- **Across stories**: Once Phase 2 is done, US1+US2+US3 can all start in parallel

---

## Parallel Example: Phase 4 (US2 — Admin Top-Up)

```
# After T012 (wallet_router.py) and T013 (registration) are done:
Parallel:
  Task T014: AdminWalletSummary.tsx
  Task T015: TopUpForm.tsx
  Task T016: AdjustForm.tsx
  Task T017: AdminLedgerTable.tsx

Then sequential:
  Task T018: page.tsx (combines all components)
```

---

## Parallel Example: Phase 5 (US3 — Driver Wallet View)

```
# After T021 (router registration) is done:
Parallel:
  Task T019: wallet/__init__.py
  Task T020: wallet/router.py
  Task T022: lib/api/wallet.ts
  Task T023: WalletBalanceCard.tsx
  Task T024: LedgerEntryRow.tsx + LedgerEntryList.tsx

Then sequential:
  Task T025: (driver)/wallet/page.tsx (combines all)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Apply migrations (T001–T005)
2. Complete Phase 2: wallet_service + Pydantic schemas (T006–T007)
3. Complete Phase 3: Commission deduction wired into ride completion (T008–T011)
4. **STOP and VALIDATE**: Run `quickstart.md` Scenario 1 — verify commission deduction fires correctly
5. Deploy Phase 8 backend-only MVP — rides now produce financial ledger entries

### Incremental Delivery

1. Foundation (Phase 1–2) → Database + shared service ready
2. US1 (Phase 3) → Commission deduction works → Backend MVP
3. US2 (Phase 4) → Admin can top up wallets → Admin usable
4. US3 (Phase 5) → Drivers see their balances → Full driver experience
5. US4 (Phase 6) → Balance enforcement prevents over-commitment → Platform safety
6. Polish (Phase 7) → Observability + integrity verified

### Solo Developer Strategy

Sequential priority order:
```
Phase 1 → Phase 2 → Phase 3 (MVP!) → Phase 4 → Phase 5 → Phase 6 → Phase 7
```

Stop after Phase 3 for a working MVP. Everything after that is additive.

---

## Notes

- `[P]` tasks operate on different files with no intra-phase dependencies — safe to implement concurrently
- All `amount_egp` values must use Python `Decimal` — never `float`; this applies to every arithmetic expression in `commission_service.py` and `wallet_service.py`
- The `SELECT ... FOR UPDATE` lock on `driver_wallets` is the single concurrency control point — both US1 (completion) and US4 (creation) acquire it; review `research.md §2` for the rationale
- Commit after each phase or logical group; each phase checkpoint is a safe commit boundary
- Verify `quickstart.md` Scenario 6 (ledger immutability) immediately after Phase 1 migrations — do not wait until Phase 7
- `commission_service.py` is split across two phases intentionally: US1 adds `deduct_commission` + `release_reservation`; US4 adds `check_available_balance` + `create_reservation`. Both phases extend the same file — do not create two separate files.
