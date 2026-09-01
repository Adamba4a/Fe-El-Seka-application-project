# Implementation Plan: Recurring Rides

**Branch**: `027-recurring-rides` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/027-recurring-rides/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

A driver defines one recurring ride (route + selected weekdays + departure time + seat count); the backend generates individual `rides` rows ("day instances") for a rolling 2-week window, linked back to the definition. Passengers search/book a day instance through the existing ride search and booking flow unchanged. A driver cancels a single day instance via the existing `cancel_ride` mechanism without ending the series; ending the series only stops future generation. Editing the definition propagates to not-yet-generated and already-generated-but-unbooked instances; confirmed bookings keep their locked details. A background refresh loop (same pattern as `driver_reminder_loop`/`booking_expiry_loop` in `main.py`) generates upcoming instances and hides/reveals unbooked instances as driver eligibility changes.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend, `services/api`), TypeScript 5 / Next.js 14 (frontend, `apps/main`)

**Primary Dependencies**: FastAPI, asyncpg (raw SQL over a connection pool — no ORM; existing pattern in `ride_service.py`/`booking_service.py`), Pydantic v2 for request/response models; Next.js App Router, Tailwind CSS, shadcn/ui on the frontend

**Storage**: Supabase PostgreSQL with PostGIS (existing `public.rides`/`public.bookings` tables extended, new `public.recurring_ride_definitions` table)

**Testing**: pytest (backend service/integration tests, existing pattern e.g. `test_groups_flow.py`); `pnpm turbo typecheck`/`lint`/`build` for frontend; no OSRM available in local dev (see project history), so end-to-end scenarios are validated via direct-service-layer scripts against the real local Supabase DB, consistent with how Spec 026 was verified

**Target Platform**: Existing deployed stack — Bunny-hosted FastAPI container (`api.triplyy.net`) and Next.js app (`triplyy.net`); Admin Panel (`apps/admin`) is local-only and not affected by this feature

**Project Type**: Monorepo web application (Next.js frontend + FastAPI backend + Supabase), per Constitution Principle VII

**Performance Goals**: No new performance target beyond NFR-002 (recurring search/booking matches existing one-off ride response envelope); background generation loop runs on a fixed interval, not request-path-critical

**Constraints**: Route feasibility for every generated instance MUST still be computed via OSRM (Principle II) — generation cannot skip routing just because the route was already validated once at definition-creation time, since OSRM route geometry/distance is stored per-instance (`rides.route_geometry`/`route_distance_km`) exactly as for one-off rides

**Scale/Scope**: Single new backend service module + table + ~6 new/reused endpoints + background loop; no new frontend app, extends existing ride-creation/ride-list/ride-detail UI in `apps/main`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Driver-First Route Sharing | Drivers still define rides ahead of travel; recurring is a batch convenience for the driver, not a passenger on-demand request mechanism | PASS |
| II. Route Intelligence Over Geographic Proximity | Each generated day instance computes its route via OSRM exactly like a one-off ride (Technical Considerations, spec.md) — no shortcut to straight-line distance | PASS |
| III. Trust Before Transportation | No change to identity/verification gates; FR-010/FR-012 explicitly re-apply existing driver-eligibility checks to every generated instance, including hiding unbooked instances immediately on ineligibility | PASS |
| IV. AI-Augmented Transportation | Not applicable — this feature does not touch ranking/pricing/matching AI; existing AI match-score behavior on ride detail pages is unaffected | PASS (N/A) |
| V. Mobile-First UX | Reuses existing mobile-first ride search/booking/detail flows; only the driver-side creation flow gains a "recurring" mode | PASS |
| VI. Modular Domain-Driven Architecture | New `recurring_ride_service.py` module, new table, additive endpoints under the existing `rides` domain — no new domain, no duplication of booking/cancellation logic (Technical Considerations) | PASS |
| VII. Shared Foundations, Independent Applications | Backend logic lives once in `services/api`; only `apps/main` gains UI, `apps/admin` untouched, consistent with sponsored-groups precedent | PASS |

No violations — Complexity Tracking table is empty.

**Post-Design Re-check** (after Phase 1 data-model.md/contracts/quickstart.md): No new violations introduced. The `recurring_ride_definitions` table and `rides.recurring_ride_definition_id` FK (data-model.md) are additive; every generated instance still routes through OSRM (contracts/recurring-rides-api.md, generation loop step 3) and existing cancellation/booking code paths untouched (contracts note on `POST /rides/{ride_id}/cancel` reuse). All 7 principles remain PASS.

## Project Structure

### Documentation (this feature)

```text
specs/027-recurring-rides/
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
└── main/                                    # Next.js 14 — passenger + driver experience (single app)
    └── src/app/(driver)/rides/
        ├── new/                             # existing one-off creation flow gains a "Recurring" mode toggle
        └── recurring/                       # new: driver's recurring-definition list, detail, edit, end

services/api/app/
├── api/rides/
│   └── recurring_router.py                  # new: recurring-definition CRUD endpoints
├── models/
│   └── recurring_ride.py                    # new: Pydantic request/response schemas
└── services/
    ├── recurring_ride_service.py            # new: definition CRUD + generation/eligibility logic
    ├── ride_service.py                       # unchanged — cancel_ride/edit_ride reused as-is
    └── main.py                                # gains recurring_ride_generation_loop() background task,
                                                # started the same way as driver_reminder_loop (existing pattern)

services/api/tests/
├── unit/test_recurring_ride_service.py       # new
└── integration/test_recurring_rides_flow.py  # new (direct-service-layer, no OSRM required locally)

supabase/migrations/
└── 20260901000001_recurring_ride_definitions.sql   # new table + rides.recurring_ride_definition_id FK
```

**Structure Decision**: Extends the existing `services/api` FastAPI backend (Constitution Principle VI: additive module in the Ride domain, not a new domain) and the existing `apps/main` Next.js app (Principle VII: one app serves both driver and passenger roles already; `apps/admin` is untouched, matching the sponsored-groups precedent where admin-only features stayed out of the local-only Admin Panel unless explicitly needed). No new package, no new deployable unit — the recurring generation loop runs inside the existing FastAPI process alongside its sibling background loops (`driver_reminder_loop`, `booking_expiry_loop`, etc. in `main.py`).

## Complexity Tracking

*No violations — table intentionally empty.*
