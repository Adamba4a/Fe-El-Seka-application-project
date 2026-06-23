# Data Model: Passenger Experience

**Feature**: `009-passenger-experience` | **Date**: 2026-06-24

Migration file: `supabase/migrations/20260624000001_phase6_bookings.sql`

---

## New Tables

### `bookings`

Primary transactional record linking a passenger to a driver ride.

```sql
CREATE TYPE booking_status AS ENUM ('pending', 'confirmed', 'cancelled', 'completed');
CREATE TYPE booking_cancelled_by AS ENUM ('passenger', 'driver', 'system');

CREATE TABLE public.bookings (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ride_id                  UUID NOT NULL REFERENCES public.rides(id) ON DELETE RESTRICT,
    passenger_id             UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,

    status                   booking_status NOT NULL DEFAULT 'pending',

    per_seat_price           NUMERIC(10, 2) NOT NULL,
    total_price              NUMERIC(10, 2) NOT NULL,

    -- PostGIS geometry: boarding and alighting points on the driver's route
    passenger_pickup_point   geometry(Point, 4326) NOT NULL,
    passenger_dropoff_point  geometry(Point, 4326) NOT NULL,

    -- Premium options (null when not requested)
    premium_pickup_requested  BOOLEAN NOT NULL DEFAULT FALSE,
    premium_dropoff_requested BOOLEAN NOT NULL DEFAULT FALSE,
    premium_pickup_fee        NUMERIC(10, 2),
    premium_dropoff_fee       NUMERIC(10, 2),

    -- Cancellation metadata
    cancelled_by             booking_cancelled_by,
    cancellation_reason      TEXT,
    late_cancellation        BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at             TIMESTAMPTZ,
    cancelled_at             TIMESTAMPTZ
);
```

**Constraints**:
- Only one active booking per passenger per ride: partial unique index on `(ride_id, passenger_id)` where `status IN ('pending', 'confirmed')`.
- `per_seat_price` and `total_price` are locked at booking creation from the ride's `price_per_seat` plus any applicable premium fees. They do not update if the ride price changes.
- `cancelled_by` and `cancellation_reason` are NULL while `status` is `pending` or `confirmed`.

**Indexes**:

```sql
-- Enforce one active booking per passenger per ride
CREATE UNIQUE INDEX idx_bookings_active_unique
    ON public.bookings (ride_id, passenger_id)
    WHERE status IN ('pending', 'confirmed');

-- Passenger "My Bookings" query
CREATE INDEX idx_bookings_passenger_status
    ON public.bookings (passenger_id, status, created_at DESC);

-- Driver booking queue query
CREATE INDEX idx_bookings_ride_status
    ON public.bookings (ride_id, status, created_at ASC);

-- Expiry sweep query
CREATE INDEX idx_bookings_expiry
    ON public.bookings (created_at ASC)
    WHERE status = 'pending';
```

**RLS Policies**:

```sql
ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;

-- Passengers: read and cancel their own bookings
CREATE POLICY "passenger_select_own_bookings" ON public.bookings
    FOR SELECT USING (passenger_id = auth.uid());

CREATE POLICY "passenger_cancel_own_bookings" ON public.bookings
    FOR UPDATE USING (passenger_id = auth.uid())
    WITH CHECK (status = 'cancelled' AND cancelled_by = 'passenger');

-- Drivers: read and respond to bookings on their rides
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

-- Service role: full access (backend uses service role for atomic operations)
-- Handled by Supabase default service_role bypass.
```

---

### `booking_audit_log`

Immutable append-only record of every booking state transition.

```sql
CREATE TYPE booking_event_type AS ENUM (
    'created', 'confirmed', 'rejected', 'cancelled', 'expired', 'completed'
);
CREATE TYPE booking_actor_role AS ENUM ('passenger', 'driver', 'system');

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
```

**Append-only enforcement**:
- No `UPDATE` or `DELETE` policies granted to any application role.
- Backend inserts via service role only.

**Indexes**:

```sql
CREATE INDEX idx_booking_audit_booking_id
    ON public.booking_audit_log (booking_id, created_at ASC);
```

**RLS Policies**:

```sql
ALTER TABLE public.booking_audit_log ENABLE ROW LEVEL SECURITY;

-- Passengers: read audit log for their own bookings
CREATE POLICY "passenger_read_own_booking_audit" ON public.booking_audit_log
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.bookings
            WHERE bookings.id = booking_audit_log.booking_id
              AND bookings.passenger_id = auth.uid()
        )
    );

-- Drivers: read audit log for bookings on their rides
CREATE POLICY "driver_read_ride_booking_audit" ON public.booking_audit_log
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.bookings b
            JOIN public.rides r ON r.id = b.ride_id
            WHERE b.id = booking_audit_log.booking_id
              AND r.driver_id = auth.uid()
        )
    );

-- No UPDATE or DELETE policies — table is append-only.
```

---

## Extended Tables

### `email_notifications` (extension)

The existing `email_notifications` table is extended with a `payload` JSONB column to carry structured booking event data (booking ID, ride departure time, driver/passenger name). New `notification_type` values are introduced without altering the existing `notification_type TEXT` column type (it is unconstrained text, not an enum).

```sql
-- Migration: add payload column
ALTER TABLE public.email_notifications
    ADD COLUMN IF NOT EXISTS payload JSONB NOT NULL DEFAULT '{}';
```

**New `notification_type` values** used by Phase 6 (no migration change required for the column itself):
- `booking_confirmed`
- `booking_rejected`
- `booking_cancelled_by_passenger`
- `booking_cancelled_by_driver`
- `booking_expired`

**Payload structure** (per event type):

```json
// booking_confirmed
{
  "booking_id": "uuid",
  "ride_id": "uuid",
  "driver_name": "Ahmed Hassan",
  "departure_datetime": "2026-07-01T08:00:00Z",
  "pickup_address": "Nasr City, Cairo",
  "per_seat_price": "45.00"
}

// booking_rejected / booking_expired
{
  "booking_id": "uuid",
  "ride_id": "uuid",
  "departure_datetime": "2026-07-01T08:00:00Z"
}

// booking_cancelled_by_driver
{
  "booking_id": "uuid",
  "ride_id": "uuid",
  "cancellation_reason": "optional text"
}
```

---

## Existing Tables Referenced (no schema change)

### `rides` (read + `booked_seats` write)

| Column | Type | Phase 6 usage |
|--------|------|---------------|
| `id` | UUID | Foreign key on `bookings.ride_id` |
| `driver_id` | UUID | Authorization — driver owns the ride |
| `booked_seats` | SMALLINT | **Incremented** on booking creation; **decremented** on cancellation/rejection/expiry. DO NOT write `available_seats` (it is generated). |
| `available_seats` | SMALLINT GENERATED | Read-only; equals `total_seats − booked_seats`. Used in candidate search. |
| `status` | ride_status | Must be `'scheduled'` at booking creation. `'completed'` triggers booking completion cascade. |
| `price_per_seat` | NUMERIC(10,2) | Locked into `bookings.per_seat_price` at booking creation time. |
| `route_geometry` | geometry(LINESTRING) | Rendered on ride detail map screen. |
| `departure_datetime` | TIMESTAMPTZ | Shown on search results, detail, and booking screens. |

### `profiles` (read-only)

Used to fetch `display_name`, `avatar_url`, and `verification_status` for ride detail and booking screens. No writes.

---

## State Transition Reference

```
Booking lifecycle:

  [created] ──────────────────────────────────────────────────────► pending
  pending ─── driver confirms ─────────────────────────────────────► confirmed
  pending ─── driver rejects ──────────────────────────────────────► cancelled (cancelled_by = driver)
  pending ─── passenger cancels ───────────────────────────────────► cancelled (cancelled_by = passenger)
  pending ─── 24h expires (system) ────────────────────────────────► cancelled (cancelled_by = system)
  confirmed ── passenger cancels ──────────────────────────────────► cancelled (cancelled_by = passenger)
  confirmed ── driver cancels individual booking ──────────────────► cancelled (cancelled_by = driver)
  confirmed ── ride marked completed (cascade) ────────────────────► completed
  cancelled ─── (terminal, no further transitions)
  completed ─── (terminal, no further transitions)
```

Every transition produces exactly one `booking_audit_log` row.
Every transition that cancels a booking (except `completed`) restores 1 to `rides.booked_seats`.
