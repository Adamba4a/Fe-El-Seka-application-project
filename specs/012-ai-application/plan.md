# Implementation Plan: AI Application

**Branch**: `012-ai-application` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/012-ai-application/spec.md`

## Summary

Phase 9 integrates the trained AI models (built in Phase 2, `services/ai`) into two live platform flows: (1) the passenger ride search pipeline, where candidates are AI-scored and ranked before being returned, and (2) the driver ride creation flow, where the system-assigned fare replaces manual driver pricing. No new database tables or columns are required — match scores are ephemeral and the existing `rides.price_per_seat NUMERIC(10, 2)` column is the system fare column. Changes are concentrated in `services/api` (new AI client service + search and ride service extensions) and `apps/main` (match score badge, confirmation screen, driver form changes).

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend), TypeScript / Node.js 20 (Next.js 14 frontend)

**Primary Dependencies**: FastAPI + httpx (async AI service HTTP client with 1s timeout), asyncpg (raw SQL, no ORM), `decimal.Decimal` for fare arithmetic, Next.js 14 App Router, Supabase Auth JWT middleware, shadcn/ui, Tailwind CSS

**Storage**: Supabase PostgreSQL — no new tables, no new columns. Existing `rides.price_per_seat NUMERIC(10, 2) NOT NULL` is the system fare column (present since Phase 4 migration `20260617000001_ride_management.sql`). AI match scores are ephemeral — not stored in any table.

**Testing**: pytest + httpx (backend unit + integration with mock AI service); Playwright (frontend E2E)

**Target Platform**: Mobile-first web (Next.js 14, Tailwind CSS, shadcn/ui); Linux server (FastAPI via uvicorn)

**Project Type**: Monorepo — `apps/main` (combined passenger + driver role-based routing), `services/api` (FastAPI backend), `services/ai` (AI service — consumed over HTTP, not modified in this phase)

**Performance Goals**: AI scoring step p95 < 500ms for a batch of up to 20 candidates; AI pricing call p95 < 200ms; fallback activation within 1 second of AI service failure

**Constraints**:
- All httpx calls to `services/ai` must have a hard 1-second timeout
- `price_per_seat` is `NUMERIC(10, 2)` — all fare arithmetic must use `decimal.Decimal`; never `float`
- AI match scores are ephemeral — no INSERT to any table for scores
- Single ride creation call — no separate fare preview endpoint (FR-009)
- `price_per_seat` removed from the ride creation request body; computed by the system only (FR-011)
- Feature vector mapping from Phase 5 compatibility response: `overlap_pct / 100` → `estimated_overlap_ratio`; `pickup_walk_m / 1000` → `estimated_pickup_detour_km`; `dropoff_walk_m / 1000` → `estimated_dropoff_distance_km`
- Cairo zone centroid lookup uses a hardcoded 13-district table (see `research.md` §Zone Centroid Lookup)
- System fare derivation from AI range: `Decimal(str(round((min_egp + max_egp) / 2, 2)))` — never raw float
- Fallback fare uses Phase 5 deterministic formula: reads `pricing_config` table (single row, `fuel_price_per_litre`, `safety_margin`)

**Scale/Scope**: ≤1,000 active users; up to 20 candidate rides per search batch; 1 AI pricing call per ride creation; no new migrations; ~5 new/extended backend files, ~4 new/extended frontend files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Principle | Assessment |
|------|-----------|------------|
| ✅ | I — Driver-First Route Sharing | Phase 9 does not alter the driver-creates/passenger-joins model. Fare assignment enhances ride creation; AI ranking enhances search results. Neither introduces on-demand dispatch. |
| ✅ | II — Route Intelligence Over Geographic Proximity | AI scoring consumes Phase 5 route overlap, detour, and proximity features as primary inputs. Deterministic feasibility gating (Phase 5) is unchanged and executes before AI scoring. |
| ✅ | III — Trust Before Transportation | System-assigned fare prevents price manipulation. Match percentage gives passengers transparent, quantified confidence. No changes to verification flows. |
| ✅ | IV — AI-Augmented Transportation | Core domain of Phase 9. `services/ai` remains independently deployable; `services/api` communicates via HTTP prediction API only — no direct imports across service boundaries. |
| ✅ | V — Mobile-First UX | `MatchScoreBadge` follows established mobile-first component pattern. Driver confirmation screen follows existing `(driver)/rides/` App Router conventions. |
| ✅ | VI — Modular Domain-Driven Architecture | Scoped entirely to the AI Integration domain. Two targeted integration points in `services/api`. No cross-domain changes to auth, booking, financial, or real-time domains. |
| ✅ | VII — Shared Foundations, Independent Applications | Monorepo unchanged. Changes in `services/api` (shared backend) and `apps/main` (passenger + driver). No new apps, packages, or services introduced. |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/012-ai-application/
├── plan.md                  # This file
├── research.md              # Phase 0 output
├── data-model.md            # Phase 1 output
├── quickstart.md            # Phase 1 output
├── contracts/
│   ├── api.md               # Phase 1 output — updated REST endpoint contracts
│   └── frontend-pages.md    # Phase 1 output — Next.js page contracts
├── checklists/
│   └── requirements.md      # Spec quality checklist
└── tasks.md                 # Phase 2 output (created by /speckit-tasks)
```

