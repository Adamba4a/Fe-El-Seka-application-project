# Data Model: Real-Time Transportation

**Feature**: `010-realtime-transportation` | **Date**: 2026-06-28

Migrations delivered in this phase:
- `supabase/migrations/20260628000001_phase7_device_tokens.sql`
- `supabase/migrations/20260628000002_phase7_notification_events.sql`
- `supabase/migrations/20260628000003_phase7_driver_locations.sql`
- `supabase/migrations/20260628000004_phase7_rides_lifecycle.sql`

---

## New Tables

### `user_device_tokens`

Stores FCM registration tokens for push notification delivery. One row per unique token; a user may have multiple rows (multiple devices).

```sql
CREATE TABLE public.user_device_tokens (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    token         TEXT NOT NULL,
    platform      TEXT NOT NULL CHECK (platform IN ('web', 'android', 'ios')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_device_token UNIQUE (token)
);
```

**Upsert pattern** (FR-003 — update `last_seen_at` and re-associate if token exists):
```sql
INSERT INTO user_device_tokens (user_id, token, platform)
VALUES ($1, $2, $3)
ON CONFLICT (token) DO UPDATE SET
    user_id      = EXCLUDED.user_id,
    last_seen_at = now();
```

**Indexes**:
```sql
-- Dispatcher lookup: all tokens for a recipient user
CREATE INDEX idx_device_tokens_user_id
    ON public.user_device_tokens (user_id);
```

**RLS Policies**:
```sql
ALTER TABLE public.user_device_tokens ENABLE ROW LEVEL SECURITY;

-- Users manage their own tokens
CREATE POLICY "user_manage_own_tokens" ON public.user_device_tokens
    FOR ALL USING (user_id = auth.uid());
-- Service role: full access (backend dispatcher reads all tokens for a given user_id)
```

---

### `notification_events`

FCM push notification dispatch queue. One row per notification event; the dispatcher polls for `pending` rows, dispatches FCM, and updates status. This is a new table created in Phase 7 — it is NOT the `email_notifications` table used by Phase 6 (see `research.md` §2).

```sql
CREATE TYPE notification_event_type AS ENUM (
    'booking_received',
    'booking_confirmed',
    'booking_rejected',
    'booking_cancelled',
    'booking_expired',
    'ride_cancelled',
    'ride_started',
    'ride_completed'
);

CREATE TYPE notification_event_status AS ENUM (
    'pending',
    'dispatched',
    'failed'
);

CREATE TABLE public.notification_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    event_type        notification_event_type NOT NULL,
    payload           JSONB NOT NULL DEFAULT '{}',
    status            notification_event_status NOT NULL DEFAULT 'pending',
    retry_count       SMALLINT NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dispatched_at     TIMESTAMPTZ
);
```

**payload JSONB structure** (per event type, for FR-011 FCM data object):

```json
// booking_received (to driver)
{
  "ride_id": "uuid",
  "booking_id": "uuid",
  "passenger_name": "Sara Ahmed",
  "departure_datetime": "2026-07-01T08:00:00Z",
  "deep_link": "/(driver)/rides/{ride_id}/bookings"
}

// booking_confirmed (to passenger)
{
  "ride_id": "uuid",
  "booking_id": "uuid",
  "driver_name": "Ahmed Hassan",
  "departure_datetime": "2026-07-01T08:00:00Z",
  "deep_link": "/(passenger)/bookings/{booking_id}"
}

// booking_rejected / booking_expired (to passenger)
{
  "ride_id": "uuid",
  "booking_id": "uuid",
  "departure_datetime": "2026-07-01T08:00:00Z",
  "deep_link": "/(passenger)/rides"
}

// booking_cancelled (to non-cancelling party)
{
  "ride_id": "uuid",
  "booking_id": "uuid",
  "cancelled_by": "passenger" | "driver",
  "deep_link": "/(passenger)/bookings/{booking_id}"   // or /(driver)/rides/{ride_id}/bookings
}

// ride_cancelled (to each confirmed passenger)
{
  "ride_id": "uuid",
  "departure_datetime": "2026-07-01T08:00:00Z",
  "deep_link": "/(passenger)/bookings/{booking_id}"
}

// ride_started (to each confirmed passenger)
{
  "ride_id": "uuid",
  "booking_id": "uuid",
  "deep_link": "/(passenger)/rides/{ride_id}/tracking"
}

// ride_completed (to each completed booking passenger)
{
  "ride_id": "uuid",
  "booking_id": "uuid",
  "deep_link": "/(passenger)/bookings/{booking_id}"
}
```

**Indexes**:
```sql
-- Dispatcher polling query
CREATE INDEX idx_notification_events_pending
    ON public.notification_events (created_at ASC)
    WHERE status = 'pending';
```

