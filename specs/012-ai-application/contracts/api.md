# API Contracts: AI Application (Phase 9)

**Feature**: `012-ai-application` | **Date**: 2026-07-01

This document specifies only the **changes** Phase 9 makes to existing endpoints. All other Phase 6 endpoints remain unchanged. For the full Phase 6 base contract, see `specs/009-passenger-experience/contracts/api.md`.

All endpoints are prefixed `/api/v1`. All requests require a valid Supabase Auth JWT in `Authorization: Bearer <token>`.

---

## Changed: POST /api/v1/search/rides

Passenger ride search. Phase 9 adds AI match scoring, ranking, threshold filtering, and the `match_score_pct` field per candidate.

**Auth**: Verified passenger (`verification_status = approved`). Returns `HTTP 403` if not verified.

**Request** (unchanged from Phase 6):
```json
{
  "origin": { "lat": 30.0626, "lng": 31.2497 },
  "destination": { "lat": 30.0444, "lng": 31.2357 },
  "desired_departure_at": "2026-07-01T08:00:00Z"
}
```

**Response `200 OK`** (Phase 9 additions in bold):

```json
{
  "candidates": [
    {
      "ride_id": "uuid",
      "driver": {
        "display_name": "Ahmed Hassan",
        "avatar_url": "https://...",
        "is_verified": true
      },
      "departure_datetime": "2026-07-01T08:00:00Z",
      "available_seats": 2,
      "per_seat_price": "47.50",
      "candidate_type": "standard",
      "match_score_pct": 85,
      "compatibility": {
        "overlap_percentage": 82.5,
        "pickup_walk_meters": 210,
        "dropoff_walk_meters": 180,
        "driver_detour_km": 0.4,
        "driver_detour_minutes": 2,
        "is_compatible": true,
        "premium_pickup_available": false,
        "premium_pickup_fee": null,
        "premium_dropoff_available": false,
        "premium_dropoff_fee": null
      }
    }
  ],
  "total": 3,
  "no_rides_found": false,
  "ai_ranking_active": true
}
```

**Phase 9 field changes**:

| Field | Type | Notes |
|-------|------|-------|
| `candidates[].match_score_pct` | `integer \| null` | 0–100 percentage. `null` when AI fallback is active. Results ordered by score descending (or by `overlap_percentage` descending in fallback). |
| `candidates[].per_seat_price` | `string` | Now system-assigned (AI or deterministic fallback). Never driver-input. |
| `ai_ranking_active` | `boolean` | `true` = AI scored and ranked. `false` = deterministic fallback active (AI unavailable). |

**Filtering behaviour** (Phase 9):
- Candidates with `match_score_pct < 20` are excluded from results.
- If exclusion leaves fewer than 3 candidates, the highest-scoring suppressed candidates are added back until the list reaches 3 (or all candidates are exhausted).
- In fallback mode (`ai_ranking_active: false`): no threshold filtering; all Phase 5-compatible candidates are returned ordered by `overlap_percentage` descending.

**Notes**:
- `match_score_pct` values are `null` for all candidates when `ai_ranking_active` is `false`.
- Results list is guaranteed non-empty if Phase 5 found at least one compatible candidate.
- AI scoring adds ≤500ms to response time at p95 (NFR-001).

---

## Changed: GET /api/v1/rides/{ride_id}/passenger-detail

Ride detail for a passenger. Phase 9 adds `match_score_pct` to the response when passenger search context is provided.

**Auth**: Any authenticated user.

**Query parameters** (Phase 9 adds `departure_at`):

| Parameter | Required | Description |
|-----------|----------|-------------|
| `origin_lat` | Yes | Passenger origin latitude |
| `origin_lng` | Yes | Passenger origin longitude |
| `destination_lat` | Yes | Passenger destination latitude |
| `destination_lng` | Yes | Passenger destination longitude |
| `departure_at` | No | Passenger desired departure (ISO 8601 UTC). Used for AI scoring. If absent, `match_score_pct` is `null`. |

