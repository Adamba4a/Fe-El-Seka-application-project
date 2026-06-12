# Data Model: Platform Foundation

**Branch**: `001-platform-foundation` | **Date**: 2026-06-12
**Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

---

## Overview

Three foundation entities are introduced in this phase. They carry only the identifying fields required to unblock all subsequent phases. Additional domain columns (verification status, seats, prices, etc.) are added per-specification in Phases 3–9.

---

## Entity: users

Represents any registered platform participant. Role determines which experiences the user accesses post-login.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PRIMARY KEY, DEFAULT gen_random_uuid() | — |
| `phone` | `VARCHAR(20)` | UNIQUE, NOT NULL | E.164 format enforced at app layer |
| `role` | `VARCHAR(20)` | NOT NULL, CHECK in ('passenger', 'driver', 'both') | 'both' allows one account for dual usage |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | — |

**Indexes**:
- `users_phone_idx` — UNIQUE index on `phone` (enforced by constraint)

**RLS**: Enabled. Phase 1 uses permissive stub policy (`USING (true)`). Replaced with user-scoped policy in Phase 3.

**State transitions**: `role` is set at registration. Role upgrade (passenger → both, driver → both) is handled in Phase 5 user-management spec.

---

## Entity: rides

Represents a single carpooling ride published by a driver. Origin and destination are spatial points (WGS84).

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PRIMARY KEY, DEFAULT gen_random_uuid() | — |
| `driver_id` | `UUID` | NOT NULL, REFERENCES users(id) | FK to users; must have role 'driver' or 'both' (enforced in Phase 4) |
| `origin` | `GEOMETRY(POINT, 4326)` | NOT NULL | Driver's departure point |
| `destination` | `GEOMETRY(POINT, 4326)` | NOT NULL | Driver's destination |
| `departure_at` | `TIMESTAMPTZ` | NOT NULL | Scheduled departure time |
| `status` | `VARCHAR(20)` | NOT NULL, DEFAULT 'active', CHECK in ('active', 'paused', 'cancelled', 'completed') | — |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | — |

**Indexes**:
- `rides_driver_id_idx` — BTREE on `driver_id` (FK lookup)
- `rides_origin_idx` — GIST on `origin` (spatial queries)
- `rides_destination_idx` — GIST on `destination` (spatial queries)
- `rides_departure_at_idx` — BTREE on `departure_at` (time-range filtering)

**RLS**: Enabled. Phase 1 uses permissive stub policy. Replaced with driver-scoped write / public read policy in Phase 4.

**Status state machine**:

```
active → paused       (driver pauses)
active → cancelled    (driver or admin cancels)
active → completed    (ride finishes)
paused → active       (driver resumes)
paused → cancelled    (driver or admin cancels)
```

Enforcement of state transitions is implemented in Phase 4 (driver-ride-management spec).

---

## Entity: bookings

Represents a passenger's seat reservation on a ride. Links a passenger (user) to a ride.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PRIMARY KEY, DEFAULT gen_random_uuid() | — |
| `ride_id` | `UUID` | NOT NULL, REFERENCES rides(id) | FK to rides |
| `passenger_id` | `UUID` | NOT NULL, REFERENCES users(id) | FK to users; must have role 'passenger' or 'both' (enforced in Phase 6) |
| `status` | `VARCHAR(20)` | NOT NULL, DEFAULT 'pending', CHECK in ('pending', 'confirmed', 'cancelled', 'completed') | — |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | — |

**Indexes**:
- `bookings_ride_id_idx` — BTREE on `ride_id` (FK lookup, seat count queries)
- `bookings_passenger_id_idx` — BTREE on `passenger_id` (user history queries)

**Composite unique constraint**: `(ride_id, passenger_id)` — a passenger cannot book the same ride twice. Enforced in Phase 6.

**RLS**: Enabled. Phase 1 uses permissive stub policy. Replaced with passenger-scoped policy in Phase 6.

**Status state machine**:

```
pending → confirmed    (driver confirms)
pending → cancelled    (passenger or driver cancels)
confirmed → cancelled  (passenger or driver cancels pre-departure)
confirmed → completed  (ride completes)
```

Enforcement of state transitions is implemented in Phase 6 (booking-system spec).

---

## Entity Relationships

```
users (1) ──────────────── (N) rides
  │                              │
  │ (passenger)                  │ (ride)
  └────────── (N) bookings (N) ──┘
```

- One user (as driver) can publish many rides
- One user (as passenger) can have many bookings
- One ride can have many bookings (one per passenger)

---

## Migration Structure

Migrations live in `supabase/migrations/` with timestamp-prefixed filenames applied in order by the Supabase CLI.

```
supabase/migrations/
├── 20260612000000_enable_extensions.sql     # PostGIS + uuid-ossp
└── 20260612000001_foundation_schema.sql     # users, rides, bookings tables
```

**Migration 1 — Enable Extensions** (`20260612000000_enable_extensions.sql`):
- `CREATE EXTENSION IF NOT EXISTS postgis;`
- `CREATE EXTENSION IF NOT EXISTS "uuid-ossp";` (fallback; gen_random_uuid() is native in PG14+)

**Migration 2 — Foundation Schema** (`20260612000001_foundation_schema.sql`):
- Create `users`, `rides`, `bookings` tables as defined above
- Enable RLS on all three tables
- Add stub permissive policies on all three tables
- Create all indexes

---

## Soft Deletion Strategy

Soft deletion is the default for transactional entities (rides, bookings) per the Constitution Data Standards. `deleted_at TIMESTAMPTZ` columns and corresponding filtered views are added per-domain specification as needed (Phase 4 for rides, Phase 6 for bookings). Not introduced in Phase 1 to keep the foundation minimal.

---

## Fields Deferred to Later Phases

The following fields are intentionally omitted from Phase 1 and added by their respective specifications:

| Field | Entity | Added In |
|-------|--------|----------|
| `verification_status` | users | Phase 3 (passenger-verification, driver-verification) |
| `full_name`, `avatar_url` | users | Phase 3 (user-management) |
| `route_polyline` | rides | Phase 4 (driver-ride-creation) |
| `available_seats`, `price_per_seat` | rides | Phase 4 (driver-ride-creation) |
| `pickup_point`, `dropoff_point` | bookings | Phase 6 (booking-system) |
| `deleted_at` | rides, bookings | Phase 4, Phase 6 |
