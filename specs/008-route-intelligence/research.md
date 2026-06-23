# Research: Route Intelligence

**Feature**: `008-route-intelligence` | **Date**: 2026-06-22

All decisions below resolve technical unknowns from the spec and plan. No NEEDS CLARIFICATION items remain.

---

## Decision 1 — OSRM Integration Method

**Decision**: Call OSRM via its REST HTTP API using `httpx` (async) from `route_service.py`. Request `geometries=geojson` so the route geometry arrives as a GeoJSON LineString — compatible with PostGIS `ST_GeomFromGeoJSON()` for direct storage.

**OSRM endpoints used**:

| Endpoint | Purpose |
|---|---|
| `GET /route/v1/driving/{lng1},{lat1};{lng2},{lat2}?overview=full&geometries=geojson&steps=false` | Route between two points — returns distance (m), duration (s), GeoJSON LineString |
| `GET /nearest/v1/driving/{lng},{lat}` | Snap a coordinate to the nearest road node |

**Key response fields**:
```
routes[0].distance       → metres (convert to km: /1000)
routes[0].duration       → seconds (convert to minutes: /60)
routes[0].geometry       → GeoJSON LineString (coordinates array)
```

**Rationale**: httpx is the standard async HTTP client for FastAPI projects; it already handles connection pooling and timeouts. GeoJSON geometry avoids a format conversion step when persisting to PostGIS. OSRM REST is stable and self-contained — no SDK needed.

**Alternatives considered**:
- `aiohttp`: viable but httpx is more idiomatic in modern FastAPI stacks
- OSRM Python bindings (`osrm-py`): not maintained, REST API is simpler
- `polyline` encoding: rejected — requires decoding before PostGIS operations

**New dependency**: add `httpx>=0.27.0` to `services/api/pyproject.toml`.

---

## Decision 2 — OSRM Docker Setup (CH Algorithm)

**Decision**: Use OSRM with the **Contraction Hierarchies (CH)** algorithm. Process the Egypt OSM extract once with a setup script; serve with `osrm-routed --algorithm ch`.

**Docker service** (add to `docker-compose.yml`):
```yaml
osrm:
  image: osrm/osrm-backend:v5.27.1
  command: osrm-routed --algorithm ch /data/egypt-latest.osrm
  volumes:
    - ./osrm-data:/data:ro
  ports:
    - "5000:5000"
  networks:
    - fe-el-seka-dev
```

**One-time setup script** (`scripts/osrm-setup.sh`):
```bash
#!/usr/bin/env bash
# Download Egypt OSM extract (~200MB) and build OSRM routing graph
set -e
mkdir -p osrm-data
curl -L -o osrm-data/egypt-latest.osm.pbf \
  https://download.geofabrik.de/africa/egypt-latest.osm.pbf

docker run --rm -v "$(pwd)/osrm-data:/data" osrm/osrm-backend:v5.27.1 \
  osrm-extract -p /opt/car.lua /data/egypt-latest.osm.pbf

docker run --rm -v "$(pwd)/osrm-data:/data" osrm/osrm-backend:v5.27.1 \
  osrm-contract /data/egypt-latest.osrm
```

**Rationale**: CH preprocessing produces a single static graph that supports very fast (sub-millisecond) route queries. No traffic updates are needed for MVP. MLD is more complex and only beneficial when live traffic data is available (post-competition enhancement).

**Alternatives considered**:
- MLD algorithm: better for live traffic but no traffic data source in scope
- Commercial routing API (Google Maps, Mapbox): violates approved technology stack (OSM + OSRM)
- Valhalla: more features but much heavier deployment footprint for MVP

---

## Decision 3 — PostGIS Overlap Calculation

**Decision**: At search time, calculate the passenger's route geometry from OSRM, then compute overlap for each candidate using PostGIS geography operations in SQL. Walk distances use `ST_ClosestPoint` + `ST_Distance` (straight-line approximation, per spec).

