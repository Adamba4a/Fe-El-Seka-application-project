-- Phase 7: Real-Time Transportation — live driver location
-- Creates: driver_locations table (one row per active ride, upserted in place),
--          driver_locations_view (exposes lat/lng as floats for Realtime consumers)

CREATE TABLE public.driver_locations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ride_id          UUID NOT NULL REFERENCES public.rides(id) ON DELETE CASCADE,
    driver_id        UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    location         geometry(Point, 4326) NOT NULL,
    bearing          SMALLINT,           -- degrees 0–359; NULL when stationary / unavailable
    speed_kmh        DECIMAL(6, 2),      -- stored for future analytics; NOT returned in GET responses
    client_timestamp TIMESTAMPTZ NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_driver_location_ride UNIQUE (ride_id)
);

-- Location read by ride_id (GET endpoint + Realtime filter)
CREATE INDEX idx_driver_locations_ride_id
    ON public.driver_locations (ride_id);

ALTER TABLE public.driver_locations ENABLE ROW LEVEL SECURITY;

-- Assigned driver: read and write their own location row
CREATE POLICY "driver_manage_own_location" ON public.driver_locations
    FOR ALL USING (driver_id = auth.uid());

-- Confirmed passengers: read location for rides they have a confirmed booking on
CREATE POLICY "confirmed_passenger_read_location" ON public.driver_locations
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.bookings
            WHERE bookings.ride_id = driver_locations.ride_id
              AND bookings.passenger_id = auth.uid()
              AND bookings.status = 'confirmed'
        )
    );

-- View exposes lat/lng as floats so Realtime payload consumers don't get raw PostGIS binary.
-- Frontend can subscribe to driver_locations_view for usable coordinate values.
CREATE VIEW public.driver_locations_view AS
SELECT
    id,
    ride_id,
    driver_id,
    ST_Y(location::geometry) AS lat,
    ST_X(location::geometry) AS lng,
    bearing,
    client_timestamp,
    updated_at
FROM public.driver_locations;
