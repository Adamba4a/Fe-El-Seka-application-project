-- Phase 4: Ride Management
-- Drops the Phase 1 stub rides/bookings tables and replaces with the full schema.

-- ─────────────────────────────────────────────────────────────────────────────
-- CLEAN UP PHASE 1 STUBS
-- ─────────────────────────────────────────────────────────────────────────────

DROP TABLE IF EXISTS public.bookings CASCADE;
DROP TABLE IF EXISTS public.rides CASCADE;

-- ─────────────────────────────────────────────────────────────────────────────
-- ENUMS
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TYPE ride_status AS ENUM ('scheduled', 'in_progress', 'completed', 'cancelled');
CREATE TYPE ride_action AS ENUM ('created', 'edited', 'cancelled', 'started', 'completed');
CREATE TYPE email_notification_status AS ENUM ('pending', 'sent', 'failed', 'failed_permanent');

-- ─────────────────────────────────────────────────────────────────────────────
-- RIDES
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE public.rides (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  driver_id                UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
  vehicle_id               UUID NOT NULL REFERENCES public.vehicles(id) ON DELETE RESTRICT,

  origin_coordinates       geography(Point, 4326) NOT NULL,
  origin_address           TEXT NOT NULL,

  destination_coordinates  geography(Point, 4326) NOT NULL,
  destination_address      TEXT NOT NULL,

  departure_datetime       TIMESTAMPTZ NOT NULL,

  total_seats              SMALLINT NOT NULL CHECK (total_seats >= 1),
  booked_seats             SMALLINT NOT NULL DEFAULT 0 CHECK (booked_seats >= 0),
  available_seats          SMALLINT GENERATED ALWAYS AS (total_seats - booked_seats) STORED,

  price_per_seat           NUMERIC(10, 2) NOT NULL CHECK (price_per_seat > 0),

  status                   ride_status NOT NULL DEFAULT 'scheduled',
  cancellation_reason      TEXT,
  cancellation_source      TEXT CHECK (cancellation_source IN ('driver', 'system')),

  notes                    TEXT,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.rides ENABLE ROW LEVEL SECURITY;

CREATE INDEX idx_rides_driver_status      ON public.rides (driver_id, status);
CREATE INDEX idx_rides_driver_departure   ON public.rides (driver_id, departure_datetime);
CREATE INDEX idx_rides_origin_geo         ON public.rides USING GIST (origin_coordinates);
CREATE INDEX idx_rides_destination_geo    ON public.rides USING GIST (destination_coordinates);

CREATE POLICY "driver_read_own_rides" ON public.rides
  FOR SELECT USING (driver_id = auth.uid());

-- ─────────────────────────────────────────────────────────────────────────────
-- RIDE HISTORY LOGS
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE public.ride_history_logs (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ride_id        UUID NOT NULL REFERENCES public.rides(id) ON DELETE RESTRICT,
  actor_id       UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  action         ride_action NOT NULL,
  changed_fields JSONB,
  reason         TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.ride_history_logs ENABLE ROW LEVEL SECURITY;

CREATE INDEX idx_ride_history_ride_id ON public.ride_history_logs (ride_id, created_at);

CREATE POLICY "driver_read_own_ride_history" ON public.ride_history_logs
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.rides
      WHERE rides.id = ride_id AND rides.driver_id = auth.uid()
    )
  );

-- ─────────────────────────────────────────────────────────────────────────────
-- EMAIL NOTIFICATIONS
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE public.email_notifications (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ride_id             UUID NOT NULL REFERENCES public.rides(id) ON DELETE RESTRICT,
  passenger_id        UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
  passenger_email     TEXT NOT NULL,
  notification_type   TEXT NOT NULL DEFAULT 'ride_cancelled',
  status              email_notification_status NOT NULL DEFAULT 'pending',
  retry_count         SMALLINT NOT NULL DEFAULT 0,
  last_attempted_at   TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.email_notifications ENABLE ROW LEVEL SECURITY;

CREATE INDEX idx_email_notifications_pending ON public.email_notifications (status, created_at)
  WHERE status IN ('pending', 'failed');