**SQL pattern for overlap**:
```sql
-- passenger_route: WKT or GeoJSON LineString from OSRM (passed as parameter)
-- driver_route: stored as rides.route_geometry GEOMETRY(LINESTRING, 4326)
-- buffer_m: from pricing_config.corridor_buffer_radius_m (default 150)

SELECT
  ST_Length(
    ST_Intersection(
      ST_Buffer(rides.route_geometry::geography, $buffer_m)::geometry,
      ST_GeomFromText($passenger_route_wkt, 4326)
    )::geography
  ) / ST_Length(ST_GeomFromText($passenger_route_wkt, 4326)::geography) * 100
  AS overlap_pct
FROM rides
WHERE rides.id = $ride_id;
```

**SQL pattern for pickup walk distance** (nearest point on driver route):
```sql
SELECT
  ST_Distance(
    ST_GeomFromText($passenger_origin_wkt, 4326)::geography,
    ST_ClosestPoint(
      rides.route_geometry,
      ST_GeomFromText($passenger_origin_wkt, 4326)
    )::geography
  ) AS pickup_walk_m
FROM rides WHERE id = $ride_id;
```

**SQL pattern for detour distance** (standard — driver deviates to serve via route corridor):
```sql
-- Detour is computed via OSRM by routing:
--   driver_origin → closest_pickup_point → passenger_destination_closest_point → driver_destination
-- and subtracting the original route_distance_km.
-- This is done in Python (route_service.py), not SQL.
```

**Rationale**: PostGIS `ST_Buffer` + `ST_Intersection` is the canonical approach for corridor-based route overlap. Running the overlap calculation in SQL (rather than in Python) avoids shipping large geometry objects over the wire. The straight-line walk approximation (ST_Distance on geography type) is accepted for MVP per spec Assumptions.

---

## Decision 4 — Candidate Pool Query Strategy (Two-Stage)

**Decision**: Two-stage filtering to cap computation at 500 rides.

**Stage 1 — SQL filter** (fast, index-driven):
```sql
SELECT id, driver_id, departure_datetime, available_seats, price_per_seat,
       route_geometry, route_distance_km, origin_lat, origin_lng,
       destination_lat, destination_lng
FROM rides
WHERE
  status = 'scheduled'
  AND available_seats > 0
  AND route_geometry IS NOT NULL
  AND departure_datetime BETWEEN ($requested_time - $window) AND ($requested_time + $window)
  AND route_geometry && ST_MakeEnvelope($bbox_min_lng, $bbox_min_lat, $bbox_max_lng, $bbox_max_lat, 4326)
ORDER BY departure_datetime
LIMIT 500;
```

The bounding box (`ST_MakeEnvelope`) is built from the passenger's origin and destination with padding equal to `max_premium_detour_km` (2 km default) in each direction. The `&&` operator uses the GiST index on `rides.route_geometry` for fast elimination.

**Stage 2 — Compatibility pipeline** (Python + PostGIS per ride):
For each ride from Stage 1:
1. Compute overlap_pct via PostGIS (single SQL query)
2. Compute pickup_walk_m via ST_ClosestPoint + ST_Distance (single SQL query)
3. Compute dropoff_walk_m (same pattern)
4. If overlap and walk distances pass standard thresholds → call OSRM for detour
5. If walk exceeds standard but within premium limit → flag as premium-eligible + compute fee
6. Build CompatibilityResult (transient, not saved)

**Rationale**: The GiST spatial index on `route_geometry` makes Stage 1 fast. Computing PostGIS operations per-ride in Stage 2 is acceptable at ≤500 rides for MVP. The bounding-box pre-filter eliminates rides that geometrically cannot overlap before the heavier per-ride computation runs.

---

## Decision 5 — Detour Calculation Method