**Response `200 OK`** (Phase 9 addition in bold):

```json
{
  "ride": {
    "id": "uuid",
    "status": "scheduled",
    "driver": {
      "display_name": "Ahmed Hassan",
      "avatar_url": "https://...",
      "is_verified": true
    },
    "departure_datetime": "2026-07-01T08:00:00Z",
    "available_seats": 2,
    "per_seat_price": "47.50",
    "route_geometry": "encoded_polyline_string",
    "route_distance_km": 18.4,
    "route_duration_minutes": 32
  },
  "passenger_context": {
    "boarding_point": { "lat": 30.0631, "lng": 31.2481 },
    "alighting_point": { "lat": 30.0451, "lng": 31.2349 },
    "pickup_walk_meters": 210,
    "dropoff_walk_meters": 180,
    "estimated_travel_minutes": 28,
    "premium_pickup_available": false,
    "premium_pickup_fee": null,
    "premium_dropoff_available": false,
    "premium_dropoff_fee": null
  },
  "match_score_pct": 85
}
```

**Phase 9 field additions**:

| Field | Type | Notes |
|-------|------|-------|
| `match_score_pct` | `integer \| null` | 0–100 percentage. `null` if `departure_at` not provided or AI service unavailable. |

---

## Changed: POST /api/v1/rides (Driver Ride Creation)

Phase 9 removes `price_per_seat` from the request body. The system computes and assigns the fare internally.

**Auth**: Verified driver (`verification_status = approved`).

**Request** — `price_per_seat` REMOVED:

```json
{
  "vehicle_id": "uuid",
  "origin": { "lat": 30.0444, "lng": 31.2357 },
  "origin_address": "Downtown Cairo, near Tahrir Square",
  "destination": { "lat": 30.0271, "lng": 31.4697 },
  "destination_address": "New Cairo, 5th Settlement",
  "departure_datetime": "2026-07-01T08:00:00Z",
  "total_seats": 3,
  "notes": "Morning commute, quiet ride"
}
```

> ⚠️ If `price_per_seat` is included in the request body, it is **silently ignored** — it is not validated and does not affect the system-assigned fare.

**Response `201 Created`** — `price_per_seat` now reflects system-assigned fare:

```json
{
  "ride_id": "uuid",
  "status": "scheduled",
  "price_per_seat": "47.50",
  "departure_datetime": "2026-07-01T08:00:00Z",
  "created_at": "2026-07-01T07:30:00Z"
}
```

**Phase 9 field changes**:

| Field | Phase 6 | Phase 9 |
|-------|---------|---------|
| `price_per_seat` (request) | Driver-provided, required | Removed — system-computed |
| `price_per_seat` (response) | Echoed from request | System-assigned fare (deterministic formula) |

**Behaviour**:
- *(Superseded 2026-07-04 — pricing was originally an AI model call with a deterministic fallback; the AI pricing model was removed as a redundant approximation of the same formula. Fare is now always computed directly.)*
- Fare is computed by `pricing_service.calculate_fare(route_distance_km, total_seats)` — `(distance_km / fuel_efficiency_km_per_l) × fuel_price_per_litre + commission + safety_margin`, split across seats (values from `pricing_config` table).
- The fare is never zero or negative in the response — it is a fixed arithmetic formula that always produces a valid positive value.
- Ride creation has no AI dependency and cannot fail due to AI service unavailability (NFR-006 is trivially satisfied for pricing).

**Error responses** (unchanged from Phase 6):
- `403` — Driver not verified
- `422` — Validation failure (missing required fields)
- `409` — Vehicle not owned by driver, or driver has insufficient balance (Phase 8)

---

## Internal Contract Stability Note

The field names in `specs/008-route-intelligence/contracts/internal-ai-features-api.md` (`CompatibilityFeatures`) are the Phase 9 feature vector input. They **must not be renamed, retyped, or removed** without a coordinated model retrain (see Phase 2 spec note on feature vector stability).
