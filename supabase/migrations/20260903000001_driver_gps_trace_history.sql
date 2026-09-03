-- Feature 029: Driver GPS Trace History
-- Creates: driver_location_history table (append-only, one row per GPS ping)
-- Internal ML telemetry, not surfaced in any UI — RLS enabled, no public policies
-- (service-role backend access only). See specs/029-driver-gps-trace-history/data-model.md.
-- Additive only — does not modify driver_locations or driver_locations_view.

CREATE TABLE public.driver_location_history (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ride_id      UUID NOT NULL REFERENCES public.rides(id) ON DELETE CASCADE,
    driver_id    UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    location     geometry(Point, 4326) NOT NULL,
    recorded_at  TIMESTAMPTZ NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Reconstruct one ride's full trace in order (FR-006)
CREATE INDEX idx_driver_location_history_ride_recorded
    ON public.driver_location_history (ride_id, recorded_at);

-- Retention job's DELETE ... WHERE recorded_at < now() - interval '30 days' (FR-004/FR-005)
CREATE INDEX idx_driver_location_history_recorded_at
    ON public.driver_location_history (recorded_at);

ALTER TABLE public.driver_location_history ENABLE ROW LEVEL SECURITY;
-- No policies: service-role only, same posture as match_events/search_sessions (013).
