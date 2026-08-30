# Implementation Plan: Sponsored Groups

**Branch**: `026-sponsored-groups` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/026-sponsored-groups/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Admins can designate a domain-verified `company`/`university` Group as **sponsored**, funding it with an EGP balance. Every booking on a sponsored group's rides is automatically settled from that balance at booking-creation time (no cash option) — the company's funded balance is debited the full seat price, and the driver's wallet is immediately credited the net-of-commission amount via a new `SPONSORED_RIDE_CREDIT` ledger entry, since no cash changes hands for a sponsored seat. This bypasses the existing cash-ride commission-reservation pipeline (`check_available_balance`/`create_reservation` at ride-creation, `deduct_commission` at ride-completion) entirely for sponsored bookings, which settle independently and immediately instead. A new driver withdrawal-request flow (mirroring wallet top-up in reverse) lets drivers cash out their wallet balance, admin-reviewed. A read-only company dashboard in `apps/main` lets a designated, already-verified group member view the funded balance and sponsorship activity.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend, `services/api`), TypeScript 5 / Next.js 14 (frontend, `apps/main`)

**Primary Dependencies**: FastAPI, asyncpg (no ORM — raw SQL against `supabase/migrations/*.sql`), Pydantic v2; Next.js 14, Tailwind CSS, shadcn/ui

**Storage**: Supabase PostgreSQL — extends the existing `groups`, `bookings`, `driver_ledger_entries` tables and adds one new table, `withdrawal_requests`

**Testing**: No dedicated automated API test suite exists in this repo today (consistent with Specs 018/023/024's delivery pattern); validated via the manual `quickstart.md` scenarios below plus existing CI checks (typecheck/build/lint)

**Target Platform**: Linux container (Bunny.net) for `services/api`; Bunny-hosted Next.js deployment for `apps/main`

**Project Type**: Web application — monorepo (`apps/main` passenger frontend + `services/api` FastAPI backend), per Principle VII

**Performance Goals**: No new performance targets beyond existing platform NFRs — sponsored-booking settlement adds one extra row lock (`groups` FOR UPDATE) to the existing booking transaction, which already locks `rides` FOR UPDATE, so no material latency change is expected on the booking hot path

**Constraints**: All monetary fields use `NUMERIC(12,2)` + `Decimal` arithmetic, never floats (matches `driver_wallets`/`wallet_topup_requests` convention); every balance mutation MUST happen under a `SELECT ... FOR UPDATE` lock held for the duration of the transaction (matches `wallet_service`/`commission_service` convention); RLS required on the new `withdrawal_requests` table

**Scale/Scope**: MVP scale per the Students/Employees pivot — a small number of sponsoring organizations initially, each with a small number of domain-verified members; no new infrastructure required

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. Driver-First Route Sharing | PASS — sponsored rides are still driver-posted rides a driver was already going to make; sponsorship only changes how a seat is paid for, not the on-demand-vs-route-sharing model. |
| II. Route Intelligence Over Geographic Proximity | N/A — no matching/routing logic changes; sponsored rides use the existing group-scoped ride listing (Spec 024) unchanged. |
| III. Trust Before Transportation | PASS — sponsorship is gated on the existing domain-verification trust tier (Spec 024); no new identity mechanism introduced. |
| IV. AI-Augmented Transportation | N/A — no AI component in this feature. |
| V. Mobile-First User Experience | PASS — the company dashboard and withdrawal flow follow the same Next.js 14 mobile-first patterns as every other `apps/main` screen. |
| VI. Modular Domain-Driven Architecture | PASS — sponsorship logic is added to the existing Groups/Wallet/Booking domains rather than a new cross-cutting module; the withdrawal flow is its own small, decomposed addition mirroring the top-up domain. |
| VII. Shared Foundations, Independent Applications | PASS — extends existing shared tables/services (`groups`, `driver_wallets`, `driver_ledger_entries`) rather than duplicating them; company dashboard lives in `apps/main` (Passenger App), not a new application. |

No violations — Complexity Tracking is empty (see below).

**Post-Phase-1 re-check**: All decisions in `research.md` extend existing tables/services rather than introducing new architectural elements (no new services, no new apps, no new infra). Constitution Check still PASSES with no changes to the table above.

## Project Structure

### Documentation (this feature)

```text
specs/026-sponsored-groups/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── api.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
supabase/migrations/
└── <timestamp>_sponsored_groups.sql
    # ALTER TABLE groups ADD is_sponsored, funded_balance_egp, dashboard_contact_user_id
    # ALTER TABLE bookings ADD payment_source
    # ALTER TYPE ledger_entry_type ADD VALUE 'SPONSORED_RIDE_CREDIT' | 'SPONSORED_RIDE_REVERSAL' | 'WITHDRAWAL_DEBIT'
    # CREATE TABLE withdrawal_requests (+ indexes, RLS policies)

services/api/app/
├── models/
│   ├── group.py                    # extended: is_sponsored, funded_balance_egp, dashboard_contact_user_id on GroupSummary/GroupDetailResponse
│   ├── wallet.py                   # extended: LedgerEntryType enum += 3 values
│   └── withdrawal.py                # new: WithdrawalSubmitRequest/Response, AdminWithdrawal* schemas (mirrors wallet_topup.py)
├── services/
│   ├── group_service.py            # extended: set_dashboard_contact, sponsorship-dashboard query
│   ├── sponsored_group_service.py   # new: create-or-upgrade, add-funds (admin-facing)
│   ├── booking_service.py          # extended: create_booking sponsored-settlement branch (research.md §4)
│   ├── ride_service.py             # extended: create_ride reservation exemption (§6), complete_ride commission-query filter (§5)
│   ├── commission_service.py       # unchanged — no new branching needed (§5 rationale)
│   └── withdrawal_service.py        # new: submit_request, list_driver_history, list_pending_queue, approve_request, reject_request (mirrors wallet_topup_service.py)
├── api/
│   ├── admin/
│   │   ├── sponsored_groups_router.py  # new: /api/admin/sponsored-groups
│   │   └── withdrawal_router.py        # new: /api/admin/withdrawal-requests
│   ├── groups/router.py            # extended: GET /{group_id}/sponsorship-dashboard
│   └── wallet_withdrawals/router.py    # new: /api/wallet/withdrawals
└── main.py                         # extended: mount the 3 new routers

apps/main/src/app/
└── (passenger)/
    └── sponsorship-dashboard/[groupId]/page.tsx   # new: read-only company dashboard, gated to dashboard_contact_user_id

apps/admin/src/
├── app/sponsored-groups/page.tsx   # new: admin create/upgrade/add-funds/dashboard-contact UI
└── app/withdrawal-requests/page.tsx # new: admin withdrawal queue/history/approve/reject UI (mirrors existing wallet-topup-requests page)
```

**Structure Decision**: This feature extends four existing domains (Groups, Wallet, Booking, Ride) in place rather than introducing a new top-level domain — new files are added only where a genuinely new capability has no existing home (`withdrawal_service.py`/`withdrawal_router.py` mirroring `wallet_topup_service.py`/`wallet_topup_router.py`; `sponsored_group_service.py`/`sponsored_groups_router.py` for the admin-only sponsorship-management surface that doesn't fit the member-facing `group_service.py`). All money movement continues to flow exclusively through `wallet_service.py`'s existing lock-then-mutate primitives (`get_wallet_with_lock`, `increment_balance`, `decrement_balance`, `insert_ledger_entry`) — no parallel wallet-mutation path is introduced.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No entries — no constitutional violations.
