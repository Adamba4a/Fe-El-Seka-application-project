-- Phase 6: Passenger Experience — bookings schema
-- Creates: booking_status, booking_cancelled_by, booking_event_type, booking_actor_role enums
--          bookings table, booking_audit_log table
-- Extends: email_notifications with payload JSONB column

-- ── Enums ──────────────────────────────────────────────────────────────────

CREATE TYPE booking_status AS ENUM ('pending', 'confirmed', 'cancelled', 'completed');
CREATE TYPE booking_cancelled_by AS ENUM ('passenger', 'driver', 'system');
CREATE TYPE booking_event_type AS ENUM ('created', 'confirmed', 'rejected', 'cancelled', 'expired', 'completed');
CREATE TYPE booking_actor_role AS ENUM ('passenger', 'driver', 'system');

-- ── bookings ────────────────────────────────────────────────────────────────

CREATE TABLE public.bookings (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ride_id                   UUID NOT NULL REFERENCES public.rides(id) ON DELETE RESTRICT,
    passenger_id              UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,

    status                    booking_status NOT NULL DEFAULT 'pending',

    per_seat_price            NUMERIC(10, 2) NOT NULL,
    total_price               NUMERIC(10, 2) NOT NULL,

    -- PostGIS geometry: boarding and alighting points on the driver's route
    passenger_pickup_point    geometry(Point, 4326) NOT NULL,
    passenger_dropoff_point   geometry(Point, 4326) NOT NULL,

    -- Premium options (null when not requested)
    premium_pickup_requested  BOOLEAN NOT NULL DEFAULT FALSE,
    premium_dropoff_requested BOOLEAN NOT NULL DEFAULT FALSE,
    premium_pickup_fee        NUMERIC(10, 2),
    premium_dropoff_fee       NUMERIC(10, 2),

    -- Cancellation metadata
    cancelled_by              booking_cancelled_by,
    cancellation_reason       TEXT,
    late_cancellation         BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at              TIMESTAMPTZ,
    cancelled_at              TIMESTAMPTZ
);

-- One active booking per passenger per ride
CREATE UNIQUE INDEX idx_bookings_active_unique
    ON public.bookings (ride_id, passenger_id)
    WHERE status IN ('pending', 'confirmed');

-- Passenger "My Bookings" query
CREATE INDEX idx_bookings_passenger_status
    ON public.bookings (passenger_id, status, created_at DESC);

-- Driver booking queue query
CREATE INDEX idx_bookings_ride_status
    ON public.bookings (ride_id, status, created_at ASC);

-- Expiry sweep query (pending bookings only)
CREATE INDEX idx_bookings_expiry
    ON public.bookings (created_at ASC)
    WHERE status = 'pending';

-- RLS
ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "passenger_select_own_bookings" ON public.bookings
    FOR SELECT USING (passenger_id = auth.uid());

CREATE POLICY "passenger_cancel_own_bookings" ON public.bookings
    FOR UPDATE USING (passenger_id = auth.uid())
    WITH CHECK (status = 'cancelled' AND cancelled_by = 'passenger');

CREATE POLICY "driver_select_ride_bookings" ON public.bookings
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.rides
            WHERE rides.id = bookings.ride_id
              AND rides.driver_id = auth.uid()
        )
    );

CREATE POLICY "driver_update_ride_bookings" ON public.bookings
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.rides
            WHERE rides.id = bookings.ride_id
              AND rides.driver_id = auth.uid()
        )
    );

-- ── booking_audit_log ───────────────────────────────────────────────────────

CREATE TABLE public.booking_audit_log (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id       UUID NOT NULL REFERENCES public.bookings(id) ON DELETE RESTRICT,
    event_type       booking_event_type NOT NULL,
    actor_id         UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    actor_role       booking_actor_role NOT NULL,
    previous_status  booking_status,
    new_status       booking_status NOT NULL,
    metadata         JSONB NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_booking_audit_booking_id
    ON public.booking_audit_log (booking_id, created_at ASC);

ALTER TABLE public.booking_audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "passenger_read_own_booking_audit" ON public.booking_audit_log
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.bookings
            WHERE bookings.id = booking_audit_log.booking_id
              AND bookings.passenger_id = auth.uid()
        )
    );

CREATE POLICY "driver_read_ride_booking_audit" ON public.booking_audit_log
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.bookings b
            JOIN public.rides r ON r.id = b.ride_id
            WHERE b.id = booking_audit_log.booking_id
              AND r.driver_id = auth.uid()
        )
    );

-- ── email_notifications extension ──────────────────────────────────────────

ALTER TABLE public.email_notifications
    ADD COLUMN IF NOT EXISTS payload JSONB NOT NULL DEFAULT '{}';