**RLS Policies**:
```sql
ALTER TABLE public.notification_events ENABLE ROW LEVEL SECURITY;

-- Recipients read their own events
CREATE POLICY "user_read_own_events" ON public.notification_events
    FOR SELECT USING (recipient_user_id = auth.uid());

-- No client INSERT/UPDATE: backend service role only
```

---

### `driver_locations`

Current GPS position of a driver during an active ride. One row per in-progress ride, updated in place on each driver report.

```sql
CREATE TABLE public.driver_locations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ride_id          UUID NOT NULL REFERENCES public.rides(id) ON DELETE CASCADE,
    driver_id        UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    location         geometry(Point, 4326) NOT NULL,
    bearing          SMALLINT,                          -- nullable: degrees 0–359; null when stationary
    speed_kmh        DECIMAL(6, 2),                     -- nullable: stored for future analytics; NOT returned in GET response
    client_timestamp TIMESTAMPTZ NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_driver_location_ride UNIQUE (ride_id)
);
```

**Frontend Realtime compatibility**: The Supabase Realtime payload for `driver_locations` carries the raw row, which includes the PostGIS binary `location` column — not directly usable as lat/lng in JavaScript. A database view exposes extracted coordinates:

```sql
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
```

**Note**: The `GET /rides/{ride_id}/location` API endpoint returns lat/lng extracted via `ST_Y`/`ST_X` directly from the raw table query — the view is available for frontend Realtime consumption if the client subscribes to the view rather than the base table. Alternatively, the frontend can subscribe to the base table and call the GET endpoint to refresh position after each Realtime event (simpler approach for MVP).

**Indexes**:
```sql
-- Location read by ride_id (GET endpoint + Realtime filter)
CREATE INDEX idx_driver_locations_ride_id
    ON public.driver_locations (ride_id);
```

**RLS Policies**:
```sql
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
-- Service role: full access (backend upsert uses service role connection)
```

---

## Extended Tables

### `rides` (extension)

Two new nullable timestamp columns added via a non-breaking migration. No existing Phase 4 or Phase 6 code is broken — columns are nullable and existing queries are unaffected.

```sql
ALTER TABLE public.rides
    ADD COLUMN IF NOT EXISTS started_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
```

**Impact on `ride_service.py`**: The `_RIDE_COLS` constant must be extended to include `started_at, completed_at` so the `RETURNING` clause in start/complete operations returns these fields. The `_to_response()` function and `RideResponse` Pydantic model must also include these new fields (nullable).

**Updated SQL in `start_ride()`**:
```sql
UPDATE rides
SET status = 'in_progress', started_at = now(), updated_at = now()
WHERE id = $1
RETURNING {_RIDE_COLS}
```

**Updated SQL in `complete_ride()`**:
```sql
UPDATE rides
SET status = 'completed', completed_at = now(), updated_at = now()
WHERE id = $1
RETURNING {_RIDE_COLS}
```

### Realtime publication additions

```sql
-- In migration 20260628000004:
ALTER PUBLICATION supabase_realtime ADD TABLE public.bookings;
ALTER PUBLICATION supabase_realtime ADD TABLE public.driver_locations;
```

---

## Existing Tables Referenced (no schema change)

### `bookings` (read + insert from Phase 7)

| Column | Phase 7 usage |
|--------|--------------|
| `ride_id` | Used to find confirmed passengers when inserting `ride_started` / `ride_completed` notification events |
| `passenger_id` | `recipient_user_id` for `ride_started`, `ride_completed`, `booking_received` notification events |
| `status` | Filtered to `confirmed` when inserting ride lifecycle notification events; `pending` when checking overdue bookings for driver reminder |
| `created_at` | Compared against `NOW() - INTERVAL '2 hours'` in driver reminder sweep |

### `profiles` (read-only)

`display_name` fetched for notification payload construction (passenger name in `booking_received`, driver name in `booking_confirmed`).

---

## State Transition Reference

### Ride lifecycle (Phase 7 additions to Phase 4 state machine)

```
Ride state machine (additions only):

  scheduled ─── driver taps "Start Ride" ──────────────────────────────► in_progress
                  sets started_at
                  inserts notification_events(ride_started) for each confirmed passenger

  in_progress ── driver taps "Complete Ride" ─────────────────────────► completed
                  sets completed_at
                  Phase 6 cascade: confirmed bookings → completed
                  inserts notification_events(ride_completed) for each completed booking's passenger

  in_progress ── location POST ────────────────────────────────────────► (upsert driver_locations)
                  Supabase Realtime broadcasts UPDATE to subscribed confirmed passengers
```

### Notification event lifecycle

```
notification_events status:

  pending ─── dispatcher picks up, FCM succeeds ──────────────────────► dispatched
  pending ─── dispatcher picks up, FCM fails, retry_count < 3 ────────► pending (retry_count + 1)
  pending ─── dispatcher picks up, FCM fails, retry_count = 3 ────────► failed
  dispatched / failed ─── (terminal; dispatcher skips these rows)
```
