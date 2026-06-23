# API Contract: Route Intelligence (User-Facing)

**Feature**: `008-route-intelligence` | **Date**: 2026-06-22

All endpoints require a valid **Supabase Auth JWT** in the `Authorization: Bearer <token>` header. Unauthenticated requests are rejected with HTTP 401.

Base path: `/api/routes`

---

## POST /api/routes/candidates

Find rides compatible with a passenger's trip request.

**Auth**: Supabase Auth JWT (passenger role)

**Request body**:
```json
{
  "origin": { "lat": 30.0626, "lng": 31.2497 },
  "destination": { "lat": 30.0444, "lng": 31.2357 },
  "departure_time": "2026-06-23T08:00:00Z"
}
```

**Response 200**:
```json
{
  "standard": [
    {
      "ride_id": "uuid",
      "driver_id": "uuid",
      "departure_time": "2026-06-23T08:15:00Z",
      "available_seats": 3,
      "price_per_seat_egp": 8.0,
      "candidate_type": "standard",
      "compatibility": {
        "overlap_pct": 82.5,
        "pickup_walk_m": 210.0,
        "dropoff_walk_m": 145.0,
        "detour_km": 0.8,
        "detour_minutes": 3,
        "is_compatible": true,
        "premium_pickup_available": false,
        "premium_pickup_detour_km": 0.0,
        "premium_pickup_fee_egp": null,
        "premium_dropoff_available": false,
        "premium_dropoff_detour_km": 0.0,
        "premium_dropoff_fee_egp": null
      }
    }
  ],
  "premium": [
    {
      "ride_id": "uuid",
      "driver_id": "uuid",
      "departure_time": "2026-06-23T08:05:00Z",
      "available_seats": 2,
      "price_per_seat_egp": 12.0,
      "candidate_type": "premium",
      "compatibility": {
        "overlap_pct": 65.0,
        "pickup_walk_m": 750.0,
        "dropoff_walk_m": 90.0,
        "detour_km": 1.4,
        "detour_minutes": 5,
        "is_compatible": false,
        "premium_pickup_available": true,
        "premium_pickup_detour_km": 1.4,
        "premium_pickup_fee_egp": 4.0,
        "premium_dropoff_available": false,
        "premium_dropoff_detour_km": 0.0,
        "premium_dropoff_fee_egp": null
      }
    }
  ],
  "total_count": 2
}
```

**Response 200 (no matches)**:
```json
{ "standard": [], "premium": [], "total_count": 0 }
```

**Response 503** (OSRM unavailable):
```json
{ "error": "route_intelligence_unavailable", "message": "Route intelligence temporarily unavailable. Please try again shortly." }
```

**Response 401**: Missing or invalid JWT.

**Sort order**: `standard` sorted by `overlap_pct` descending; `premium` sorted by total premium fee ascending. Both lists are replaced by Phase 9 AI reranking when operational.

---

## POST /api/routes/fare

Calculate the system-generated per-seat fare for a driver's ride.

**Auth**: Supabase Auth JWT (driver role)

**Request body**:
```json
{
  "origin": { "lat": 30.0626, "lng": 31.2497 },
  "destination": { "lat": 30.0444, "lng": 31.2357 },
  "seat_count": 4
}
```

**Response 200**:
```json
{
  "distance_km": 18.3,
  "fuel_price_per_litre_egp": 15.00,
  "fuel_cost_egp": 21.12,
  "platform_commission_egp": 4.22,
  "safety_margin_egp": 5.00,
  "seat_count": 4,
  "per_seat_price_egp": 8.0,
  "total_collected_egp": 32.0
}
```

**Response 422** (unroutable origin/destination):
```json
{ "error": "unroutable", "message": "No road-network route found between the provided points. Ride creation is blocked until a valid route exists." }
```

**Response 503** (OSRM unavailable):
```json
{ "error": "route_intelligence_unavailable", "message": "Route intelligence temporarily unavailable." }
```

**Response 401**: Missing or invalid JWT.

**Notes**:
- The returned `per_seat_price_egp` is the system-enforced price. The driver cannot override it.
- This endpoint is called by the ride creation flow (from the existing `POST /api/rides` handler). The fare breakdown values (`fuel_cost_egp`, `platform_commission_egp`, `safety_margin_egp`) are written to the `rides` row at creation.
- Calling this endpoint standalone (outside ride creation) is valid for price preview during ride form entry.
