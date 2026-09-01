# Implementation Plan: Loyalty Points

**Branch**: `028-loyalty-points` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/028-loyalty-points/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

A single role-agnostic points ledger generalizes the existing driver car-maintenance savings mechanism (0.3 EGP/km distance fee → EGP counter → threshold reward) into a points system usable by both passengers and drivers. Passengers earn points on completed bookings proportional to fare; drivers earn points from the same distance-fee share that used to fund `car_maintenance_savings_egp`, now credited 1:1 as points. Both roles redeem points from a shared reward catalog (free ride, fare discount, car-maintenance credit, admin-managed vouchers) against per-role balances (FR-003). Free-ride and discount redemptions resolve inline at booking creation; car-maintenance and manually-flagged vouchers go through the existing admin PENDING/FULFILLED/REJECTED queue pattern (generalized from `car_maintenance_rewards`); standard vouchers fulfill instantly. All admin-tunable thresholds (point costs, free-ride fare cap, discount percentage) are `platform_settings` rows, edited without a redeploy, following the existing headless-settings pattern used everywhere else in this codebase.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend, `services/api`), TypeScript 5 / Next.js 14 (frontend, `apps/main` for passenger/driver, `apps/admin` for the admin queue+catalog)

**Primary Dependencies**: FastAPI, asyncpg (raw SQL over a connection pool — no ORM; existing pattern in `wallet_service.py`/`car_maintenance_service.py`), Pydantic v2 for request/response models; Next.js App Router, Tailwind CSS, shadcn/ui on the frontend

**Storage**: Supabase PostgreSQL (new tables `loyalty_points_accounts`, `loyalty_points_transactions`, `loyalty_reward_catalog`, `loyalty_redemption_requests`; extends `admin_audit_logs` and `notification_event_type`; `driver_wallets.car_maintenance_savings_egp` and `car_maintenance_rewards` deprecated in place, not dropped — see data-model.md)

**Testing**: pytest (backend service/integration tests, existing pattern e.g. `test_groups_flow.py`); `pnpm turbo typecheck`/`lint`/`build` for `apps/main` and `apps/admin`; no OSRM dependency for this feature, so end-to-end scenarios are validated via direct-service-layer scripts against the real local Supabase DB, consistent with Specs 026/027

**Target Platform**: Existing deployed stack — Bunny-hosted FastAPI container (`api.triplyy.net`) and Next.js app (`triplyy.net`); Admin Panel (`apps/admin`) is local-only, gains the generalized loyalty queue+catalog UI but is not itself redeployed

**Project Type**: Monorepo web application (Next.js frontend + FastAPI backend + Supabase), per Constitution Principle VII

**Performance Goals**: NFR-001 — balance/transaction-history reads respond within 500ms p95, matching existing wallet-read endpoints

**Constraints**: NFR-002 — all balance mutations (earn, redeem, refund, clawback) MUST be atomic under `SELECT ... FOR UPDATE` row locking (mirroring `wallet_service.get_wallet_with_lock`), no double-spend under concurrent redemption; NFR-003 — 50 concurrent voucher redemptions; NFR-004 — ledger entries retained indefinitely (immutable, append-only)

**Scale/Scope**: One new backend service module (`loyalty_service.py`) + 4 new tables + ~10 new/extended endpoints + refactor of `commission_service.py`'s single call site; frontend gains passenger loyalty balance/redeem UI, driver loyalty balance/redeem UI (replacing the implicit car-maintenance widget in the wallet page), and an admin loyalty tab (generalizing the existing car-maintenance tab) with a catalog-management sub-view

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Driver-First Route Sharing | No change to ride creation/discovery/matching; points are earned/redeemed around existing ride and booking lifecycle events only | PASS |
| II. Route Intelligence Over Geographic Proximity | Not applicable — feature has no routing/matching component | PASS (N/A) |
| III. Trust Before Transportation | No change to identity/verification gates; redemption requires an authenticated role-scoped account, admin fulfillment reuses existing `get_current_admin` authorization | PASS |
| IV. AI-Augmented Transportation | Not applicable — no AI component in this feature | PASS (N/A) |
| V. Mobile-First UX | Balance/history/redeem UI reuses existing mobile-first wallet/booking screens' patterns in `apps/main`; admin queue reuses existing admin dashboard table patterns | PASS |
| VI. Modular Domain-Driven Architecture | New `loyalty_service.py` module is additive within the existing Financial System domain (research.md Decision 1); no new domain created | PASS |
| VII. Shared Foundations, Independent Applications | Points logic lives once in `services/api`, consumed by both `apps/main` (passenger+driver) and `apps/admin`; generalizing car-maintenance into loyalty points directly satisfies "duplication of shared functionality is prohibited" | PASS |

