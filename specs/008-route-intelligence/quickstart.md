# Quickstart Validation Guide: Route Intelligence

**Feature**: `008-route-intelligence` | **Date**: 2026-06-22

This guide provides runnable validation scenarios that prove the feature works end-to-end. It is not an implementation guide — refer to [data-model.md](data-model.md) for schema details and [contracts/](contracts/) for full endpoint specs.

---

## Prerequisites

1. **OSRM data built**: run `scripts/osrm-setup.sh` once to download the Egypt OSM extract and build the routing graph into `osrm-data/`.
2. **Supabase running locally**: `supabase start` (provides PostgreSQL + PostGIS).
3. **Migrations applied**: run migrations `005_add_pricing_config.sql` and `006_add_ride_geometry.sql` against the local DB.
4. **Stack up**: `docker compose up` — starts `api`, `osrm`, `main`, `ai`, `nginx`.
5. **Pricing config seeded**: the migration seeds one default row in `pricing_config` (fuel: 15 EGP/L, safety: 5 EGP, buffer: 150m). No manual step needed.
6. **Test data**: at least one verified driver with an active vehicle and one published ride (with `route_geometry` populated) in `scheduled` status with available seats.

---

## Scenario 1 — Route Path Calculation (FR-001 to FR-004)

**Goal**: Verify OSRM is reachable and returns road-network data.

```bash
# Direct OSRM check — Maadi to Tahrir (Cairo)
curl "http://localhost:5000/route/v1/driving/31.2497,30.0626;31.2357,30.0444?overview=full&geometries=geojson&steps=false"
```

**Expected**: HTTP 200, `routes[0].distance > 0`, `routes[0].geometry.type == "LineString"`, `routes[0].geometry.coordinates` is a non-empty array.

**Unroutable check**:
```bash
curl "http://localhost:5000/route/v1/driving/0,0;1,1?overview=false"
```
**Expected**: `code == "NoRoute"` (ocean coordinates — no road network).

---

## Scenario 2 — Fare Calculation (FR-024 to FR-027)

**Goal**: Verify the fuel-cost formula produces the correct per-seat price.

```bash
# As a logged-in driver (replace TOKEN with a valid Supabase JWT)
curl -X POST http://localhost/api/routes/fare \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "origin":      { "lat": 30.0626, "lng": 31.2497 },
    "destination": { "lat": 30.0444, "lng": 31.2357 },
    "seat_count": 4
  }'
```

**Expected**:
- HTTP 200
- `distance_km > 0` (road-network, not 0)
- `fuel_price_per_litre_egp == 15.0`
- `fuel_cost_egp ≈ distance_km / 13 * 15` (within ±5%)
- `platform_commission_egp ≈ fuel_cost_egp * 0.20`
- `safety_margin_egp == 5.0`
- `per_seat_price_egp == round((fuel_cost + commission + safety) / 4)` (nearest EGP)
- `total_collected_egp == per_seat_price_egp * 4`

**Unroutable check**:
```bash
curl -X POST http://localhost/api/routes/fare \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "origin": { "lat": 0.0, "lng": 0.0 }, "destination": { "lat": 1.0, "lng": 1.0 }, "seat_count": 2 }'
```
**Expected**: HTTP 422, `error == "unroutable"`.

---

## Scenario 3 — Candidate Search: Standard Match (FR-017 to FR-023)

**Goal**: Verify a passenger receives compatible rides with correct compatibility metrics.

**Setup**: Publish a ride (as a verified driver) from Maadi to Dokki departing at 08:15. The ride creation flow should populate `route_geometry`, `route_distance_km`, and `price_per_seat` automatically.

```bash
# As a logged-in passenger
curl -X POST http://localhost/api/routes/candidates \
  -H "Authorization: Bearer PASSENGER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "origin":           { "lat": 30.0580, "lng": 31.2500 },
    "destination":      { "lat": 30.0444, "lng": 31.2200 },
    "departure_time":   "2026-06-23T08:00:00Z"
  }'
```

