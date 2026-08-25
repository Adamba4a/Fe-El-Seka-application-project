# Implementation Plan: Driver Fare Override (Capped)

**Branch**: `023-driver-fare-override` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/023-driver-fare-override/spec.md`

## Summary

Drivers may set a final per-seat price anywhere in `[fair_price, fair_price × 1.30]` when creating or
editing a ride, instead of being locked to the system-computed fair price. The pricing engine keeps
computing the fair price exactly as today; a new helper derives the max price from it. Both values are
persisted on the ride row. The platform's 20% commission is extended so it also applies to the driver's
markup (not just the fair-price cost baseline), so platform revenue scales with what the driver actually
charges. Server-side validation is authoritative — the band is enforced in `ride_service`, not only in the
client.

## Technical Context

**Language/Version**: Python 3.11 (backend, `services/api`), TypeScript / Next.js 14 App Router (frontend, `apps/main`)

**Primary Dependencies**: FastAPI, asyncpg (raw SQL over a connection pool — no ORM), Pydantic v2, pytest (backend); Next.js 14, React, Tailwind CSS, shadcn/ui (frontend)

**Storage**: Supabase PostgreSQL — extends the existing `rides` table with one new column; no new tables

**Testing**: pytest for `services/api` (unit tests for `pricing_service`, integration tests for `ride_service` / `rides/router.py`), following existing test layout under `services/api/tests/`

**Target Platform**: Linux containers (Bunny.net in production; `docker-compose.yml` for local dev — `api`, `main`, `nginx` services, joined to the Supabase CLI's `supabase_network_fe-el-seka` network)

**Project Type**: Monorepo web app — FastAPI backend + two Next.js 14 frontends (per Principle VII)

**Performance Goals**: No new performance requirements; band computation is O(1) arithmetic added to an already-synchronous request path (ride create/edit), so no measurable latency impact

**Constraints**:
- NFR-001: price-band validation MUST be enforced server-side, independent of client-side guardrails
- NFR-002: max-price rounding MUST use the same convention as the existing fair-price calculation (bare `round()` to nearest whole EGP)
- NFR-003: no new passenger-facing steps

**Scale/Scope**: Small, backend-heavy — one new persisted column, one new pricing helper, validation added to two existing service functions (`create_ride`, `edit_ride`), one commission-formula change, admin detail view extended, driver-app pricing step extended. No new domains, no new external integrations.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I — Driver-First Route Sharing**: PASS. Drivers still only price rides they are already
  creating for their own travel; the platform still doesn't accept passenger-initiated ride requests.
  Bounded, upward-only pricing flexibility doesn't turn this into an on-demand marketplace.
- **Principle III — Trust Before Transportation**: PASS. Both the fair price and the driver's final price
  are persisted as distinct values and surfaced to passengers and admins, preserving ride transparency and
  accountability rather than hiding the markup.
- **Architecture Standards** ("Critical business rules MUST NOT exist exclusively in frontend applications"):
  Satisfied by NFR-001 — band validation lives in `ride_service`, called from the API layer; the driver UI
  in `apps/main` only mirrors it for UX.
- **Architecture Standards** ("APIs MUST be defined before frontend integrations"): Satisfied by this
  plan's phase ordering — contracts (Phase 1) precede any UI work, which belongs to `/speckit-tasks`.
- **Data Standards** ("Critical operational history MUST be preserved"): Satisfied — `ride_history_logs`
  already records `price_per_seat` changes on edit (`ride_service.py` edit_ride, `changed_fields`); this
  feature extends what's tracked, it doesn't remove any history.
- **Security & Privacy — Auditability** ("financial operations... MUST be traceable and auditable"):
  Satisfied — FR-010 gives admins fair price + final price + markup in one view; the new commission
  formula is deterministic and derived from persisted values, not opaque.
- **Development Workflow — Specification-Driven Development**: Satisfied — spec.md has all mandatory
  sections and passed its quality checklist (16/16) before this plan was started.

No violations identified. Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/023-driver-fare-override/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
services/api/
├── app/
│   ├── services/
│   │   ├── pricing_service.py       # + max-price helper (fair_price * 1.30, same rounding)
│   │   ├── ride_service.py          # create_ride/edit_ride: band validation, FR-008 re-band-on-edit
│   │   └── commission_service.py    # deduct_commission: markup-inclusive commission formula
│   ├── models/
│   │   └── ride.py                  # CreateRideRequest/EditRideRequest/RideResponse: new price fields
│   └── api/
│       ├── rides/router.py          # POST/PATCH rides: pass driver-chosen price through, surface 422s
│       └── admin/rides_router.py    # admin ride detail: fair price, final price, markup %
└── tests/                           # unit tests (pricing_service) + integration tests (ride_service, router)

apps/main/
└── src/                             # driver ride-creation & edit flows: fair/max price display, price input

supabase/migrations/
└── <timestamp>_add_fair_price_per_seat.sql   # new rides.fair_price_per_seat column + backfill
```

**Structure Decision**: This is a backend-driven change within the existing monorepo layout — no new
apps or services. All business-rule changes (band computation, validation, commission) live in
`services/api`, per the Architecture Standard that backend services own business logic. `apps/main`
(the single combined passenger+driver Next.js app) only adds a display/input step to the existing
ride-creation and ride-edit flows; `apps/admin` gets a read-only display addition. No changes to
`services/ai`.

## Complexity Tracking

*No constitution violations — this section intentionally left empty.*
