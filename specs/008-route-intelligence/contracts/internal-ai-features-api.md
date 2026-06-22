# API Contract: Route Intelligence (Internal — Phase 9 AI Service)

**Feature**: `008-route-intelligence` | **Date**: 2026-06-22

This endpoint is consumed exclusively by the Phase 9 AI service (`services/ai`). It is NOT reachable from the Main App or any client application.

**Auth**: `X-Internal-Secret: {value}` header. Value must match `settings.internal_secret` (stored in `services/api/.env`). Requests without a valid secret are rejected with HTTP 403.

Base path: `/internal/route-intelligence`

**IMPORTANT — Feature Contract Stability**: The field names and types in `CompatibilityFeatures` are the input feature vector for the Phase 9 XGBoost model. They MUST NOT be renamed, retyped, or removed between Phase 5 and Phase 9 without a coordinated version bump and model retrain.

---

## POST /internal/route-intelligence/compatibility

Compute the full compatibility feature vector for a (passenger-request, ride) pair. Called by the Phase 9 AI scoring service to obtain input features for match score prediction.

**Request body**:
```json
{
  "ride_id": "uuid",
  "passenger_origin": { "lat": 30.0626, "lng": 31.2497 },
  "passenger_destination": { "lat": 30.0444, "lng": 31.2357 },
  "requested_departure_time": "2026-06-23T08:00:00Z"
}
```

**Response 200**:
```json
{
  "ride_id": "uuid",
  "overlap_pct": 82.5,
  "pickup_walk_m": 210.0,
  "dropoff_walk_m": 145.0,
  "detour_km": 0.8,
  "detour_minutes": 3,
  "passenger_route_km": 12.4,
  "driver_route_km": 18.3,
  "available_seats": 3,
  "departure_delta_minutes": 15,
  "price_per_seat_egp": 8.0,
  "is_compatible": true,
  "premium_pickup_available": false,
  "premium_dropoff_available": false
}
```

**Response 404**: Ride ID does not exist or has no route geometry (legacy Phase 4 ride).

**Response 403**: Missing or invalid `X-Internal-Secret` header.

**Response 503**: OSRM unavailable.

---

## Field Definitions

| Field | Type | Description |
|---|---|---|
| `ride_id` | UUID | The driver ride being scored |
| `overlap_pct` | float | % of passenger's journey within driver's route corridor (0–100) |
| `pickup_walk_m` | float | Walk distance from passenger origin to nearest boarding point (metres) |
| `dropoff_walk_m` | float | Walk distance from nearest alighting point to passenger destination (metres) |
| `detour_km` | float | Extra km driver incurs to serve this passenger |
| `detour_minutes` | int | Extra minutes driver incurs |
| `passenger_route_km` | float | Total road-network distance of passenger's journey |
| `driver_route_km` | float | Total road-network distance of driver's planned route |
| `available_seats` | int | Available seats at time of call |
| `departure_delta_minutes` | int | `abs(driver_departure - requested_departure)` in minutes |
| `price_per_seat_egp` | float | Current per-seat price in EGP |
| `is_compatible` | bool | Passes all standard compatibility thresholds |
| `premium_pickup_available` | bool | Premium pickup option available (walk > standard threshold but within premium limit) |
| `premium_dropoff_available` | bool | Premium dropoff option available |
