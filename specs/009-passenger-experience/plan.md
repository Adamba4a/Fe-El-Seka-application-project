# Implementation Plan: Passenger Experience

**Branch**: `009-passenger-experience` | **Date**: 2026-06-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/009-passenger-experience/spec.md`

## Summary

Phase 6 builds the demand side of the Fe El Seka platform: a passenger ride-search surface (thin proxy to the Phase 5 `candidate_service`), a ride-detail screen with interactive premium option selection, a booking creation flow with atomic seat reservation via the existing `booked_seats` counter, a driver confirmation / rejection workflow, cancellation by either party, booking completion cascade triggered by ride completion, and a "My Bookings" list. Four new backend components are added — a `search` router, a `bookings` router, `booking_service.py`, and a `booking_expiry_loop` background task — alongside a new `(passenger)` Next.js route group with five screens and a driver booking queue screen under the existing `(driver)` group.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend), TypeScript / Node.js 20 (Next.js 14 frontend)

**Primary Dependencies**: FastAPI + asyncpg (raw SQL, no ORM), Next.js 14 App Router, Supabase Auth (JWT), PostGIS (booking geometry), Phase 5 `candidate_service` and `route_service` (OSRM)

**Storage**: Supabase PostgreSQL + PostGIS — new tables: `bookings`, `booking_audit_log`; `email_notifications` extended with booking event types

**Testing**: pytest + httpx (backend unit + integration); Playwright (frontend E2E)

**Target Platform**: Mobile-first web (Next.js 14, Tailwind CSS, shadcn/ui); Linux server (FastAPI via uvicorn)

**Project Type**: Monorepo — `apps/main` (combined passenger + driver role-based routing), `services/api` (FastAPI backend)

**Performance Goals**: Ride search p95 < 4 s (inclusive of Phase 5 candidate generation call); booking creation p95 < 1 s; end-to-end search → book journey < 90 s

**Constraints**:
- `available_seats` is a **generated column** (`total_seats − booked_seats`) — seat reservation must increment `booked_seats`, never write `available_seats` directly
- Atomic seat claim uses a conditional `UPDATE rides SET booked_seats = booked_seats + 1 WHERE id = $1 AND booked_seats < total_seats RETURNING id`; zero rows returned = seat taken, return HTTP 409
- All passenger booking endpoints require `verification_status = 'approved'`

**Scale/Scope**: ~1,000 active users; up to 500 rides per candidate pool; expiry sweep handles up to 500 expired bookings per run

## Constitution Check

| Gate | Principle | Assessment |
|------|-----------|------------|
| ✅ | I — Driver-First Route Sharing | Passengers discover existing rides only; no demand-request / ride-hailing mechanism exists |
| ✅ | II — Route Intelligence Over Geographic Proximity | Search delegates entirely to Phase 5 candidate engine (OSRM + PostGIS); no straight-line fallback |
| ✅ | III — Trust Before Transportation | `get_current_verified_passenger` dependency enforces `verification_status = approved` at search and booking creation |
| ✅ | IV — AI-Augmented Transportation | Phase 9 AI re-ranking is an accepted result override; Phase 6 implements no AI logic |
| ✅ | V — Mobile-First UX | All new screens are mobile-first within the existing Tailwind / shadcn/ui system |
| ✅ | VI — Modular Domain-Driven | Spec and plan are scoped to Ride Discovery + Booking only; no cross-domain logic |
| ✅ | VII — Shared Foundations | Monorepo; passenger and driver screens share `apps/main`; shared types in `packages/shared` |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/009-passenger-experience/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── api.md           # Phase 1 output — REST endpoint contracts
│   └── frontend-pages.md  # Phase 1 output — Next.js page contracts
└── tasks.md             # Phase 2 output (created by /speckit-tasks)
```

### Source Code (repository root)

```text
# ── Backend ─────────────────────────────────────────────────────────────────
services/api/app/
├── api/
│   ├── bookings/              # NEW
│   │   ├── __init__.py
│   │   └── router.py          # Booking lifecycle: create, confirm, reject, cancel, list
│   ├── search/                # NEW
│   │   ├── __init__.py
│   │   └── router.py          # POST /search/rides — thin proxy to candidate_service
│   └── rides/
│       └── router.py          # EXTEND — add passenger-facing GET /rides/{id}/detail
├── dependencies/
│   └── verification.py        # EXTEND — add get_current_verified_passenger
├── models/
│   └── booking.py             # NEW — Pydantic schemas for booking request/response
├── services/
│   ├── booking_service.py     # NEW — booking lifecycle, completion cascade, expiry loop
│   └── notification_service.py  # EXTEND — add booking notification enqueue helpers
└── main.py                    # EXTEND — register booking_expiry_loop at startup

# ── Database ─────────────────────────────────────────────────────────────────
supabase/migrations/
└── 20260624000001_phase6_bookings.sql   # NEW — bookings, booking_audit_log, RLS, indexes

# ── Frontend ─────────────────────────────────────────────────────────────────
apps/main/src/
├── app/
│   ├── (passenger)/           # NEW route group (mirrors existing (driver)/)
│   │   ├── layout.tsx         # Passenger layout with bottom nav
│   │   ├── search/
│   │   │   └── page.tsx       # Ride search form + results list
│   │   ├── rides/
│   │   │   └── [id]/
│   │   │       └── page.tsx   # Ride detail + premium option selector + Book button
│   │   └── bookings/
│   │       ├── page.tsx       # My Bookings list
│   │       └── [id]/
│   │           └── page.tsx   # Booking detail + cancel action
│   └── (driver)/
│       └── rides/
│           └── [id]/
│               └── bookings/  # NEW — driver booking queue for a ride
│                   └── page.tsx
└── components/
    └── bookings/              # NEW
        ├── BookingCard.tsx
        ├── BookingStatusBadge.tsx
        ├── RideSearchForm.tsx
        ├── RideCard.tsx
        └── RideDetailMap.tsx
```

**Structure Decision**: Option 4 (Monorepo). The passenger route group `(passenger)/` is introduced following the identical pattern as the existing `(driver)/` group — same `apps/main` app, same layout wrapper, same role-based protection via `middleware.ts`. No new applications or packages are required.
