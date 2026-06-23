# Data Model: Route Intelligence

**Feature**: `008-route-intelligence` | **Date**: 2026-06-22

---

## Database Changes

### New Table: `pricing_config`

Singleton table (enforced via application logic — always exactly one row). Admin edits values directly via the Supabase dashboard.

```sql
-- migrations/005_add_pricing_config.sql

CREATE TABLE pricing_config (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pricing formula parameters (FR-024, FR-025)
    fuel_price_per_litre    NUMERIC(10, 2)  NOT NULL DEFAULT 15.00,   -- EGP/L
    safety_margin           NUMERIC(10, 2)  NOT NULL DEFAULT 5.00,    -- EGP per ride

    -- Compatibility thresholds (configurable, FR-005, FR-010, FR-014)
    corridor_buffer_radius_m    INTEGER     NOT NULL DEFAULT 150,     -- metres
    min_overlap_pct             NUMERIC(5, 2)  NOT NULL DEFAULT 50.00, -- %
    max_pickup_walk_m           INTEGER     NOT NULL DEFAULT 500,     -- metres
    max_dropoff_walk_m          INTEGER     NOT NULL DEFAULT 500,     -- metres
    max_detour_km               NUMERIC(10, 2) NOT NULL DEFAULT 3.00, -- km
    max_detour_minutes          INTEGER     NOT NULL DEFAULT 10,      -- minutes
    max_premium_detour_km       NUMERIC(10, 2) NOT NULL DEFAULT 2.00, -- km (FR-014)
    time_window_minutes         INTEGER     NOT NULL DEFAULT 30,      -- ±minutes from requested time

    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed the single default row
INSERT INTO pricing_config (id) VALUES (gen_random_uuid());

-- Trigger to keep updated_at current
CREATE OR REPLACE FUNCTION set_pricing_config_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;

CREATE TRIGGER pricing_config_updated_at
    BEFORE UPDATE ON pricing_config
    FOR EACH ROW EXECUTE FUNCTION set_pricing_config_updated_at();
```

**RLS**: Admin-only write access. Read access for the API service role (via service role key). No passenger/driver row-level access.

---

### Modified Table: `rides`

Adds route geometry, fare breakdown, and price provenance columns.

```sql
-- migrations/006_add_ride_geometry.sql

-- Route geometry and travel stats (populated at ride creation from OSRM)
ALTER TABLE rides
    ADD COLUMN route_geometry       GEOMETRY(LINESTRING, 4326)  NULL,
    ADD COLUMN route_distance_km    NUMERIC(10, 2)              NULL,
    ADD COLUMN route_duration_minutes INTEGER                   NULL;

-- Fare breakdown (persisted for audit trail per Technical Considerations)
ALTER TABLE rides
    ADD COLUMN fuel_cost_egp            NUMERIC(10, 2)  NULL,
    ADD COLUMN platform_commission_egp  NUMERIC(10, 2)  NULL,
    ADD COLUMN safety_margin_egp        NUMERIC(10, 2)  NULL,
    ADD COLUMN price_source             VARCHAR(20)     NOT NULL DEFAULT 'system';

-- Spatial index for corridor overlap queries (Stage 1 bounding box + Stage 2 overlap)
CREATE INDEX idx_rides_route_geometry
    ON rides USING GIST (route_geometry);

-- Composite index for Stage 1 time-window + status filter
CREATE INDEX idx_rides_departure_status
    ON rides (departure_datetime, status)
    WHERE status = 'scheduled';
```

**Notes**:
- `route_geometry` is `NULL` for Phase 4 legacy rides. The Stage 1 candidate query filters `route_geometry IS NOT NULL` to exclude them.
- `price_source` is always `'system'` for rides created from Phase 5 onwards. Legacy Phase 4 rides have `NULL` (migration default) but are already excluded by the geometry filter.
- `fuel_cost_egp`, `platform_commission_egp`, `safety_margin_egp` are persisted at ride creation time using the `pricing_config` values active at that moment.

---

## Pydantic Models (`app/models/route.py`)