**Decision**: For standard detour (driver picks up from route corridor), call OSRM with waypoints:
`driver_origin → nearest_pickup_point → nearest_dropoff_point → driver_destination`
and subtract the original `route_distance_km`. For premium detour (driver goes to passenger's exact point), use passenger's exact coordinates as the waypoint.

**OSRM multi-waypoint call**:
```
GET /route/v1/driving/{orig_lng},{orig_lat};{pickup_lng},{pickup_lat};{drop_lng},{drop_lat};{dest_lng},{dest_lat}
    ?overview=false&steps=false
```

Returns `routes[0].distance` (total with waypoints). Detour = `(waypoint_route_distance - original_route_distance)`.

**Rationale**: OSRM natively handles multi-waypoint routing. This is more accurate than summing segment estimates. `overview=false&steps=false` minimises response size since we only need the total distance/duration.

---

## Decision 6 — Pricing Config Caching

**Decision**: Load `pricing_config` from DB into a module-level `_config_cache` dict in `pricing_service.py` on startup. A background `asyncio` task refreshes it every **30 seconds** (safely within the 60-second NFR-007 requirement). Use `asyncio.Lock` to prevent concurrent refresh races.

```python
_config_cache: dict = {}
_config_lock = asyncio.Lock()

async def _refresh_pricing_config(pool) -> None:
    async with _config_lock:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM pricing_config LIMIT 1")
            _config_cache.update(dict(row))

async def pricing_config_refresh_loop(pool) -> None:
    while True:
        await _refresh_pricing_config(pool)
        await asyncio.sleep(30)
```

The refresh loop is started in `main.py`'s `lifespan` function alongside the existing `email_retry_loop`.

**Rationale**: Matches the existing pattern in the codebase (`email_retry_loop`). 30-second refresh is well within the 60-second NFR-007 SLA. Avoids a DB hit on every fare calculation request.

---

## Decision 7 — Phase 9 AI Service Feature Contract

**Decision**: The internal endpoint at `POST /internal/route-intelligence/compatibility` returns a `CompatibilityFeatures` payload with the numeric feature vector the Phase 9 XGBoost model will consume.

**Feature vector fields**:

| Field | Type | Description |
|---|---|---|
| `ride_id` | UUID | Candidate ride identifier |
| `overlap_pct` | float | Route corridor overlap percentage (0–100) |
| `pickup_walk_m` | float | Walk distance to boarding point (metres) |
| `dropoff_walk_m` | float | Walk distance from alighting point (metres) |
| `detour_km` | float | Driver detour distance (km) |
| `detour_minutes` | int | Driver detour time (minutes) |
| `passenger_route_km` | float | Passenger's total journey distance |
| `driver_route_km` | float | Driver's total route distance |
| `available_seats` | int | Seats available at query time |
| `departure_delta_minutes` | int | Abs. diff between driver departure and passenger requested time |
| `price_per_seat_egp` | float | Current per-seat price |
| `is_compatible` | bool | Passes all standard thresholds |
| `premium_pickup_available` | bool | Premium pickup eligible |
| `premium_dropoff_available` | bool | Premium dropoff eligible |

This contract is finalised here and MUST NOT change between Phase 5 and Phase 9 without a coordinated version bump. Phase 9 uses these features as its model input; renaming fields breaks the model pipeline.

**Authentication**: `X-Internal-Secret: {shared_secret}` header (stored in `settings.internal_secret`).

---

## Decision 8 — Rides Table: price_per_seat Transition

**Decision**: From Phase 5 onwards, `price_per_seat` on the `rides` table is always system-calculated and set by the backend at ride creation time (via `pricing_service.calculate_fare()`). The `price_source` column (default `'system'`) is always `'system'` for new rides created after this phase. Phase 4 rides that have `price_source = NULL` (set before migration) are treated as manually-priced legacy rides and are excluded from candidate generation (they also have no `route_geometry`).

No data migration is needed for existing rides — they retain their manual prices and remain excluded from Phase 5 candidate matching (already handled by the `route_geometry IS NOT NULL` filter in Stage 1).