**Expected**:
- HTTP 200
- The test ride appears in `standard` (or `premium` if walk distance exceeds 500m)
- `compatibility.overlap_pct > 0`
- `compatibility.is_compatible == true` for standard candidates
- `candidate_type == "standard"` for rides within all thresholds
- `total_count >= 1`

**No-match check**: Use a passenger origin/destination far from all existing rides.
**Expected**: `{ "standard": [], "premium": [], "total_count": 0 }` — HTTP 200, not an error.

---

## Scenario 4 — Candidate Search: Premium Candidate

**Goal**: Verify that a ride where the passenger's origin exceeds the walk threshold (>500m) but is within the premium detour limit (≤2km) appears as a premium candidate with a calculated fee.

**Setup**: Use a passenger origin that is 700m from the nearest point on the test ride's route (beyond the 500m walk threshold, within the 2km premium limit).

**Expected** in response:
- Ride appears in `premium` list, not `standard`
- `candidate_type == "premium"`
- `compatibility.is_compatible == false`
- `compatibility.premium_pickup_available == true`
- `compatibility.premium_pickup_fee_egp > 0`
- `compatibility.premium_pickup_detour_km > 0 and <= 2.0`

---

## Scenario 5 — Authentication Enforcement (NFR-008)

**Goal**: Verify unauthenticated requests are rejected.

```bash
# No Authorization header
curl -X POST http://localhost/api/routes/candidates \
  -H "Content-Type: application/json" \
  -d '{ "origin": { "lat": 30.0626, "lng": 31.2497 }, "destination": { "lat": 30.0444, "lng": 31.2357 }, "departure_time": "2026-06-23T08:00:00Z" }'
```
**Expected**: HTTP 401.

```bash
# Internal endpoint without secret
curl -X POST http://localhost/internal/route-intelligence/compatibility \
  -H "Content-Type: application/json" \
  -d '{ "ride_id": "some-uuid", ... }'
```
**Expected**: HTTP 403.

---

## Scenario 6 — Pricing Config Live Update (NFR-007)

**Goal**: Verify pricing config changes take effect within 60 seconds without restart.

1. Note current `per_seat_price_egp` from Scenario 2.
2. In Supabase Studio (dashboard), update `pricing_config.fuel_price_per_litre` from 15 to 20.
3. Wait 35 seconds (one cache refresh cycle).
4. Re-call `POST /api/routes/fare` with the same inputs.

**Expected**: `fuel_price_per_litre_egp == 20.0`, `per_seat_price_egp` is higher than in step 1. No restart performed.

---

## Scenario 7 — Internal AI Features Endpoint (Research Decision 7)

**Goal**: Verify the Phase 9 feature contract endpoint returns the correct feature vector.

```bash
curl -X POST http://localhost/internal/route-intelligence/compatibility \
  -H "X-Internal-Secret: YOUR_INTERNAL_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "ride_id": "THE_TEST_RIDE_UUID",
    "passenger_origin":      { "lat": 30.0580, "lng": 31.2500 },
    "passenger_destination": { "lat": 30.0444, "lng": 31.2200 },
    "requested_departure_time": "2026-06-23T08:00:00Z"
  }'
```

**Expected**: HTTP 200, all 14 fields from the [internal API contract](contracts/internal-ai-features-api.md) present, `departure_delta_minutes == 15` (08:00 requested, 08:15 ride departure).

---

## Performance Spot-Checks

These are manual timing checks, not automated benchmarks.

| Check | How | Target |
|---|---|---|
| Fare calculation | `time curl POST /api/routes/fare ...` | < 500ms wall clock |
| Candidate search (small pool) | `time curl POST /api/routes/candidates ...` | < 3s wall clock |
| Pricing config refresh | See Scenario 6 | Change visible within 60s |
