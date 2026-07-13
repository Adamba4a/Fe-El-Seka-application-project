# Implementation Plan: Match Learning Foundation

**Branch**: `013-match-learning-foundation` | **Date**: 2026-07-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/013-match-learning-foundation/spec.md`

## Summary

Instrument the existing passenger search and booking-lifecycle flows so every AI-ranked (or
fallback-ranked) candidate shown to a passenger is durably recorded — feature vector, rank position,
predicted score — and every downstream state change for a previously-shown candidate (requested,
accepted, rejected, completed, cancelled, and later rated) is linked back to it. Also inject a small,
configurable amount of ranking randomization (~10-15% of searches) so outcome data is not entirely
confirmation of the launch model's own beliefs. Four new Supabase Postgres tables
(`search_sessions`, `match_events`, `match_outcomes`, `ranking_config`); changes concentrated in
`services/api/app/api/search/router.py` and `services/api/app/services/booking_service.py`, plus two
new service modules. `services/ai` is unchanged — this is purely a `services/api` concern.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend) — no frontend changes.

**Primary Dependencies**: FastAPI, `asyncpg` (raw SQL, no ORM), existing `ai_client.py` httpx client
(unchanged). No new third-party dependencies.

**Storage**: Supabase PostgreSQL — 4 new tables: `search_sessions`, `match_events`,
`match_outcomes`, `ranking_config`. No changes to `rides`, `requests`, `bookings`, or
`booking_audit_log`.

**Testing**: pytest + `asyncpg` test-DB fixtures (existing `services/api` convention); no new test
tooling.

**Target Platform**: Linux server (FastAPI via uvicorn) — `services/api` only.

**Project Type**: Monorepo — backend-only change within `services/api` (shared backend, Principle
VII). `services/ai` and both Next.js apps are unmodified.

**Performance Goals**: Zero added synchronous latency to the search response (match-event
persistence is fire-and-forget, per Clarifications); exploration reorder is an in-memory list
operation (<1ms) on an already-computed ranked list; outcome-linking insert adds one indexed lookup +
one insert to existing booking-transaction latency (negligible, same class of cost as the existing
`booking_audit_log` insert in the same transaction).

**Constraints**:
- Match-event persistence MUST NOT block or delay the search response (FR-005, NFR-001) — implemented via `asyncio.create_task`, not awaited by the request handler.
- The existing AI service 1-second call timeout (012-ai-application) is unchanged.
- Exploration MUST only reorder candidates that already passed deterministic feasibility gating (FR-009) — operates strictly on the post-threshold-filter `final_scored` list already produced by `_ai_rank`.
- Exploration rate MUST be adjustable without a code deployment (FR-010, NFR-004) — singleton config table + cached refresh loop, mirroring `pricing_config`.
- `asyncpg` raw SQL only, no ORM, per existing `services/api` convention.
- Match Outcome inserts (FR-003) ARE durable, synchronous, and transactional with the booking/ride status change they represent — not fire-and-forget (see `research.md` R5; only match-event logging on the search path carries the best-effort guarantee).

**Scale/Scope**: ~100 rides/day at launch (per spec Assumptions), scaling over time; up to 20
candidates per search batch (existing `_AI_CANDIDATE_CAP`); one new migration file; 2 new service
modules; 3 existing files extended (`search/router.py`, `booking_service.py`, `main.py` for the new
config refresh loop).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Principle | Assessment |
|------|-----------|------------|
| ✅ | I — Driver-First Route Sharing | No change to the driver-creates/passenger-joins model. Logging and exploration are additive instrumentation on the existing search/booking flows. |
| ✅ | II — Route Intelligence Over Geographic Proximity | Exploration reorders only candidates that already passed deterministic feasibility gating (008-route-intelligence, FR-009) — that gate remains the sole arbiter of eligibility, unchanged. |
| ✅ | III — Trust Before Transportation | No change to verification, safety, or trust mechanics. Exploration is bounded (~10-15%) and never surfaces an infeasible or unsafe candidate. |
| ✅ | IV — AI-Augmented Transportation | Core domain. Directly implements the constitution's mandate that "the platform architecture MUST support continuous model improvement without requiring major architectural redesign" and improves AI auditability (every prediction's feature vector and model version is now recorded). `services/ai` remains unmodified and independently deployable. |
| ✅ | V — Mobile-First UX | No UI changes (Out-of-Scope). N/A. |
| ✅ | VI — Modular Domain-Driven Architecture | Primarily scoped to AI Integration domain; touches the Booking domain (`booking_service.py`) only to append outcome records to an existing transaction — an explicit, documented cross-domain dependency (spec Dependencies section), not a redesign of booking logic. |
| ✅ | VII — Shared Foundations, Independent Applications | Entirely within the shared `services/api` backend. No new apps, packages, or services. |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/013-match-learning-foundation/
├── plan.md                  # This file
├── research.md              # Phase 0 output
├── data-model.md            # Phase 1 output
├── quickstart.md            # Phase 1 output
├── contracts/
│   └── data-schema.md       # Phase 1 output — DB schema as the ETL/monitoring consumer contract
├── checklists/
│   └── requirements.md      # Spec quality checklist
└── tasks.md                 # Phase 2 output (created by /speckit-tasks)
```