No violations — Complexity Tracking table is empty.

**Post-Design Re-check** (after Phase 1 data-model.md/contracts/quickstart.md): No new violations introduced. The refactor of `car_maintenance_service.py` into `loyalty_service.py` (research.md Decision 1) and deprecation-in-place of `car_maintenance_savings_egp`/`car_maintenance_rewards` (Decision 2) is the generalization Principle VII requires, not a second parallel system. All new tables are additive; the one extended existing flow (`commission_service.deduct_commission()`) has a single, already-locked call-site change (contracts/loyalty-points-api.md, Internal section). All 7 principles remain PASS.

## Project Structure

### Documentation (this feature)

```text
specs/028-loyalty-points/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── loyalty-points-api.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
apps/
├── main/                                          # Next.js 14 — passenger + driver experience (single app)
│   └── src/app/
│       ├── (passenger)/loyalty/                   # new: balance, transaction history, catalog browse+redeem
│       └── (driver)/wallet/loyalty/                # new: balance, transaction history, car-maintenance redeem
│                                                    # (driver wallet page's car-maintenance widget updated to link here)
└── admin/                                          # Next.js 14 — admin panel
    └── src/app/(dashboard)/
        └── loyalty/                                # new: generalizes car-maintenance/page.tsx
            ├── queue/                              # pending manual-fulfillment requests (fulfill/reject)
            └── catalog/                             # voucher CRUD + system-entry editing (point cost,
                                                        #   free-ride max fare, discount percentage)

services/api/app/
├── api/
│   ├── loyalty/
│   │   └── loyalty_router.py                       # new: passenger/driver balance, transactions, catalog, redeem
│   ├── admin/
│   │   ├── loyalty_router.py                        # new: queue fulfill/reject, catalog CRUD
│   │   └── car_maintenance_router.py                 # removed — superseded by admin/loyalty_router.py
│   └── rides/
│       └── booking_router.py                        # extended: loyalty_redemption_catalog_entry_id field
├── models/
│   └── loyalty.py                                    # new: Pydantic request/response schemas
└── services/
    ├── loyalty_service.py                            # new: account/ledger/catalog/redemption logic
    ├── car_maintenance_service.py                     # removed — logic merged into loyalty_service.py
    ├── commission_service.py                          # changed: calls loyalty_service.award_driver_points()
    ├── booking_service.py                              # changed: complete_ride_bookings() calls
    │                                                    #   loyalty_service.award_passenger_points() per booking;
    │                                                    #   booking creation handles inline free_ride/discount redemption
    └── wallet_service.py                                # unchanged — driver_wallets EGP mutations untouched

services/api/tests/
├── unit/test_loyalty_service.py                      # new
└── integration/test_loyalty_flow.py                   # new (direct-service-layer, no OSRM required locally)

supabase/migrations/
└── 20260901000002_loyalty_points.sql                  # new: 4 tables, enum extensions, admin_audit_logs column,
                                                         #   platform_settings seeds, car_maintenance_rewards→
                                                         #   loyalty_redemption_requests data migration for PENDING rows
```

**Structure Decision**: Extends the existing `services/api` FastAPI backend (Constitution Principle VI: additive module in the Financial System domain, replacing rather than duplicating `car_maintenance_service.py`) and the existing `apps/main` Next.js app (Principle VII: one app already serves both driver and passenger roles). `apps/admin` gains a `loyalty` tab that replaces `car-maintenance`, consistent with how every prior admin queue (top-up, withdrawal, sponsored-groups) lives in this same local-only Admin Panel. No new package, no new deployable unit.

## Complexity Tracking

*No violations — table intentionally empty.*
