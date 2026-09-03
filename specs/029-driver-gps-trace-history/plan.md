# Implementation Plan: Driver GPS Trace History

**Branch**: `029-driver-gps-trace-history` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/029-driver-gps-trace-history/spec.md`

## Summary

Add an append-only `driver_location_history` table that records every GPS ping received during an
active ride, alongside the existing overwrite-per-ride `driver_locations` table (unchanged). The
history write is fire-and-forget from `update_driver_location` (`services/api/app/api/rides/router.py`),
mirroring the non-blocking pattern `match_logging_service.persist_match_events` already established
(013-match-learning-foundation). A new recurring in-process loop (same pattern as
`retraining_scheduler_loop`) purges rows older than a rolling 30-day window. One new Supabase Postgres
table and one new service module (`location_history_service.py`); `services/ai` and all frontend apps
are unchanged.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend) — no frontend changes.

**Primary Dependencies**: FastAPI, `asyncpg` (raw SQL, no ORM). No new third-party dependencies.

**Storage**: Supabase PostgreSQL — 1 new table: `driver_location_history`. No changes to
`driver_locations`, `driver_locations_view`, or any other existing table.

**Testing**: pytest + `asyncpg` test-DB fixtures (existing `services/api` convention); no new test
tooling.

**Target Platform**: Linux server (FastAPI via uvicorn) — `services/api` only.

**Project Type**: Monorepo — backend-only change within `services/api` (shared backend, Principle
VII). `services/ai` and all three Next.js apps are unmodified.

**Performance Goals**: Zero added synchronous latency to the location-ping request path (history
write is fire-and-forget via `asyncio.create_task`, per FR-003/NFR-001 — same mechanism as
`match_logging_service.persist_match_events`). The retention DELETE runs once per loop tick against an
indexed column, off any request path.

**Constraints**:
- History logging MUST NOT block, delay, or fail the existing `driver_locations` upsert (FR-003) —
  implemented via `asyncio.create_task`, not awaited by the request handler, and wrapped in its own
  try/except inside the service function so it can never raise into the caller.
- `recorded_at` reuses the already-validated `client_timestamp` from the same location-update request
  (no new client contract, no new validation) — see `research.md` R1.
- The retention job MUST be idempotent and window-relative, not tied to a fixed calendar schedule
  (FR-004, FR-005, NFR-003) — a plain `DELETE ... WHERE recorded_at < now() - interval '30 days'` run
  on a recurring in-process loop, mirroring `retraining_scheduler_loop`'s existing pattern.
- `asyncpg` raw SQL only, no ORM, per existing `services/api` convention.
- No new passenger- or driver-facing UI or API surface (spec Out-of-Scope) — this feature has no
  request/response schema of its own.

**Scale/Scope**: One new migration file; one new service module; two existing files extended
(`api/rides/router.py`, `main.py`, both minimally — a background-task call and a lifespan loop
registration).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Principle | Assessment |
|------|-----------|------------|
| ✅ | I — Driver-First Route Sharing | No change to the driver-creates/passenger-joins model. Purely additive instrumentation on the existing live-location ping path. |
| ✅ | II — Route Intelligence Over Geographic Proximity | No matching/ranking logic touched. This feature only preserves raw GPS data for a *future* route-overlap-pooling-optimization model (roadmap TBD item) — it does not itself change any route-intelligence decision. |
| ✅ | III — Trust Before Transportation | No change to verification, safety, or trust mechanics. |
| ✅ | IV — AI-Augmented Transportation | Core domain. Directly closes data-collection gap #1 from the 2026-09-03 roadmap audit, a named blocker for the future route-overlap-pooling-optimization model — "training data cannot be reconstructed retroactively," the same rationale that made 013-match-learning-foundation mandatory before launch. `services/ai` remains unmodified and independently deployable. |
| ✅ | V — Mobile-First UX | No UI changes (Out-of-Scope). N/A. |
| ✅ | VI — Modular Domain-Driven Architecture | Scoped entirely to the Route Intelligence / AI Integration domain, touching only the existing live-location ping path it instruments. |
| ✅ | VII — Shared Foundations, Independent Applications | Entirely within the shared `services/api` backend. No new apps, packages, or services. |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/029-driver-gps-trace-history/
├── plan.md                  # This file
├── research.md              # Phase 0 output
├── data-model.md            # Phase 1 output
├── quickstart.md            # Phase 1 output
├── contracts/
│   └── data-schema.md       # Phase 1 output — DB schema as the future ETL/model consumer contract
└── tasks.md                 # Phase 2 output (created by /speckit-tasks)
```

### Source Code (repository root)

```text
# ── Database Migration ────────────────────────────────────────────────────────
supabase/migrations/
└── 20260903000001_driver_gps_trace_history.sql
                             # NEW — driver_location_history table, indexes on
                             #       (ride_id, recorded_at) and (recorded_at) for
                             #       the retention DELETE. RLS enabled with no
                             #       public policies (service-role only, same
                             #       pattern as match_events/search_sessions).

# ── Backend — New Service ─────────────────────────────────────────────────────
services/api/app/services/
└── location_history_service.py
                             # NEW — record_ping(ride_id, driver_id, lat, lng,
                             #       recorded_at) -> fire-and-forget entry point
                             #       called via asyncio.create_task from
                             #       rides/router.py (mirrors
                             #       match_logging_service.persist_match_events);
                             #       purge_expired() -> int, a single DELETE
                             #       against the 30-day cutoff; and
                             #       location_history_retention_loop() -> the
                             #       recurring in-process loop registered in
                             #       main.py (mirrors retraining_scheduler_loop).

# ── Backend — Extended ────────────────────────────────────────────────────────
services/api/app/api/rides/router.py
                             # EXTEND — update_driver_location(): after the
                             #   existing location_service.upsert_location(...)
                             #   call succeeds, add
                             #   asyncio.create_task(location_history_service
                             #   .record_ping(...)) using the same validated
                             #   payload fields already on hand.

services/api/app/main.py    # EXTEND — lifespan: asyncio.create_task(
                             #   location_history_service
                             #   .location_history_retention_loop()) alongside
                             #   the existing 12 background-loop registrations;
                             #   cancel on shutdown.

# ── No changes ─────────────────────────────────────────────────────────────────
services/api/app/services/location_service.py
                             # UNCHANGED — driver_locations upsert path this
                             # feature instruments, not modifies.
services/ai/                # UNCHANGED — no model or endpoint changes needed
                             # to support capture; this feature is instrumentation
                             # only (see spec Out-of-Scope).
apps/                        # UNCHANGED — backend-only feature, no UI.
```

**Structure Decision**: Option 4 (Monorepo), backend-only. The new service module follows the
existing `services/api/app/services/` pattern (alongside `match_logging_service.py`,
`retraining_scheduler_service.py`). No new Pydantic request/response models are needed — the new
table is written via raw SQL from within the service layer and is never exposed through any API
response.

## Complexity Tracking

*No Constitution Check violations — this section is not required.*
