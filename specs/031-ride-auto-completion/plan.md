# Implementation Plan: Ride Auto-Completion Timeout

**Branch**: `031-ride-auto-completion` | **Date**: 2026-09-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/031-ride-auto-completion/spec.md`

## Summary

Add a 10-minute background sweep (`ride_timeout_sweep_loop`, in `app/services/ride_service.py`, wired into `app/main.py` alongside the ~12 existing background loops) that finds `scheduled` rides more than 2 hours past `departure_datetime` and `in_progress` rides more than `route_duration_minutes × 2` (floor 2h) past `started_at`, and drives each through the existing `start_ride()`/`complete_ride()` consequence pipeline (commission charge, reservation release, booking finalization, notification) rather than a new transition path. Both functions gain small, targeted extensions: `start_ride()` accepts an optional backfilled `started_at`, `complete_ride()` accepts a `completion_source` ('driver'/'system') written to a new `rides.completion_source` column mirroring the existing `cancellation_source` pattern. Both functions' `UPDATE ... WHERE id = $1` statements gain an `AND status = '<expected>'` guard so the sweep can never double-process a ride a driver is concurrently acting on.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend, `services/api`)

**Primary Dependencies**: FastAPI, asyncpg (raw SQL, no ORM) — no new dependency introduced

**Storage**: Supabase PostgreSQL — one additive column migration (`rides.completion_source`), no new tables

**Testing**: Manual quickstart validation against local Supabase dev stack (see quickstart.md) — this codebase has no existing automated test suite for `ride_service.py`'s status-transition functions to extend; consistent with how `recurring_ride_service.py`'s own generation loop was validated (Spec 027)

**Target Platform**: Linux server (Bunny container), local Docker dev stack

**Project Type**: Monorepo backend service (`services/api`) — no frontend/UI changes (Out-of-Scope)

**Performance Goals**: Sweep must complete well within its own 10-minute interval at current ride volume; no new indexes needed at current scale (see research.md §2)

**Constraints**: Must reuse `complete_ride()`'s existing consequence logic verbatim (FR-003) rather than duplicate it; must not modify `recurring_ride_service.py`'s generation loop (Out-of-Scope)

**Scale/Scope**: Two new small query paths + two function signature extensions + one migration + one background loop; no new endpoints, tables, or enum values

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Driver-First Route Sharing** — N/A, no change to how rides are created or discovered.
- **II. Route Intelligence Over Geographic Proximity** — N/A, no matching logic touched. (The in-progress grace period *reads* `route_duration_minutes`, an existing routing-derived field, but doesn't recompute or reinterpret it.)
- **III. Trust Before Transportation** — PASS. This feature directly serves accountability/traceability: a driver who fails to run a ride they committed to is still held to its financial consequences (per the user's explicit accountability decision), and every completion becomes traceable to its source (User Story 3).
- **IV. AI-Augmented Transportation** — N/A, no AI component.
- **V. Mobile-First UX** — N/A, no UI change; the existing "Completed" ride-list state is unchanged.
- **VI. Modular Domain-Driven Architecture** — PASS. Single bounded concern (ride lifecycle finalization), fits entirely inside the existing Ride Management domain, no cross-domain sprawl.
- **VII. Shared Foundations, Independent Applications** — PASS. Backend-only change in the shared `services/api`; no per-app duplication.
- **Architecture Standards** ("Critical business rules MUST NOT exist exclusively in frontend applications") — PASS, this is entirely backend.
- **Data Standards** ("Critical operational history MUST be preserved") — PASS, reuses `ride_history_logs` insert already inside `complete_ride()`; no history is lost or overwritten.
- **Auditability** ("ride operations... MUST be traceable") — PASS, the explicit purpose of `completion_source`.
- **Quality Standards** ("avoid unnecessary complexity", "favor simplicity") — PASS, see research.md §1/§3 alternatives-considered: a new scheduler dependency and a new duplicate transition function were both rejected in favor of reusing existing patterns.

No violations. Complexity Tracking table not needed.

## Project Structure

### Documentation (this feature)

```text
specs/031-ride-auto-completion/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks command — NOT created by this plan)
```

No `contracts/` directory — this feature adds no new API endpoints (Out-of-Scope); the only interface surface is two internal function-signature extensions, documented in data-model.md instead.

### Source Code (repository root)

```text
services/api/
├── app/
│   ├── main.py                              # + 2 lines: create_task/.cancel() for the new loop, alongside the existing ~12
│   └── services/
│       ├── ride_service.py                  # + sweep_stale_rides(), + ride_timeout_sweep_loop()
│       │                                     # extend start_ride() and complete_ride() (see data-model.md)
│       ├── recurring_ride_service.py         # UNCHANGED — reference pattern only (Out-of-Scope: no edits)
│       └── commission_service.py             # UNCHANGED — deduct_commission()/release_reservation() called as-is
└── scripts/                                  # no new script — this is a live background loop, not a one-off

supabase/migrations/
└── <YYYYMMDD>000001_ride_completion_source.sql   # new: ALTER TABLE rides ADD COLUMN completion_source
```

**Structure Decision**: Single-service backend change within `services/api`, following this repo's existing monorepo layout (Principle VII). No `apps/*` (frontend) changes. All new logic lands in the same file (`ride_service.py`) that already owns `start_ride`/`complete_ride`/`cancel_ride`, keeping the ride-lifecycle domain's logic in one place rather than spreading it across a new module.

## Complexity Tracking

*No constitution violations — table not applicable.*
