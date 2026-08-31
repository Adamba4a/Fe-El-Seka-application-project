# Data Model: Recurring Rides

**Feature**: 027-recurring-rides | **Date**: 2026-08-31

## New table: `public.recurring_ride_definitions`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | `gen_random_uuid()` default, per Constitution Data Standards |
| `driver_id` | `UUID FK drivers` | Owning driver |
| `vehicle_id` | `UUID FK vehicles` | Same vehicle used for every generated instance, mirrors `rides.vehicle_id` |
| `origin_coordinates` | `geography(Point,4326)` | Mirrors `rides.origin_coordinates` |
| `origin_address` | `text` | |
| `destination_coordinates` | `geography(Point,4326)` | Mirrors `rides.destination_coordinates` |
| `destination_address` | `text` | |
| `departure_time` | `TIME` | Time-of-day only (date comes from the generated instance's calendar date) |
| `weekdays` | `SMALLINT[]` | ISO weekday numbers (1=Monday..7=Sunday) the driver runs this route; CHECK non-empty (FR-002) |
| `total_seats` | `SMALLINT` | Copied onto each generated instance's `total_seats` |
| `price_per_seat` | `NUMERIC(10,2)` | Copied onto each generated instance's `price_per_seat` |
| `notes` | `text` | Optional, mirrors `rides.notes` |
| `status` | `recurring_definition_status ENUM('active','ended')` | Driver-controlled; `ended` stops future generation (FR-008) but never touches existing instances |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | Standard audit columns |

RLS: same policy shape as `rides.driver_read_own_rides` — a `driver_read_own_recurring_definitions` policy restricting rows to `driver_id = auth.uid()`-equivalent, consistent with Constitution Security & Privacy Requirements.

## Extended table: `public.rides`

| New column | Type | Notes |
|---|---|---|
| `recurring_ride_definition_id` | `UUID FK recurring_ride_definitions ON DELETE SET NULL` | Nullable — `NULL` for one-off rides (the overwhelming majority), set for every generated day instance. `ON DELETE SET NULL` rather than `CASCADE`/`RESTRICT`: a definition row is never deleted (only marked `ended`), so this is a defensive default, not an active code path. |

No other `rides` columns change meaning. A generated instance is a normal `rides` row (`status`, `booked_seats`, `available_seats`, `route_geometry`, `route_distance_km`, `route_duration_minutes`, cancellation fields, etc. all behave identically to a one-off ride, per Decision 3 in research.md).

## Relationships

- `recurring_ride_definitions.driver_id` → `drivers.id` (many definitions per driver, per Assumptions in spec.md)
- `recurring_ride_definitions.vehicle_id` → `vehicles.id`
- `rides.recurring_ride_definition_id` → `recurring_ride_definitions.id` (one definition has many generated `rides` rows; a `rides` row belongs to at most one definition)
- `bookings` → `rides` unchanged — a booking references a single day instance exactly as it references a one-off ride today (per spec.md Key Entities)

## State transitions

**Recurring Ride Definition**: `active` → `ended` (one-way; driver action, FR-008). No `active` → `active` re-activation flow in v1 (out of scope; not requested by spec).

**Generated instance eligibility visibility** (not a stored state, computed at query time per FR-012): an instance with zero confirmed bookings is excluded from search/booking results whenever its parent definition's driver is currently ineligible (unverified vehicle/driver status) or the definition is `ended` and the instance hasn't been generated yet (moot — ended definitions stop generating). An instance with ≥1 confirmed booking is always visible/unaffected regardless of eligibility.

**Ride Day Instance lifecycle**: identical to a one-off `Ride` (`scheduled` → `in_progress` → `completed`, or → `cancelled`) — no new states introduced (per spec.md Key Entities).

## Validation rules (from Functional Requirements)

- `weekdays` must contain at least one value (FR-002).
- Editing a definition (`route`/`departure_time`/`total_seats`/`price_per_seat`) propagates to: (a) not-yet-generated future instances, and (b) already-generated instances with zero confirmed bookings that haven't passed the existing ride-edit cutoff window. Instances with ≥1 confirmed booking are excluded from the update (FR-011).
- Generation must not produce a duplicate instance for the same `(recurring_ride_definition_id, calendar_date)` pair — enforced via a unique constraint on `rides (recurring_ride_definition_id, departure_datetime::date)` scoped to non-null `recurring_ride_definition_id`, guarding the generation loop's idempotency (NFR-001).
