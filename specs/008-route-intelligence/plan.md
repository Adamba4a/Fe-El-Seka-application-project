# Implementation Plan: Route Intelligence

**Branch**: `008-route-intelligence` | **Date**: 2026-06-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-route-intelligence/spec.md`

## Summary

Extend the existing FastAPI service (`services/api`) with a deterministic route intelligence layer built on OSRM and PostGIS. The implementation adds three new service modules — `route_service` (OSRM HTTP client + PostGIS spatial queries), `candidate_service` (two-stage pool filtering + compatibility pipeline), and `pricing_service` (fuel-cost formula + in-memory config cache) — plus two new API surfaces: user-facing endpoints (JWT-authenticated) for passenger candidate search and driver fare estimation, and an internal endpoint (shared-secret-authenticated) that packages compatibility features for the Phase 9 AI service. A new `pricing_config` singleton table holds all admin-tunable thresholds. The `rides` table gains a `route_geometry` column (PostGIS LineString) and four fare-breakdown columns. OSRM is added as a new Docker service, seeded with an Egypt OSM extract.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: FastAPI ≥ 0.111, asyncpg ≥ 0.29 (raw SQL, no ORM), GeoAlchemy2 ≥ 0.15 (PostGIS type helpers — already in pyproject.toml), httpx ≥ 0.27 (async OSRM HTTP client — new dependency), python-jose (JWT verification — existing)

**Storage**: Supabase PostgreSQL + PostGIS. New: `pricing_config` singleton table. Modified: `rides` table — `route_geometry GEOMETRY(LINESTRING, 4326)`, `route_distance_km`, `route_duration_minutes`, `fuel_cost_egp`, `platform_commission_egp`, `safety_margin_egp`, `price_source`.

**Testing**: pytest + pytest-asyncio (existing). OSRM calls mocked with `respx` for unit tests. PostGIS queries tested against a local Supabase instance.

**Target Platform**: Linux container (Docker), same compose stack as existing `api`, `ai`, `main` services. New: `osrm` service.

**Project Type**: Web service — new domain modules inside the existing FastAPI monolith (`services/api`)

**Performance Goals**: Route path calculation ≤ 500ms p95 (NFR-001); candidate generation for ≤ 500 rides ≤ 3s p95 (NFR-002)

**Constraints**: CompatibilityResult is transient — computed fresh per request, never persisted. Pricing parameters in DB (not code). All spatial distance via PostGIS geography type. JWT required for public endpoints. Shared secret required for internal Phase 9 endpoint. Candidate pool capped at 500 rides per search.

**Scale/Scope**: ~1,000 active users; 500-ride candidate pool cap per search

## Constitution Check

*GATE: Must pass before Phase 0. Re-checked after Phase 1 design — all pass.*

| Principle | Status | Notes |
|---|---|---|
| I. Driver-First Route Sharing | ✅ Pass | Candidate generation filters existing driver rides; passengers search against supply — no on-demand dispatch |
| II. Route Intelligence Over Geographic Proximity | ✅ Pass | All match decisions use OSRM road-network distance + PostGIS corridor overlap; Euclidean distance is prohibited in code |
| III. Trust Before Transportation | ✅ Pass | Route intelligence endpoints enforce JWT; unauthenticated access rejected HTTP 401 |
| IV. AI-Augmented Transportation | ✅ Pass | Phase 5 is deterministic only; Phase 9 AI scores candidates generated here — boundary clean, internal contract defined |
| V. Mobile-First UX | ✅ Pass | Backend-only phase; no UX scope |
| VI. Modular Domain-Driven Architecture | ✅ Pass | Route intelligence is a new isolated domain (`api/routes/`, `services/route_service.py`, `services/pricing_service.py`) |
| VII. Shared Foundations | ✅ Pass | Lives in `services/api` (shared backend); Main App and AI service consume via HTTP — no duplication |
| §Data Standards | ✅ Pass | Geospatial columns use `GEOMETRY(LINESTRING, 4326)` and `geography` cast for distance; UUID PKs |
| §Architecture Standards | ✅ Pass | Business logic in services; routers are thin; pricing config in DB not code |
| §Security | ✅ Pass | JWT for public endpoints; shared secret for internal; no sensitive data in logs |
| §Auditability | ✅ Pass | FareEstimate breakdown persisted on `rides` row for audit trail |

## Project Structure

### Documentation (this feature)

```text
specs/008-route-intelligence/
├── plan.md                          ← this file
├── research.md                      ← Phase 0: OSRM, PostGIS overlap, pricing, Phase 9 contract
├── data-model.md                    ← Phase 1: DB schema + Pydantic models
├── quickstart.md                    ← Phase 1: end-to-end validation guide
├── contracts/
│   ├── route-intelligence-api.md    ← user-facing endpoints (JWT)
│   └── internal-ai-features-api.md ← Phase 9 internal endpoint (shared secret)
└── tasks.md                         ← Phase 2 output (created by /speckit-tasks)
```

### Source Code

```text
services/api/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   └── router.py                      ← candidate search + fare calc (new)
│   │   └── internal/
│   │       └── route_intelligence_router.py   ← Phase 9 features endpoint (new)
│   ├── services/
│   │   ├── route_service.py                   ← OSRM client + PostGIS overlap/proximity/detour (new)
│   │   ├── candidate_service.py               ← two-stage candidate pipeline (new)
│   │   └── pricing_service.py                 ← fare formula + config cache (new)
│   ├── models/
│   │   └── route.py                           ← Pydantic request/response models (new)
│   └── main.py                                ← register new routers (modified)
├── migrations/
│   ├── 005_add_pricing_config.sql             ← new table (new)
│   └── 006_add_ride_geometry.sql              ← rides additions (new)
└── tests/
    ├── unit/
    │   ├── test_route_service.py
    │   ├── test_candidate_service.py
    │   └── test_pricing_service.py
    └── integration/
        └── test_route_intelligence_api.py

osrm-data/                 ← mounted into OSRM container (new top-level directory)
│                             (egypt-latest.osm.pbf + processed .osrm files)
scripts/
└── osrm-setup.sh          ← one-time OSRM graph build script (new)

docker-compose.yml         ← add osrm service (modified)
```
