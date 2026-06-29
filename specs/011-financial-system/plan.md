# Implementation Plan: Financial System

**Branch**: `011-financial-system` | **Date**: 2026-06-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/011-financial-system/spec.md`

## Summary

Phase 8 adds the financial backbone of Fe El Seka: a driver wallet with an append-only ledger, a commission reservation system that prevents over-commitment at ride creation, automatic commission deduction wired into the Phase 7 ride-completion transaction, and admin endpoints for manual wallet top-up and corrective adjustments. All monetary storage uses PostgreSQL `NUMERIC(12,2)`; all balance-mutating transactions acquire a pessimistic row lock on `driver_wallets`; the ledger table has `UPDATE`/`DELETE` privileges revoked at the database role level. No external payment gateway is involved — this is a pure internal ledger system.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend), TypeScript / Node.js 20 (Next.js 14 frontend)

**Primary Dependencies**: FastAPI + asyncpg (raw SQL, no ORM), Python `decimal.Decimal` for financial arithmetic, `pydantic.Decimal` for schema validation, Next.js 14 App Router, Supabase Auth JWT middleware

**Storage**: Supabase PostgreSQL — three new tables (`driver_wallets`, `commission_reservations`, `driver_ledger_entries`); no new columns on existing tables (reads `rides.fuel_cost_egp`, `rides.total_seat_count`, `bookings.status`)

**Testing**: pytest + httpx (backend unit + integration); Playwright (frontend E2E)

**Target Platform**: Mobile-first web (Next.js 14, Tailwind CSS, shadcn/ui); Linux server (FastAPI via uvicorn)

**Project Type**: Monorepo — `apps/main` (combined passenger + driver role-based routing), `apps/admin` (admin panel), `services/api` (FastAPI backend)

**Performance Goals**: Commission deduction within ride-completion transaction p95 < 500ms; wallet balance read endpoint p95 < 200ms

**Constraints**:
- All EGP amounts stored as `NUMERIC(12, 2)` — never `FLOAT` or `DOUBLE PRECISION`
- `driver_ledger_entries` is INSERT+SELECT only — `UPDATE`/`DELETE` revoked at migration level from the application database role
- Balance check + reservation INSERT must execute in one transaction with `SELECT FOR UPDATE` on `driver_wallets` (same pattern as Phase 7 `notification_events` dispatcher)
- Commission deduction runs inside Phase 7's `complete_ride()` transaction — not as an async listener
- Ride cancellation (Phase 4/6 handlers) must release reservation inside the cancellation transaction
- Platform commission rate (20% of `fuel_cost_egp`) is a hardcoded constant — same as Phase 5; NOT a configurable DB/env value

**Scale/Scope**: ≤1,000 active drivers; up to 50 simultaneous active rides per driver

## Constitution Check

| Gate | Principle | Assessment |
|------|-----------|------------|
| ✅ | I — Driver-First Route Sharing | Financial system is driver-facing (wallet, commission). No changes to ride discovery, matching, or passenger booking flows. |
| ✅ | II — Route Intelligence Over Geographic Proximity | No routing logic in Phase 8. Reads `fuel_cost_egp` already computed by Phase 5 at ride creation. |
| ✅ | III — Trust Before Transportation | Append-only ledger + full audit trail satisfies the Auditability requirement. Driver identity verified via Phase 3 Supabase Auth JWTs before any wallet access. Least-privilege DB permissions enforced. |
| ✅ | IV — AI-Augmented Transportation | No AI logic in Phase 8. Commission calculation is deterministic (fixed formula). |
| ✅ | V — Mobile-First UX | Driver wallet screen and admin wallet management follow mobile-first Tailwind + shadcn/ui patterns established across prior phases. |
| ✅ | VI — Modular Domain-Driven | Phase 8 is scoped entirely to the Financial System domain. No ride matching, tracking, or passenger-facing changes. Cross-domain hooks (into Phase 4/7 handlers) are explicit, minimal, and non-breaking for existing callers. |
| ✅ | VII — Shared Foundations | Monorepo unchanged. Uses existing `apps/main` for driver wallet UI and existing `apps/admin` for admin management. No new apps or packages introduced. |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/011-financial-system/
├── plan.md                  # This file
├── research.md              # Phase 0 output
├── data-model.md            # Phase 1 output
├── quickstart.md            # Phase 1 output
├── contracts/
│   ├── api.md               # Phase 1 output — REST endpoint contracts
│   └── frontend-pages.md    # Phase 1 output — Next.js page contracts
├── checklists/
│   └── requirements.md      # Spec quality checklist
└── tasks.md                 # Phase 2 output (created by /speckit-tasks)
```

