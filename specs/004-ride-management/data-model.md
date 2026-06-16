# Data Model: Ride Management

**Branch**: `004-ride-management` | **Date**: 2026-06-17

---

## Enumerations

```sql
CREATE TYPE ride_status AS ENUM ('scheduled', 'in_progress', 'completed', 'cancelled');
CREATE TYPE ride_action AS ENUM ('created', 'edited', 'cancelled', 'started', 'completed');
CREATE TYPE email_notification_status AS ENUM ('pending', 'sent', 'failed', 'failed_permanent');
```

---

## Tables

### rides

Central record for every driver-posted trip.

```sql
CREATE TABLE rides (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  driver_id                UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  vehicle_id               UUID NOT NULL REFERENCES vehicles(id) ON DELETE RESTRICT,

  -- Origin: PostGIS geography point + human-readable label from Nominatim reverse geocode
  origin_coordinates       geography(Point, 4326) NOT NULL,
  origin_address           TEXT NOT NULL,

  -- Destination: PostGIS geography point + human-readable label
  destination_coordinates  geography(Point, 4326) NOT NULL,
  destination_address      TEXT NOT NULL,

  departure_datetime       TIMESTAMPTZ NOT NULL,

  -- Seat tracking
  total_seats              SMALLINT NOT NULL CHECK (total_seats >= 1),
  booked_seats             SMALLINT NOT NULL DEFAULT 0 CHECK (booked_seats >= 0),
  available_seats          SMALLINT GENERATED ALWAYS AS (total_seats - booked_seats) STORED,

  -- Pricing (manual entry for this phase; fuel-cost formula deferred to Phase 5)
  price_per_seat           NUMERIC(10, 2) NOT NULL CHECK (price_per_seat > 0),

  -- Status lifecycle
  status                   ride_status NOT NULL DEFAULT 'scheduled',
  cancellation_reason      TEXT,
  cancellation_source      TEXT CHECK (cancellation_source IN ('driver', 'system')),

  notes                    TEXT,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Constraints**:
- `available_seats` is a generated column — always equals `total_seats - booked_seats`; never writable directly.
- `cancellation_reason` and `cancellation_source` are NOT NULL when `status = 'cancelled'` — enforced at the application layer (FastAPI service), not as a DB check, to keep migration simple.
- Origin ≠ destination enforced at application layer (comparing coordinates).
- Departure within 48 hours of creation enforced at application layer.
- Two-hour overlap rule enforced at application layer with advisory lock (see research.md §4).

**Indexes**:
```sql
-- Dashboard query: list a driver's rides filtered by status
CREATE INDEX idx_rides_driver_status ON rides (driver_id, status);

-- Overlap check: find driver's rides near a target departure time
CREATE INDEX idx_rides_driver_departure ON rides (driver_id, departure_datetime);

-- Spatial indexes for Phase 5 proximity/overlap queries (created now, used in Phase 5)
CREATE INDEX idx_rides_origin_geo      ON rides USING GIST (origin_coordinates);
CREATE INDEX idx_rides_destination_geo ON rides USING GIST (destination_coordinates);
```

**RLS policies** (Supabase Row Level Security):
```sql
-- Drivers can read their own rides only
CREATE POLICY "driver_read_own_rides" ON rides FOR SELECT
  USING (driver_id = auth.uid());

-- Service role only for INSERT/UPDATE (all mutations go through FastAPI backend)
-- No direct client INSERT/UPDATE policies — all writes via backend API
```

---

### ride_history_logs

Append-only audit trail for every state change or edit on a ride. Never updated or deleted.

```sql
CREATE TABLE ride_history_logs (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ride_id        UUID NOT NULL REFERENCES rides(id) ON DELETE RESTRICT,
  actor_id       UUID REFERENCES users(id) ON DELETE SET NULL,  -- NULL when system-triggered
  action         ride_action NOT NULL,
  changed_fields JSONB,  -- Only present for 'edited' actions; records field name → {before, after}
  reason         TEXT,   -- Only present for 'cancelled' actions
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Indexes**:
```sql
CREATE INDEX idx_ride_history_ride_id ON ride_history_logs (ride_id, created_at);
```

**RLS policies**:
```sql
-- Drivers can read history for their own rides
CREATE POLICY "driver_read_own_ride_history" ON ride_history_logs FOR SELECT
  USING (
    EXISTS (SELECT 1 FROM rides WHERE rides.id = ride_id AND rides.driver_id = auth.uid())
  );

-- No client INSERT — all history written by backend service role
```

---

### email_notifications

Persistent queue for best-effort cancellation emails. Enables background retry without losing state.

```sql
CREATE TABLE email_notifications (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ride_id             UUID NOT NULL REFERENCES rides(id) ON DELETE RESTRICT,
  passenger_id        UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  passenger_email     TEXT NOT NULL,
  notification_type   TEXT NOT NULL DEFAULT 'ride_cancelled',
  status              email_notification_status NOT NULL DEFAULT 'pending',
  retry_count         SMALLINT NOT NULL DEFAULT 0,
  last_attempted_at   TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Indexes**:
```sql
CREATE INDEX idx_email_notifications_pending ON email_notifications (status, created_at)
  WHERE status IN ('pending', 'failed');
```

**RLS policies**: Service role only — no client access.

---

## Entity Relationships

```
users (Phase 3)
  │
  ├─── [driver_id] ──→ rides
  │                        │
  │                        ├─── [ride_id] ──→ ride_history_logs
  │                        │                      │
  │                        │                  [actor_id] ──→ users
  │                        │
  │                        └─── [ride_id] ──→ email_notifications
  │                                               │
  │                                           [passenger_id] ──→ users (Phase 6)
  │
  └─── [driver_id] ──→ vehicles (Phase 3)
                            │
                         [vehicle_id] ──→ rides
```

---

## State Transition Diagram

```
                    ┌──────────────────────────────────────────┐
                    │         verification revoked (FR-020)    │
                    ↓                                          │
[created] → scheduled ──── driver cancels (FR-014) ────→ cancelled
                    │
          departure time reached
          + driver confirms start (FR-022)
                    │
                    ↓
              in_progress ──── driver confirms complete (FR-023) ──→ completed
```

**Invariants enforced at all times**:
- `available_seats = total_seats - booked_seats` (generated column, always consistent)
- `booked_seats >= 0` (DB check constraint)
- `available_seats >= 0` (guaranteed by generated column + booked_seats check)
- `booked_seats <= total_seats` (enforced at application layer when updating either field)

---

## `changed_fields` JSONB Schema (for `ride_history_logs` on `edited` actions)

```json
{
  "departure_datetime": { "before": "2026-06-20T08:00:00Z", "after": "2026-06-20T09:00:00Z" },
  "price_per_seat": { "before": "50.00", "after": "45.00" }
}
```

Only fields that actually changed are included. Field names match the `rides` table column names.
