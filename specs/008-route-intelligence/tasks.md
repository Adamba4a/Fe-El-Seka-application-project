# Tasks: Route Intelligence

**Input**: Design documents from `specs/008-route-intelligence/`

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Data Model**: [data-model.md](data-model.md) | **Contracts**: [contracts/](contracts/)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. No test tasks are included (not requested in spec).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no blocking dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup

**Purpose**: New dependencies, Docker, settings, Pydantic models, and code scaffolding required before any user story can begin.

- [x] T001 Add `httpx>=0.27.0` to `services/api/pyproject.toml` dependencies
- [x] T002 [P] Add `OSRM_URL` (default `http://osrm:5000`) and `INTERNAL_SECRET` fields to `services/api/app/core/config.py` Settings class
- [x] T003 [P] Add `osrm` service to `docker-compose.yml` — image `osrm/osrm-backend:v5.27.1`, command `osrm-routed --algorithm ch /data/egypt-latest.osrm`, volume `./osrm-data:/data:ro`, port `5000:5000`, network `fe-el-seka-dev`
- [x] T004 [P] Create `scripts/osrm-setup.sh` — downloads `egypt-latest.osm.pbf` from Geofabrik, runs `osrm-extract` with `car.lua` profile, then `osrm-contract`, outputs processed graph into `osrm-data/`
- [x] T005 [P] Create `osrm-data/.gitkeep`; add `osrm-data/*.osm.pbf` and `osrm-data/*.osrm*` to `.gitignore` (keep directory, ignore data files)
- [x] T006 [P] Create `services/api/app/models/route.py` with all Pydantic models from data-model.md: `GeoPoint`, `RouteGeometry`, `CompatibilityResult`, `RideCandidate`, `CandidateSearchRequest`, `CandidateListResponse`, `FareEstimateRequest`, `FareEstimateResponse`, `CompatibilityFeaturesRequest`, `CompatibilityFeatures`