### Source Code (repository root)

```text
# ── Backend — New Services ────────────────────────────────────────────────────
services/api/app/services/
├── wallet_service.py        # NEW — wallet CRUD: get_or_create_wallet(),
│                            #       get_wallet_with_lock(), update_balance(),
│                            #       update_reserved(), get_ledger_page()
├── commission_service.py    # NEW — deduct_commission(ride_id, completed_bookings),
│                            #       create_reservation(ride_id, wallet),
│                            #       release_reservation(ride_id),
│                            #       check_available_balance(wallet, max_commission)
├── ride_service.py          # EXTEND — create_ride(): insert balance check + reservation
│                            #           (before ride INSERT, inside same transaction);
│                            #           complete_ride(): call deduct_commission()
│                            #           (after booking cascade, inside same transaction);
│                            #           cancel_ride(): call release_reservation()
│                            #           (inside cancellation transaction)
└── booking_service.py       # EXTEND — booking_expiry_loop(): call release_reservation()
                             #           when a ride is auto-cancelled due to expiry

# ── Backend — New Models ──────────────────────────────────────────────────────
services/api/app/models/
└── wallet.py                # NEW — Pydantic schemas:
                             #       WalletSummaryResponse, LedgerEntryResponse,
                             #       WalletPageResponse, TopUpRequest, TopUpResponse,
                             #       AdjustRequest, AdjustResponse

# ── Backend — New API Routers ─────────────────────────────────────────────────
services/api/app/api/
├── wallet/
│   ├── __init__.py          # NEW
│   └── router.py            # NEW — GET /drivers/me/wallet (driver-facing)
└── admin/
    └── wallet_router.py     # NEW — POST /admin/drivers/{id}/wallet/topup
                             #        POST /admin/drivers/{id}/wallet/adjust

# ── Database Migrations ───────────────────────────────────────────────────────
supabase/migrations/
├── 20260629000005_phase8_driver_wallets.sql          # NEW — driver_wallets table + RLS
├── 20260629000006_phase8_commission_reservations.sql  # NEW — commission_reservations table + RLS
├── 20260629000007_phase8_driver_ledger.sql            # NEW — driver_ledger_entries table,
│                                                      #        ledger_entry_type enum,
│                                                      #        REVOKE UPDATE/DELETE
└── 20260629000008_phase8_indexes.sql                  # NEW — performance indexes

# ── Frontend — Driver Wallet (apps/main) ─────────────────────────────────────
apps/main/src/
├── app/
│   └── (driver)/
│       └── wallet/
│           └── page.tsx               # NEW — driver wallet screen
├── components/
│   └── wallet/
│       ├── WalletBalanceCard.tsx      # NEW — total/reserved/available display
│       ├── LedgerEntryList.tsx        # NEW — paginated transaction list
│       └── LedgerEntryRow.tsx         # NEW — single transaction row (type, amount, ride link)
└── lib/
    └── api/
        └── wallet.ts                  # NEW — getWallet(page), formatEgp()

# ── Frontend — Admin Wallet Management (apps/admin) ──────────────────────────
apps/admin/src/
├── app/
│   └── (dashboard)/
│       └── drivers/
│           └── [id]/
│               └── wallet/
│                   └── page.tsx       # NEW — admin wallet management screen
└── components/
    └── wallet/
        ├── AdminWalletSummary.tsx     # NEW — balance summary for admin view
        ├── TopUpForm.tsx              # NEW — top-up form + submission
        ├── AdjustForm.tsx             # NEW — corrective debit form
        └── AdminLedgerTable.tsx       # NEW — full ledger with admin metadata

# Existing files extended (no new files):
# services/api/app/api/admin/__init__.py  — register wallet_router
# services/api/app/main.py               — register wallet router
# apps/admin/src/app/(dashboard)/drivers/[id]/page.tsx — add link to wallet page
```

**Structure Decision**: Option 4 (Monorepo). No new applications or packages. The `(driver)/wallet/` route follows the existing nested App Router pattern under `(driver)/`. A new `wallet/` API module is added alongside the existing `rides/`, `bookings/`, and `search/` modules. Admin wallet endpoints extend the existing `admin/` API module with a new `wallet_router.py`.