### Source Code (repository root)

```text
# ── Backend — New Services ────────────────────────────────────────────────────
services/api/app/services/
└── ai_client.py             # NEW — async httpx client for services/ai HTTP API:
                             #       score_candidates(passenger_req, candidates) → list[ScoredCandidate]
                             #       rank_candidates(scored_candidates) → list[str]  (ride_id order)
                             #       get_fare(origin_zone, dest_zone, origin_centroid,
                             #               dest_centroid, distance_km, departure_at) → Decimal
                             #       is_available() → bool  (health check, 1s timeout)
                             #       All calls: timeout=1.0s; raises AIServiceUnavailableError
                             #       on connection error, timeout, or HTTP 503.

# ── Backend — Extended Services ───────────────────────────────────────────────
services/api/app/services/
├── search_service.py        # EXTEND — after Phase 5 candidate generation:
                             #   1. Build feature vectors from Phase 5 compatibility data
                             #      (convert units: pct→ratio, m→km; map coords to zone centroids)
                             #   2. Call ai_client.score_candidates() → raw scores (0.0–1.0)
                             #   3. Clamp scores to [0.0, 1.0]; log any out-of-range values
                             #   4. Call ai_client.rank_candidates() → ordered ride_id list
                             #   5. Apply 20% threshold filter + minimum-3 guarantee
                             #   6. Attach match_score_pct (int) to each candidate
                             #   On AIServiceUnavailableError or all-scores-identical:
                             #     → fallback: sort by overlap_pct descending, no threshold filter
└── ride_service.py          # EXTEND — create_ride():
                             #   1. price_per_seat removed from CreateRideRequest
                             #   2. After OSRM route computation, call
                             #      pricing_service.calculate_fare(distance_km, seat_count)
                             #   3. Set price_per_seat = fare in ride INSERT
                             #   (Superseded 2026-07-04 — steps 2-4 of the original AI-pricing
                             #   design, ai_client.get_fare() + fallback, were removed; fare is
                             #   always the deterministic formula, no AI call, no fallback branch)

# ── Backend — New Models ──────────────────────────────────────────────────────
services/api/app/models/
└── ai.py                    # NEW — Pydantic schemas for AI service communication:
                             #       ZoneCentroid, PassengerRequestFeatures,
                             #       CandidateFeatures, ScoredCandidate
                             #       (AIPriceRequest/AIPriceResponse removed 2026-07-04 —
                             #       pricing is deterministic-only, no AI call)

# ── Backend — Zone Utility ────────────────────────────────────────────────────
services/api/app/utils/
└── zone_lookup.py           # NEW — hardcoded Cairo zone centroid table (13 districts);
                             #       nearest_zone(lat, lng) → (zone_name: str, centroid: dict)
                             #       Uses Euclidean distance to nearest zone centroid.
                             #       No external calls; deterministic; importable by ai_client.py.

# ── Frontend — New Components (apps/main) ─────────────────────────────────────
apps/main/src/components/search/
└── MatchScoreBadge.tsx      # NEW — displays "85% match" with colour coding:
                             #       ≥70% → green; 40–69% → amber; <40% → grey
                             #       Props: score_pct: number | null

# ── Frontend — Extended Pages (apps/main) ─────────────────────────────────────
apps/main/src/app/
├── (passenger)/
│   ├── search/results/
│   │   └── page.tsx         # EXTEND — import MatchScoreBadge; render on each ride card
│   └── rides/[id]/
│       └── page.tsx         # EXTEND — receive match_score_pct from API response;
│                            #          display MatchScoreBadge alongside ride detail
└── (driver)/
    └── rides/create/
        └── page.tsx         # EXTEND — remove price_per_seat input field;
                             #          show system-assigned fare on success/confirmation screen

# ── Frontend — Extended API Clients (apps/main) ───────────────────────────────
apps/main/src/lib/api/
├── search.ts                # EXTEND — add match_score_pct?: number to RideCandidate type
└── rides.ts                 # EXTEND — remove price_per_seat from CreateRideRequest type;
                             #          add price_per_seat to CreateRideResponse type

# ── Database Migrations ───────────────────────────────────────────────────────
# NONE — rides.price_per_seat NUMERIC(10,2) NOT NULL already exists
#         (20260617000001_ride_management.sql, Phase 4).
#
# Existing files extended (no new files in these directories):
# services/api/app/api/rides/router.py  — remove price_per_seat from CreateRideRequest schema
# services/api/app/api/search/router.py — add match_score_pct to RideCandidateResponse schema;
#                                         add match_score_pct to passenger-detail response
```

**Structure Decision**: Option 4 (Monorepo). No new applications or packages. The AI client (`ai_client.py`) follows the existing services pattern alongside `wallet_service.py` and `search_service.py`. A new `models/ai.py` module holds Pydantic schemas for AI service I/O. A new `utils/zone_lookup.py` provides the Cairo zone centroid lookup, keeping it importable without coupling to any service. Frontend changes follow the established App Router pattern under `(passenger)/` and `(driver)/`.