**Checkpoint**: Dependencies installed, OSRM containerised, all Pydantic models defined. Stack can be brought up with `docker compose up` (OSRM starts but returns errors until osrm-data is built — that's expected at this stage).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: DB schema additions and pricing config service MUST be complete before any user story can run. No user story work begins until this phase is done.

**⚠️ CRITICAL**: All Phase 3–6 work is blocked until Phase 2 is complete.

- [x] T007 Write `supabase/migrations/20260622000001_add_pricing_config.sql` — `CREATE TABLE pricing_config` with all columns from data-model.md (`fuel_price_per_litre`, `safety_margin`, `corridor_buffer_radius_m`, `min_overlap_pct`, `max_pickup_walk_m`, `max_dropoff_walk_m`, `max_detour_km`, `max_detour_minutes`, `max_premium_detour_km`, `time_window_minutes`, `updated_at`); seed one default row; add `updated_at` trigger
- [x] T008 [P] Write `supabase/migrations/20260622000002_add_ride_geometry.sql` — `ALTER TABLE rides ADD COLUMN route_geometry GEOMETRY(LINESTRING, 4326)`, `route_distance_km NUMERIC(10,2)`, `route_duration_minutes INTEGER`, `fuel_cost_egp NUMERIC(10,2)`, `platform_commission_egp NUMERIC(10,2)`, `safety_margin_egp NUMERIC(10,2)`, `price_source VARCHAR(20) NOT NULL DEFAULT 'legacy'`; `CREATE INDEX idx_rides_route_geometry ON rides USING GIST(route_geometry)`; `CREATE INDEX idx_rides_departure_status ON rides(departure_datetime, status) WHERE status = 'scheduled'`
- [ ] T009 ⚠️ MANUAL STEP — Apply both migrations to local Supabase: run `supabase db push` from the repo root; verify `pricing_config` has one row and `rides` has new columns
- [x] T010 Create `services/api/app/services/pricing_service.py` — module-level `_config_cache: dict`, `_config_lock: asyncio.Lock`; `init_pricing_config()` for blocking initial load; `pricing_config_refresh_loop()` (refreshes every 30s); `get_pricing_config() -> dict`; constants `FUEL_EFFICIENCY_KM_PER_L = 13.0` and `PLATFORM_COMMISSION_RATE = 0.20`; `_calc_fee_from_distance()`; `calculate_fare()`; `calculate_premium_detour_fee()`
- [x] T011 Register `pricing_config_refresh_loop` and `init_pricing_config` in `services/api/app/main.py` lifespan — initial blocking load before yield, background loop alongside `email_retry_loop`
- [x] T012 Create `services/api/app/api/routes/__init__.py` and `services/api/app/api/routes/router.py` (empty `APIRouter`); registered in `main.py` with prefix `/api/routes` and tag `routes`
- [x] T013 [P] Create `services/api/app/api/internal/route_intelligence_router.py` — `APIRouter` with `_require_internal_secret()` helper checking `X-Internal-Secret` header against `settings.internal_secret`, HTTP 403 on mismatch; stub `POST /compatibility` returns HTTP 501; registered in `main.py` with prefix `/internal/route-intelligence`

**Checkpoint**: Migrations applied, pricing config cached and refreshing, both routers registered and responding (candidates → 422 stub, fare → 422 stub, compatibility → 501). `GET /health` still green.

---

## Phase 3: User Story 1 — Route Path Calculation (Priority: P1) 🎯

**Goal**: The platform can calculate road-network distance, travel time, and route geometry between any two geographic points using OSRM.

**Independent Test**: Call `POST /api/routes/fare` with Maadi→Dokki coordinates; verify `distance_km > 0`, `fuel_cost_egp > 0`, geometry is returned. Call with ocean coordinates (0,0)→(1,1); verify HTTP 422 with `error: "unroutable"`. Kill the OSRM container; verify HTTP 503.

- [x] T014 Create `services/api/app/services/route_service.py` — initialise `httpx.AsyncClient` with `base_url=settings.OSRM_URL` and a 10-second timeout; expose `calculate_route(origin: GeoPoint, destination: GeoPoint) -> RouteGeometry` that calls `GET /route/v1/driving/{lng1},{lat1};{lng2},{lat2}?overview=full&geometries=geojson&steps=false`, parses `routes[0].distance` (metres→km), `routes[0].duration` (seconds→minutes), and `routes[0].geometry` (GeoJSON LineString), sets `is_routable=True`
- [x] T015 Add unroutable handling to `route_service.calculate_route()` — if OSRM response `code != "Ok"` or `routes` is empty, return `RouteGeometry(is_routable=False, distance_km=0, duration_minutes=0, geojson_linestring={})` rather than raising; callers check `is_routable`
- [x] T016 Add OSRM unavailable handling in `route_service.py` — catch `httpx.ConnectError`, `httpx.TimeoutException`, and any `httpx.HTTPError`; raise a distinct `RouteServiceUnavailableError` exception that endpoint handlers convert to HTTP 503
- [x] T017 [US1] Wire `calculate_route()` into `POST /api/routes/fare` in `services/api/app/api/routes/router.py` — call `route_service.calculate_route(origin, destination)`, return HTTP 422 `{"error":"unroutable"}` if not routable, HTTP 503 `{"error":"route_intelligence_unavailable"}` on `RouteServiceUnavailableError`; pass `distance_km` to `pricing_service._calc_fee_from_distance(distance_km, seat_count)` and return `FareEstimateResponse`

**Checkpoint**: `POST /api/routes/fare` returns correct fuel-cost breakdown for any two Cairo coordinates. Unroutable and service-down paths return correct error codes. US1 independently testable via Scenario 2 in quickstart.md.

---

## Phase 4: User Story 2 — Route Overlap & Compatibility Assessment (Priority: P2)

**Goal**: Given a driver's stored route and a passenger's origin/destination, the system computes overlap percentage, walk distances, driver detour, and premium pickup/dropoff eligibility with fees.

**Independent Test**: Call the internal `POST /internal/route-intelligence/compatibility` with a known (ride_id, passenger_origin, passenger_destination) pair; verify `overlap_pct`, `pickup_walk_m`, `detour_km`, `is_compatible` match pre-calculated expected values. Test with a passenger origin >500m but <2km from route; verify `premium_pickup_available=true` with a non-zero fee.

- [ ] T018 [US2] Add `calculate_overlap_pct(ride_geometry_wkt: str, passenger_route_wkt: str, buffer_m: int) -> float` to `services/api/app/services/route_service.py` — runs PostGIS SQL via asyncpg: `ST_Length(ST_Intersection(ST_Buffer(geom::geography, $buffer_m)::geometry, passenger_geom)::geography) / ST_Length(passenger_geom::geography) * 100` where `geom` is the driver route and `passenger_geom` is the passenger route
- [ ] T019 [P] [US2] Add `calculate_walk_distance(point_wkt: str, route_wkt: str) -> float` to `route_service.py` — PostGIS SQL: `ST_Distance(ST_GeomFromText($point, 4326)::geography, ST_ClosestPoint(ST_GeomFromText($route, 4326), ST_GeomFromText($point, 4326))::geography)` returns metres (straight-line approximation per spec Assumptions)
- [ ] T020 [US2] Add `calculate_detour(driver_origin: GeoPoint, pickup_point_wkt: str, dropoff_point_wkt: str, driver_destination: GeoPoint, original_distance_km: float) -> tuple[float, int]` to `route_service.py` — calls OSRM multi-waypoint route `{driver_origin};{pickup};{dropoff};{driver_dest}`, returns `(detour_km, detour_minutes)` as diff from original distance
- [ ] T021 [US2] Add `calculate_premium_detour(driver_origin: GeoPoint, passenger_point: GeoPoint, driver_destination: GeoPoint, original_distance_km: float) -> tuple[float, int]` to `route_service.py` — same pattern as T020 but uses passenger's exact coordinates instead of nearest-route point; returns `(detour_km, detour_minutes)`
- [ ] T022 [US2] Add `calculate_premium_detour_fee(detour_km: float) -> float` to `services/api/app/services/pricing_service.py` — applies `_calc_fee_from_distance(detour_km, seat_count=1)` with `seat_count=1` (premium fee is per-passenger, not split), returns `per_seat_price_egp` rounded to nearest EGP
- [ ] T023 [US2] Add `assess_compatibility(ride: dict, passenger_origin: GeoPoint, passenger_destination: GeoPoint, passenger_route_geom: RouteGeometry, config: dict) -> CompatibilityResult` to `route_service.py` — orchestrates T018–T022: computes overlap, pickup walk, dropoff walk, standard detour; checks all thresholds; sets `is_compatible`; if walk exceeds standard threshold but detour ≤ `config.max_premium_detour_km`, sets `premium_pickup_available=True` and calls T022 for the fee; assembles and returns `CompatibilityResult`

**Checkpoint**: `assess_compatibility()` returns a correct `CompatibilityResult` for any (ride, passenger request) pair when called directly. Internal endpoint (T013 stub) not yet wired, but unit-testable in isolation.

---

## Phase 5: User Story 3 — Compatible Ride Candidate Generation (Priority: P3)

**Goal**: A passenger submits an origin, destination, and departure time and receives a sorted list of standard and premium-eligible ride candidates, each with full compatibility metrics.

**Independent Test**: Scenario 3 and Scenario 4 from quickstart.md — verify correct rides appear, standard/premium are distinguished, empty list returns HTTP 200 not error, full rides are excluded.

- [ ] T024 [US3] Create `services/api/app/services/candidate_service.py` — implement `generate_candidates(origin: GeoPoint, destination: GeoPoint, departure_time: datetime, pool, config: dict) -> CandidateListResponse`
- [ ] T025 [US3] Implement Stage 1 SQL filter in `candidate_service.py` — query `rides` table: `status = 'scheduled'`, `available_seats > 0`, `route_geometry IS NOT NULL`, `departure_datetime BETWEEN (departure_time - interval) AND (departure_time + interval)` (interval from `config.time_window_minutes`), `route_geometry && ST_MakeEnvelope(bbox)` using GiST index, `ORDER BY departure_datetime LIMIT 500`; bounding box built from min/max of passenger origin+destination coords plus `config.max_premium_detour_km` padding
- [ ] T026 [US3] Implement Stage 2 compatibility pipeline in `candidate_service.py` — for each ride from Stage 1: call `route_service.calculate_route()` once for passenger route (cache result), then call `route_service.assess_compatibility(ride, ...)` per ride; collect results into `standard` (is_compatible=True) and `premium` (either premium flag True) lists; sort standard by `overlap_pct` desc, premium by total fee asc
- [ ] T027 [US3] Implement `POST /api/routes/candidates` in `services/api/app/api/routes/router.py` — JWT-authenticated (existing `get_current_user` dependency pattern); parse `CandidateSearchRequest`; call `candidate_service.generate_candidates()`; handle `RouteServiceUnavailableError` → HTTP 503; return `CandidateListResponse`
- [ ] T028 [US3] Implement `POST /internal/route-intelligence/compatibility` in `services/api/app/api/internal/route_intelligence_router.py` — shared-secret auth (T013 dependency); look up ride by `ride_id` (return 404 if not found or `route_geometry IS NULL`); call `route_service.calculate_route()` for passenger route and `route_service.assess_compatibility()`; build and return `CompatibilityFeatures` (all 14 fields from internal API contract)

**Checkpoint**: `POST /api/routes/candidates` returns correct standard/premium split for test rides. `POST /internal/route-intelligence/compatibility` returns all feature vector fields. Scenarios 3, 4, and 7 from quickstart.md pass.

---

## Phase 6: User Story 4 — Fuel-Cost-Based Fare Calculation (Priority: P4)

**Goal**: Ride creation auto-calculates and stores the system-enforced per-seat price. Drivers see a fare breakdown. Price is non-overridable.

**Independent Test**: Scenario 2 from quickstart.md (fare endpoint returns correct breakdown). Create a new ride via `POST /api/rides` and verify `price_per_seat`, `fuel_cost_egp`, `platform_commission_egp`, `safety_margin_egp`, `route_geometry`, `route_distance_km`, and `price_source='system'` are all populated on the saved ride row.

- [ ] T029 [US4] Add `calculate_fare(distance_km: float, seat_count: int) -> FareEstimateResponse` to `services/api/app/services/pricing_service.py` — wraps `_calc_fee_from_distance()`, adds `distance_km` and `fuel_price_per_litre_egp` to the response object from the cached config
- [ ] T030 [US4] Update `services/api/app/models/ride.py` `CreateRideRequest` — remove `price_per_seat` field (now system-calculated); backend rejects any `price_per_seat` in the request body with HTTP 400 `{"error":"price_override_not_allowed"}`
- [ ] T031 [US4] Update `services/api/app/api/rides/router.py` ride creation handler — before inserting the ride row: (1) call `route_service.calculate_route(origin, destination)`, return HTTP 422 `{"error":"unroutable"}` if not routable; (2) call `pricing_service.calculate_fare(route.distance_km, total_seats)`; (3) include `route_geometry` (WKT from GeoJSON), `route_distance_km`, `route_duration_minutes`, `fuel_cost_egp`, `platform_commission_egp`, `safety_margin_egp`, `price_source='system'`, and `price_per_seat` (= `per_seat_price_egp`) in the INSERT statement
- [ ] T032 [US4] Update `services/api/app/models/ride.py` `RideResponse` — add `route_distance_km`, `route_duration_minutes`, `fuel_cost_egp`, `platform_commission_egp`, `safety_margin_egp`, `price_source` fields to the response model
- [ ] T033 [US4] Update `services/api/app/services/ride_service.py` INSERT query for ride creation — add the six new columns (`route_geometry`, `route_distance_km`, `route_duration_minutes`, `fuel_cost_egp`, `platform_commission_egp`, `safety_margin_egp`, `price_source`) to the `INSERT INTO rides` SQL and the corresponding parameter list
- [ ] T034 [US4] Add `calculate_premium_fare_addition(pickup_detour_km: float, dropoff_detour_km: float) -> dict` to `pricing_service.py` — returns `{premium_pickup_fee_egp, premium_dropoff_fee_egp}` using `calculate_premium_detour_fee()` from T022; used by Phase 6 booking (Phase 6 spec) but defined here to complete the pricing contract

**Checkpoint**: New rides created via `POST /api/rides` have route geometry and fare breakdown populated; `price_per_seat` is system-calculated and non-overridable. Scenario 2 in quickstart.md passes. Scenario 6 (live config update) passes.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Observability (NFR-009), auth enforcement validation, and end-to-end quickstart run.

- [ ] T035 Add structured logging to `services/api/app/services/route_service.py` — log at INFO level on each `calculate_route()` call: input coordinates, `is_routable`, `distance_km`, `duration_minutes`, elapsed ms; log at ERROR on `RouteServiceUnavailableError`
- [ ] T036 [P] Add structured logging to `services/api/app/services/candidate_service.py` — log at INFO: input params, Stage 1 count, Stage 2 standard/premium counts, total elapsed ms; log at WARNING if pool cap (500) was hit
- [ ] T037 [P] Add structured logging to `services/api/app/services/pricing_service.py` — log at INFO on each fare calculation: `distance_km`, `fuel_price`, `per_seat_price`, `seat_count`; log at WARNING when config cache miss forces a synchronous DB refresh
- [ ] T038 Add per-endpoint request count and p95 latency logging to `POST /api/routes/candidates` and `POST /api/routes/fare` in `services/api/app/api/routes/router.py` — record start time, compute elapsed ms on response, emit a structured log line with `endpoint`, `status_code`, `duration_ms` (NFR-009; full metrics export sink is a post-competition concern — log-based metrics are sufficient for MVP)
- [ ] T039 Run quickstart.md Scenarios 1–7 end-to-end against the local stack and confirm all expected responses match; fix any discrepancies found

**Checkpoint**: All 7 quickstart scenarios pass. Every route intelligence request produces a structured log line. Stack passes `docker compose up` cleanly with OSRM serving requests.

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)         — no dependencies, start immediately
Phase 2 (Foundational)  — depends on Phase 1 completion; BLOCKS Phase 3–6
Phase 3 (US1)           — depends on Phase 2
Phase 4 (US2)           — depends on Phase 3 (uses route_service from T014)
Phase 5 (US3)           — depends on Phase 4 (uses assess_compatibility from T023)
Phase 6 (US4)           — depends on Phase 3 (uses calculate_route); independent of US2/US3
Phase 7 (Polish)        — depends on Phase 3–6 complete
```

### User Story Dependencies

- **US1 (P1)**: Unblocked after Phase 2. No dependency on other user stories.
- **US2 (P2)**: Depends on US1 (`route_service.py` established in T014). US2 extends route_service with PostGIS operations.
- **US3 (P3)**: Depends on US2 (`assess_compatibility()` in T023). US3 orchestrates the full pipeline.
- **US4 (P4)**: Depends on US1 (`calculate_route()` in T014) and Phase 2 (`_calc_fee_from_distance()` in T010). US4 is independent of US2 and US3.

### Within Each Phase

- Models before services, services before endpoints
- `assess_compatibility()` (T023) must complete before Stage 2 pipeline (T026)
- Stage 1 SQL filter (T025) must complete before Stage 2 (T026)
- Ride creation integration (T031, T033) depends on `calculate_fare()` (T029) and `calculate_route()` (T014)

### Parallel Opportunities Per Story

```
# Phase 1 — run all together:
T002, T003, T004, T005, T006  (all different files, no deps)

