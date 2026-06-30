# Data Model: AI Application (Phase 9)

**Branch**: `012-ai-application` | **Date**: 2026-07-01

---

## Database Changes

### No New Tables or Columns

Phase 9 requires **no database migration**. The existing `rides.price_per_seat NUMERIC(10, 2) NOT NULL` column (from `20260617000001_ride_management.sql`) serves as the system fare column. AI match scores are ephemeral and not persisted.

### Existing Column — rides.price_per_seat

| Column | Type | Constraint | Change in Phase 9 |
|--------|------|------------|-------------------|
| `price_per_seat` | `NUMERIC(10, 2)` | `NOT NULL, CHECK (price_per_seat > 0)` | Now populated by the AI pricing model (or deterministic fallback) at ride creation. No longer accepted from the driver's request body. |

### Fare Immutability (Application Layer)

`price_per_seat` is excluded from the `UpdateRideRequest` Pydantic schema. No database trigger in Phase 9 (planned for Phase 12 hardening).

---

## Python Pydantic Schemas — `services/api/app/models/ai.py`

```python
from __future__ import annotations
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field


class ZoneCentroid(BaseModel):
    lat: float
    lng: float


class PassengerRequestFeatures(BaseModel):
    origin_zone: str
    destination_zone: str
    origin_centroid: ZoneCentroid
    destination_centroid: ZoneCentroid
    departure_at: datetime


class CandidateFeatures(BaseModel):
    ride_id: str
    driver_origin_zone: str
    driver_destination_zone: str
    driver_origin_centroid: ZoneCentroid
    driver_dest_centroid: ZoneCentroid
    driver_departure_at: datetime
    estimated_overlap_ratio: float = Field(ge=0.0, le=1.0)
    estimated_pickup_detour_km: float = Field(ge=0.0)
    estimated_dropoff_distance_km: float = Field(ge=0.0)


class AIMatchScoreRequest(BaseModel):
    passenger_request: PassengerRequestFeatures
    candidates: list[CandidateFeatures] = Field(min_length=1, max_length=20)


class ScoredCandidate(BaseModel):
    ride_id: str
    match_score: float              # Internal 0.0–1.0 (clamped before use)
    match_score_pct: int            # Displayed value: round(match_score * 100)


class AIMatchScoreResponse(BaseModel):
    model_version: str
    scores: list[ScoredCandidate]


class AIRankingRequest(BaseModel):
    candidates: list[ScoredCandidate]


class AIRankingResponse(BaseModel):
    model_version: str
    ranked: list[str]               # ride_id strings, best match first


class AIPriceRequest(BaseModel):
    origin_zone: str
    destination_zone: str
    origin_centroid: ZoneCentroid
    destination_centroid: ZoneCentroid
    estimated_distance_km: float = Field(gt=0.0)
    departure_at: datetime


class AIPriceResponse(BaseModel):
    model_version: str
    min_egp: Decimal
    max_egp: Decimal                # System fare = round((min + max) / 2, 2)
```

---

## TypeScript Type Extensions — `apps/main/src/lib/api/`

### search.ts — Extended RideCandidate

```typescript
export interface RideCandidate {
  ride_id: string
  driver: {
    display_name: string
    avatar_url: string | null
    is_verified: boolean
  }
  departure_datetime: string
  available_seats: number
  per_seat_price: string            // EGP, e.g. "45.00" — system-assigned
  candidate_type: "standard" | "premium"
  match_score_pct: number | null    // 0–100; null when AI unavailable (fallback mode)
  compatibility: {
    overlap_percentage: number
    pickup_walk_meters: number
    dropoff_walk_meters: number
    driver_detour_km: number
    driver_detour_minutes: number
    is_compatible: boolean
    premium_pickup_available: boolean
    premium_pickup_fee: string | null
    premium_dropoff_available: boolean
    premium_dropoff_fee: string | null
  }
}

export interface RideSearchResponse {
  candidates: RideCandidate[]
  total: number
  no_rides_found: boolean
  ai_ranking_active: boolean        // true = AI scored; false = deterministic fallback
}
```

