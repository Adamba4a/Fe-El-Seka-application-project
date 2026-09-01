-- Spec 027: Recurring Rides
-- New recurring_ride_definitions table + rides.recurring_ride_definition_id FK.

-- ─────────────────────────────────────────────────────────────────────────────
-- ENUMS
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TYPE recurring_definition_status AS ENUM ('active', 'ended');

-- ─────────────────────────────────────────────────────────────────────────────
-- RECURRING RIDE DEFINITIONS
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE public.recurring_ride_definitions (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  driver_id                UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
  vehicle_id               UUID NOT NULL REFERENCES public.vehicles(id) ON DELETE RESTRICT,

  origin_coordinates       geography(Point, 4326) NOT NULL,
  origin_address           TEXT NOT NULL,

  destination_coordinates  geography(Point, 4326) NOT NULL,
  destination_address      TEXT NOT NULL,

  departure_time           TIME NOT NULL,
  weekdays                 SMALLINT[] NOT NULL CHECK (array_length(weekdays, 1) > 0),

  total_seats              SMALLINT NOT NULL CHECK (total_seats >= 1),
  price_per_seat           NUMERIC(10, 2) NOT NULL CHECK (price_per_seat > 0),

  notes                    TEXT,
  status                   recurring_definition_status NOT NULL DEFAULT 'active',

  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.recurring_ride_definitions ENABLE ROW LEVEL SECURITY;

CREATE INDEX idx_recurring_definitions_driver_status
  ON public.recurring_ride_definitions (driver_id, status);

CREATE POLICY "driver_read_own_recurring_definitions" ON public.recurring_ride_definitions
  FOR SELECT USING (driver_id = auth.uid());

-- ─────────────────────────────────────────────────────────────────────────────
-- RIDES: link generated day instances back to their definition
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.rides
  ADD COLUMN recurring_ride_definition_id UUID
    REFERENCES public.recurring_ride_definitions(id) ON DELETE SET NULL;

CREATE INDEX idx_rides_recurring_definition_id
  ON public.rides (recurring_ride_definition_id)
  WHERE recurring_ride_definition_id IS NOT NULL;

-- Idempotency guard for the generation loop (NFR-001): at most one generated
-- instance per definition per calendar date. departure_datetime::date is
-- STABLE (not IMMUTABLE) because the cast depends on the session timezone, so
-- indexing on it directly is rejected — wrap it in an IMMUTABLE function that
-- pins the conversion to UTC (the timezone every departure_datetime is stored
-- and reasoned about in throughout this codebase).
CREATE OR REPLACE FUNCTION public.utc_date(ts TIMESTAMPTZ)
RETURNS DATE
LANGUAGE sql
IMMUTABLE
AS $$ SELECT (ts AT TIME ZONE 'UTC')::date $$;

CREATE UNIQUE INDEX uq_rides_recurring_instance_per_date
  ON public.rides (recurring_ride_definition_id, public.utc_date(departure_datetime))
  WHERE recurring_ride_definition_id IS NOT NULL;
