-- Phase 5: Route Intelligence — Ride Geometry & Fare Breakdown
-- Extends the rides table with OSRM-calculated route data and per-ride fare audit columns.
-- route_geometry is NULL for Phase 4 legacy rides; they are excluded from candidate queries
-- via the "route_geometry IS NOT NULL" filter.

ALTER TABLE public.rides
    ADD COLUMN route_geometry           geometry(LINESTRING, 4326)  NULL,
    ADD COLUMN route_distance_km        NUMERIC(10, 2)              NULL,
    ADD COLUMN route_duration_minutes   INTEGER                     NULL,
    ADD COLUMN fuel_cost_egp            NUMERIC(10, 2)              NULL,
    ADD COLUMN platform_commission_egp  NUMERIC(10, 2)              NULL,
    ADD COLUMN safety_margin_egp        NUMERIC(10, 2)              NULL,
    ADD COLUMN price_source             VARCHAR(20)                 NOT NULL DEFAULT 'legacy';

-- GiST spatial index — required for corridor overlap queries (Stage 1 bounding-box + Stage 2)
CREATE INDEX idx_rides_route_geometry
    ON public.rides USING GIST (route_geometry);

-- Composite partial index — Stage 1 time-window + status filter
CREATE INDEX idx_rides_departure_status
    ON public.rides (departure_datetime, status)
    WHERE status = 'scheduled';