### rides.ts — Updated CreateRide types

```typescript
// price_per_seat REMOVED — system-assigned at creation
export interface CreateRideRequest {
  vehicle_id: string
  origin: { lat: number; lng: number }
  origin_address: string
  destination: { lat: number; lng: number }
  destination_address: string
  departure_datetime: string        // ISO 8601 UTC
  total_seats: number
  notes?: string
}

export interface CreateRideResponse {
  ride_id: string
  status: "scheduled"
  price_per_seat: string            // System-assigned fare, e.g. "47.50"
  departure_datetime: string
  created_at: string
}

// Ride detail — extended with match score for passenger view
export interface RidePassengerDetail {
  ride: {
    id: string
    status: string
    driver: {
      display_name: string
      avatar_url: string | null
      is_verified: boolean
    }
    departure_datetime: string
    available_seats: number
    per_seat_price: string
    route_geometry: string
    route_distance_km: number
    route_duration_minutes: number
  }
  passenger_context: {
    boarding_point: { lat: number; lng: number }
    alighting_point: { lat: number; lng: number }
    pickup_walk_meters: number
    dropoff_walk_meters: number
    estimated_travel_minutes: number
    premium_pickup_available: boolean
    premium_pickup_fee: string | null
    premium_dropoff_available: boolean
    premium_dropoff_fee: string | null
  }
  match_score_pct: number | null    // null if AI unavailable or context not provided
}
```

---

## Zone Lookup Table — `services/api/app/utils/zone_lookup.py`

```python
CAIRO_ZONES = [
    {"name": "Downtown Cairo",  "lat": 30.0444, "lng": 31.2357},
    {"name": "Maadi",           "lat": 30.0131, "lng": 31.2089},
    {"name": "Zamalek",         "lat": 30.0626, "lng": 31.2197},
    {"name": "Heliopolis",      "lat": 30.0876, "lng": 31.3219},
    {"name": "Nasr City",       "lat": 30.0561, "lng": 31.3360},
    {"name": "New Cairo",       "lat": 30.0271, "lng": 31.4697},
    {"name": "6th of October",  "lat": 29.9285, "lng": 30.9188},
    {"name": "Giza",            "lat": 30.0131, "lng": 31.2089},
    {"name": "Mohandessin",     "lat": 30.0619, "lng": 31.1997},
    {"name": "Dokki",           "lat": 30.0380, "lng": 31.2114},
    {"name": "Shubra",          "lat": 30.1060, "lng": 31.2436},
    {"name": "Ain Shams",       "lat": 30.1180, "lng": 31.3197},
    {"name": "Smart Village",   "lat": 30.0723, "lng": 30.9703},
]

def nearest_zone(lat: float, lng: float) -> tuple[str, dict[str, float]]:
    zone = min(CAIRO_ZONES, key=lambda z: (z["lat"] - lat) ** 2 + (z["lng"] - lng) ** 2)
    return zone["name"], {"lat": zone["lat"], "lng": zone["lng"]}
```

---

## `MatchScoreBadge` Component Contract

**File**: `apps/main/src/components/search/MatchScoreBadge.tsx`

```typescript
interface MatchScoreBadgeProps {
  score_pct: number | null   // 0–100; null renders nothing (or skeleton placeholder)
}
```

**Colour coding**:

| Score range | Colour | Tailwind classes |
|-------------|--------|-----------------|
| ≥ 70% | Green | `bg-green-100 text-green-800` |
| 40% – 69% | Amber | `bg-amber-100 text-amber-800` |
| < 40% | Grey | `bg-gray-100 text-gray-600` |
| `null` | Hidden | (render nothing) |

**Display text**: `"{score_pct}% match"` — e.g., `"85% match"`.
