# Implementation Plan: Featured Rides

**Branch**: `022-add-featured-rides` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/022-add-featured-rides/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Admins can mark an eligible ride (scheduled, in the future, seats available) as "Featured" from the existing admin Rides views. The passenger `find-a-ride` entry point — currently a map-only screen — becomes a landing page that lists currently bookable Featured rides (computed fresh on each page load, no polling/realtime) plus a "Find a Ride" button that opens the existing pin-drop map search flow unchanged. Backend: extend the read-only Admin Rides API with feature/unfeature mutation endpoints, extend the Ride data model with a Featured designation + audit metadata, and add a passenger-facing Featured Rides read endpoint that live-filters on status/seats/departure. Frontend: extend the admin rides list/detail UI with a toggle, and restructure `apps/main`'s passenger search page into a landing page + reused map-search flow (mirroring the driver's post-a-ride page pattern).

## Technical Context

**Language/Version**: TypeScript 5 (Next.js 14 App Router, both `apps/main` and `apps/admin`); Python 3.11 (`services/api`, FastAPI)

**Primary Dependencies**: Next.js 14, React 18, Tailwind CSS, shadcn/ui (`packages/ui`), `@supabase/ssr` for auth/session — frontend. FastAPI, asyncpg, GeoAlchemy2/PostGIS, pydantic-settings — backend. Shared types live in `packages/shared`.

**Storage**: Supabase PostgreSQL (existing `rides` table, `supabase/migrations/`), extended with a Featured designation and audit columns via a new migration.

**Testing**: pytest (`services/api/tests/unit`, `services/api/tests/integration`) for the API; `tsc --noEmit` + `eslint` for both Next.js apps (no frontend unit-test runner is currently configured in this repo — verification for UI changes is manual/browser-driven, consistent with existing feature work in this codebase).

**Target Platform**: Web (mobile-first responsive), deployed as Docker containers on Bunny (per existing deployment: `apps/main`/`services/api` live on triplyy.net/api.triplyy.net; `apps/admin` is local-only, not deployed).

**Project Type**: Monorepo web application — Option 4 (multiple Next.js apps + shared FastAPI backend), per Constitution Principle VII.

**Performance Goals**: Featured Rides listing endpoint responds within 500ms at p95 (NFR-001); landing page's Featured section (or its empty state) visible within 2s on a typical mobile connection (SC-005).

**Constraints**: No new realtime/polling infrastructure — the Featured list is fetched fresh per page load only (per Clarifications, 2026-08-25). Featuring must not alter AI ranking/matching output (FR-013, Constitution Principle II). No new admin roles/permissions in this iteration (any authenticated admin may toggle Featured).

**Scale/Scope**: Small, admin-curated set of Featured rides (no enforced cap); two UI surfaces (admin toggle, passenger landing page) plus one new/extended API surface (admin mutation, passenger read).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Driver-First Route Sharing | Featured only curates/surfaces rides drivers already created; it introduces no passenger-initiated ride requests. | PASS |
| II. Route Intelligence Over Geographic Proximity | FR-013 explicitly forbids Featured status from influencing route-matching/AI ranking; Featured eligibility filtering (status/seats/departure) is deterministic backend logic, not part of the matching/ranking service. | PASS |
| III. Trust Before Transportation | No change to identity verification; FR-014 reuses existing auth/verification gating for the landing page unchanged. | PASS |
| IV. AI-Augmented Transportation | No AI component added; Featured curation is explicitly kept separate from the AI ranking service (see II). | PASS (N/A) |
| V. Mobile-First User Experience | Landing page redesign reuses the existing mobile-first map/bottom-sheet/pin-drop pattern already proven on the driver post-a-ride page; adds a lighter-weight list view before it. | PASS |
| VI. Modular Domain-Driven Architecture | Feature is scoped to Ride Discovery (passenger) + Administration (admin curation) domains; it extends two existing domains rather than introducing an unrelated one. | PASS |
| VII. Shared Foundations, Independent Applications | Reuses the existing `RideMap`/`BottomSheet`/pin-drop components and `packages/ui`/`packages/shared` types instead of duplicating UI; extends the existing Admin Rides API rather than building a parallel one. | PASS |

No violations requiring justification — Complexity Tracking section is not needed.

**Post-Phase 1 re-check**: Design artifacts (research.md, data-model.md, contracts/) confirm the above holds — Featured filtering stayed in `ride_service.py`/the admin rides router, structurally separate from `search/router.py`'s AI ranking (II, IV); the migration only adds columns to existing tables, no new services or apps (VI, VII). No new violations introduced.

## Project Structure

### Documentation (this feature)

```text
specs/022-add-featured-rides/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
apps/
├── main/                           # Next.js 14 — passenger + driver experience (route-group split)
│   ├── src/
│   │   ├── app/
│   │   │   ├── (passenger)/
│   │   │   │   └── search/
│   │   │   │       └── page.tsx        # becomes the landing page (Featured list + "Find a Ride" entry)
│   │   │   └── (driver)/
│   │   │       └── rides/new/page.tsx  # reference pattern only — not modified
│   │   ├── components/
│   │   │   ├── bookings/
│   │   │   │   ├── RideSearchForm.tsx      # existing map/pin-drop search — reused unchanged, relocated behind "Find a Ride"
│   │   │   │   └── FeaturedRidesSection.tsx   # NEW — landing page's featured list
│   │   │   └── rides/
│   │   │       └── RideCard.tsx            # existing card component — reused for featured cards
│   │   └── lib/api/
│   │       └── search.ts               # add fetchFeaturedRides()
│   └── tests/ (none configured; manual/browser verification per repo convention)
│
└── admin/                          # Next.js 14 — admin panel (local-only)
    └── src/
        ├── app/(dashboard)/rides/
        │   ├── page.tsx                 # add Featured column/filter to list
        │   └── [ride_id]/page.tsx       # add Featured toggle control
        └── lib/api/
            └── rides.ts                 # add featureRide()/unfeatureRide() calls

services/api/
├── app/
│   ├── api/
│   │   ├── admin/
│   │   │   └── rides_router.py      # add POST {ride_id}/feature and {ride_id}/unfeature (raw-SQL pattern, matches existing handlers)
│   │   ├── rides/
│   │   │   └── router.py            # add GET /featured (passenger-facing, public rides domain — not the AI search router)
│   │   └── search/
│   │       └── router.py            # reference only; NOT modified — Featured stays structurally separate from AI ranking (FR-013)
│   ├── models/
│   │   └── ride.py                  # extend RideResponse/RideDetailResponse with is_featured/featured_at
│   └── services/
│       ├── ride_service.py          # add list_featured_rides() alongside existing list_rides()/get_ride()
│       └── audit_service.py         # reuse append_log(); extend admin_audit_logs with a nullable ride_id column
└── tests/
    ├── unit/          # featured eligibility/filtering logic
    └── integration/   # admin feature/unfeature endpoints, passenger featured-listing endpoint

supabase/migrations/
└── <timestamp>_add_featured_rides.sql   # NEW — is_featured, featured_at, featured_by columns + index
```

**Structure Decision**: Monorepo Option 4 (existing structure, unchanged). This feature adds no new apps or packages — it extends `apps/main` (passenger landing page), `apps/admin` (curation toggle), and `services/api` (new mutation + read endpoints, one new service module, one new migration). `apps/main` already houses both passenger and driver experiences via Next.js route groups, and `apps/admin` is presently local-only (no deployed container), matching prior features in this repo.

## Complexity Tracking

*No Constitution Check violations — this section is not applicable.*