### Source Code (repository root)

```text
# ── Database Migration ────────────────────────────────────────────────────────
supabase/migrations/
└── 20260714000001_phase13_match_learning.sql
                             # NEW — search_sessions, match_events, match_outcomes,
                             #       ranking_config (+ seed row), match_outcome_transition enum,
                             #       RLS enabled with no public policies (service-role only),
                             #       updated_at trigger on ranking_config (mirrors pricing_config)

# ── Backend — New Services ────────────────────────────────────────────────────
services/api/app/services/
├── match_logging_service.py # NEW — persist_match_events(search_ctx, ranked_candidates, score_map,
                             #       ai_scored, model_version) -> fire-and-forget entry point called
                             #       via asyncio.create_task from search/router.py;
                             #       record_outcome(conn, ride_id, passenger_id, transition_type,
                             #       metadata) -> synchronous, called inside existing booking
                             #       transactions (see research.md R1 for the correlation lookup)
└── ranking_config_service.py# NEW — mirrors pricing_service.py's config pattern:
                             #       init_ranking_config(), ranking_config_refresh_loop(),
                             #       get_exploration_rate() -> float
                             #       apply_exploration(ranked_candidates) -> (reordered, promoted_id | None)

# ── Backend — Extended Services ───────────────────────────────────────────────
services/api/app/services/
└── booking_service.py       # EXTEND — create_booking() records 'requested' outcome;
                             #   confirm_booking() records 'accepted'; reject_booking() records
                             #   'rejected' (both branches: fallback-confirmed and cancelled);
                             #   cancel_booking() records 'cancelled'; complete_ride_bookings()
                             #   records 'completed' per booking. Each call is
                             #   match_logging_service.record_outcome(conn, ...) inside the existing
                             #   conn.transaction() block, alongside the existing
                             #   _insert_audit_log() call.

services/api/app/api/search/router.py
                             # EXTEND — search_rides(): after building candidates_out and score_map,
                             #   call ranking_config_service.apply_exploration() on the final ranked
                             #   list (both AI and fallback paths, so fallback searches remain
                             #   eligible for exploration/logging per FR-006), then
                             #   asyncio.create_task(match_logging_service.persist_match_events(...))
                             #   immediately before returning the JSONResponse. Task is fire-and-forget:
                             #   never awaited, never allowed to raise into the request path.

services/api/app/main.py     # EXTEND — lifespan: await ranking_config_service.init_ranking_config();
                             #   asyncio.create_task(ranking_config_service.ranking_config_refresh_loop())
                             #   alongside the existing pricing_config startup calls; cancel on shutdown.

# ── No changes ─────────────────────────────────────────────────────────────────
services/ai/                # UNCHANGED — this feature instruments what already happens in
                             # services/api; no new endpoints or model changes needed here.
apps/main/                  # UNCHANGED — backend-only feature, no UI (spec Out-of-Scope).
```

**Structure Decision**: Option 4 (Monorepo), backend-only. Two new service modules follow the
existing `services/api/app/services/` pattern (alongside `pricing_service.py`, `booking_service.py`).
`ranking_config_service.py` deliberately mirrors `pricing_service.py`'s singleton-config-table +
cached-refresh-loop shape rather than introducing a new configuration mechanism. No new Pydantic
models are needed in `app/models/` — the new tables are written via raw SQL from within the service
layer and are not exposed through any request/response schema.

## Complexity Tracking

*No Constitution Check violations — this section is not required.*
