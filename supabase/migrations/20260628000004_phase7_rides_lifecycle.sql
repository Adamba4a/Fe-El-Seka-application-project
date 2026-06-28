-- Phase 7: Real-Time Transportation — ride lifecycle timestamps + Realtime publication
-- Extends: rides table with started_at and completed_at nullable timestamp columns
-- Adds: bookings and driver_locations to supabase_realtime publication

ALTER TABLE public.rides
    ADD COLUMN IF NOT EXISTS started_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

-- Enable Supabase Realtime change events for booking status updates
-- and driver location updates (required for in-app real-time features).
-- NOTE: Supabase Realtime Authorization must also be enabled manually in
-- the project dashboard (Database → Replication → Realtime Authorization)
-- so that RLS policies filter change events per authenticated subscriber.
ALTER PUBLICATION supabase_realtime ADD TABLE public.bookings;
ALTER PUBLICATION supabase_realtime ADD TABLE public.driver_locations;