# Phase 2 — T007 and T008 in parallel, T009 after both:
T007 || T008  →  T009  →  T010  →  T011 || T012 || T013

# Phase 4 (US2) — overlap, walk, and premium detour in parallel:
T018 || T019  →  T020  →  T021 || T022  →  T023

# Phase 6 (US4) — model updates in parallel:
T030 [P] || T032 [P]  →  T031  →  T033  →  T034
```

---

## Implementation Strategy

### MVP Scope (US1 + US4 only — fare calculation for ride creation)

The minimum viable increment that unblocks Phase 6 (Passenger Experience):

1. Complete Phase 1 and Phase 2
2. Complete Phase 3 (US1) — OSRM route calculation works
3. Complete Phase 6 (US4) — ride creation auto-prices; `/api/routes/fare` works
4. **STOP and VALIDATE**: new rides have system-calculated prices; drivers can't override
5. Proceed to US2 and US3 for passenger search

### Full Feature Delivery Order

1. Setup (Phase 1) + Foundational (Phase 2) → foundation ready
2. US1 (Phase 3) → OSRM working, fare endpoint functional
3. US4 (Phase 6) → ride creation integrated, pricing locked
4. US2 (Phase 4) → compatibility assessment ready
5. US3 (Phase 5) → passenger candidate search working
6. Polish (Phase 7) → observability, end-to-end validation

---

## Notes

- `[P]` tasks operate on different files with no blocking dependencies — safe to parallelize
- `price_per_seat` is removed from `CreateRideRequest` in T030; update the frontend ride creation form accordingly (out of scope for this phase but coordinate with Phase 4.2 frontend)
- The OSRM data build (`scripts/osrm-setup.sh`) takes ~10–20 minutes on first run — do this before starting Phase 3 work
- `_calc_fee_from_distance()` is the single source of truth for the fuel-cost formula; never duplicate the formula elsewhere
- Phase 9 field contract (`CompatibilityFeatures`) is frozen from T028 — do not rename fields without coordinating with Phase 9 scope