```python
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Shared primitives ─────────────────────────────────────────────────────────

class GeoPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


# ── Route path calculation ────────────────────────────────────────────────────

class RouteGeometry(BaseModel):
    distance_km: float
    duration_minutes: int
    geojson_linestring: dict          # raw GeoJSON for PostGIS storage
    is_routable: bool


# ── Compatibility assessment (transient — never persisted) ────────────────────

class CompatibilityResult(BaseModel):
    overlap_pct: float                # 0–100
    pickup_walk_m: float              # metres
    dropoff_walk_m: float             # metres
    detour_km: float
    detour_minutes: int
    is_compatible: bool               # passes all standard thresholds

    premium_pickup_available: bool
    premium_pickup_detour_km: float
    premium_pickup_fee_egp: Optional[float] = None

    premium_dropoff_available: bool
    premium_dropoff_detour_km: float
    premium_dropoff_fee_egp: Optional[float] = None


# ── Candidate generation ──────────────────────────────────────────────────────

class RideCandidate(BaseModel):
    ride_id: UUID
    driver_id: UUID
    departure_time: datetime
    available_seats: int
    price_per_seat_egp: float
    candidate_type: str               # 'standard' | 'premium'
    compatibility: CompatibilityResult


class CandidateSearchRequest(BaseModel):
    origin: GeoPoint
    destination: GeoPoint
    departure_time: datetime


class CandidateListResponse(BaseModel):
    standard: list[RideCandidate]     # sorted by overlap_pct desc
    premium: list[RideCandidate]      # sorted by total_premium_fee asc
    total_count: int


# ── Fare calculation ──────────────────────────────────────────────────────────

class FareEstimateRequest(BaseModel):
    origin: GeoPoint
    destination: GeoPoint
    seat_count: int = Field(..., ge=1, le=8)


class FareEstimateResponse(BaseModel):
    distance_km: float
    fuel_price_per_litre_egp: float
    fuel_cost_egp: float
    platform_commission_egp: float    # always fuel_cost × 0.20
    safety_margin_egp: float
    seat_count: int
    per_seat_price_egp: float         # rounded to nearest EGP
    total_collected_egp: float        # per_seat_price × seat_count


# ── Phase 9 AI feature contract (internal endpoint) ──────────────────────────

class CompatibilityFeaturesRequest(BaseModel):
    ride_id: UUID
    passenger_origin: GeoPoint
    passenger_destination: GeoPoint
    requested_departure_time: datetime


class CompatibilityFeatures(BaseModel):
    ride_id: UUID
    overlap_pct: float
    pickup_walk_m: float
    dropoff_walk_m: float
    detour_km: float
    detour_minutes: int
    passenger_route_km: float
    driver_route_km: float
    available_seats: int
    departure_delta_minutes: int      # abs(driver_departure - requested_departure) in minutes
    price_per_seat_egp: float
    is_compatible: bool
    premium_pickup_available: bool
    premium_dropoff_available: bool
```

---

## Entity Relationships

```text
pricing_config (singleton)
  └── read by: pricing_service, route_service, candidate_service
       at startup + every 30s refresh

rides (existing, extended)
  ├── route_geometry          ← written at ride creation (Phase 5+)
  ├── route_distance_km       ← written at ride creation (Phase 5+)
  ├── route_duration_minutes  ← written at ride creation (Phase 5+)
  ├── fuel_cost_egp           ← written at ride creation (Phase 5+)
  ├── platform_commission_egp ← written at ride creation (Phase 5+)
  ├── safety_margin_egp       ← written at ride creation (Phase 5+)
  └── price_source            ← 'system' for all Phase 5+ rides

CompatibilityResult (transient)
  └── computed per request, attached to RideCandidate in response
      never written to DB

FareEstimateResponse (transient)
  └── computed per request, returned to driver
      breakdown values are also persisted to rides row at creation
```

---

## Invariants

- `pricing_config` always has exactly one row. Application code reads with `LIMIT 1`; no `WHERE` needed.
- A ride with `route_geometry IS NULL` is treated as a Phase 4 legacy ride and excluded from all candidate queries.
- `price_source = 'system'` for all rides created from Phase 5 onwards. Driver cannot set price via API.
- `platform_commission_egp` is always `fuel_cost_egp × 0.20`. This is recomputed at query time if needed for audit; the stored value is for convenience and transparency.
- `per_seat_price_egp` is `round((fuel_cost + commission + safety_margin) / seat_count)` using Python's `round()` to nearest integer EGP.
- The `FUEL_EFFICIENCY_KM_PER_L = 13.0` constant is defined once in `pricing_service.py` and referenced nowhere else. It is not configurable.
- The `PLATFORM_COMMISSION_RATE = 0.20` constant is defined once in `pricing_service.py` and is not configurable.
