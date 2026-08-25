# Phase 1 Data Model: Featured Rides

## Entity: Ride (extended)

Existing table: `rides` (`supabase/migrations/20260617000001_ride_management.sql`, extended by several later migrations). This feature adds three columns:

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `is_featured` | `boolean` | not null | `false` | Current Featured state (FR-001/FR-002). |
| `featured_at` | `timestamptz` | nullable | `null` | Set on feature, left as the last-set value on unfeature (last-action metadata, not history — see [research.md](./research.md) §1). |
| `featured_by` | `uuid` (FK → `profiles.id`) | nullable | `null` | Admin who performed the most recent feature/unfeature action. |

**Index**: partial index on `rides (departure_datetime) WHERE is_featured = true AND status = 'scheduled'` — supports the passenger Featured Rides read (decision 4 in research.md) without scanning the full table.

**Validation / state rules** (enforced at write time in the admin mutation endpoints, FR-003):

- A ride MAY be newly marked `is_featured = true` only if `status = 'scheduled'`, `departure_datetime > now()`, and `available_seats > 0`.
- A ride MAY be unmarked (`is_featured = false`) at any time, regardless of its current status.
- `is_featured = true` does NOT itself change any other ride field, booking eligibility, or the AI ranking/matching output (FR-013) — it is a pure discovery-surface flag.

**Derived visibility rule** (read time, not stored — FR-004, FR-012): a ride is included in the passenger Featured Rides listing if and only if `is_featured = true AND status = 'scheduled' AND departure_datetime > now() AND available_seats > 0`. This is recomputed fresh on every request; a ride can have `is_featured = true` in storage while being invisible to passengers because it no longer meets this derived condition (e.g. it filled up) — no separate cleanup job is required.

## Entity: Featured Rides Listing (derived, not a table)

A read-time projection of Ride rows matching the derived visibility rule above, sorted by `departure_datetime ASC` (soonest first — per spec Assumptions, no manual admin ordering in this iteration). Each item exposes: `id`, `origin`, `destination`, `departure_datetime`, `price_per_seat`, `available_seats` (FR-008).

## Entity: Admin Audit Log (extended)

Existing table: `admin_audit_logs` (used via `services/api/app/services/audit_service.py::append_log`). This feature adds one column:

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `ride_id` | `uuid` (FK → `rides.id`) | nullable | Set for `action_type IN ('ride_featured', 'ride_unfeatured')`; null for all pre-existing action types. |

**New `action_type` values**: `ride_featured`, `ride_unfeatured`. `admin_audit_logs.action_type` has an existing `CHECK (action_type IN ('approved', 'rejected', 'suspended', 'reinstated', 'unlocked'))` constraint (`20260614000004_create_admin_audit_logs.sql`) that must be dropped and recreated to include these two new values, following the same drop/recreate pattern this constraint would need for any new action type (there is no prior example of extending it, since prior additions like `topup_request_id` reused existing values — this is the first feature needing genuinely new `action_type` values).

Each feature/unfeature admin action MUST append exactly one row here (FR-006), with `admin_id` = the acting admin, `target_user_id` = the ride's `driver_id`, `ride_id` = the ride. This is the audit trail; `rides.featured_at`/`rides.featured_by` (above) is a denormalized fast-path copy of the latest such action, not a replacement for it.

## State Transitions

```text
[not featured] --admin feature (if eligible)--> [featured, visible if still bookable]
[featured, visible]      --admin unfeature-------> [not featured]
[featured, visible]      --ride fills up----------> [featured (flag unchanged), NOT visible]
[featured, visible]      --ride cancelled----------> [featured (flag unchanged), NOT visible]
[featured, visible]      --departure time passes---> [featured (flag unchanged), NOT visible]
[featured, NOT visible]  --admin unfeature-------> [not featured]   (still allowed at any time, FR-002)
```

No transition automatically flips `is_featured` back to `false` in storage when a ride stops being visible — visibility is entirely a read-time computation (see Derived visibility rule). This keeps the write path simple (only two admin-triggered transitions exist) while still satisfying FR-004 at read time.
