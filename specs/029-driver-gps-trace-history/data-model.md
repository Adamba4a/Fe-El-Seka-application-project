# Data Model: Driver GPS Trace History

One new table in the existing Supabase Postgres database. No changes to `driver_locations` or
`driver_locations_view`. Primary key is UUID (`gen_random_uuid()`), per constitution Data Standards.
`asyncpg` raw SQL, no ORM.

---

## `driver_location_history`

Append-only record of every GPS ping received during an active ride — one row per ping, never updated
or overwritten (contrast with `driver_locations`, which upserts a single current-position row per
ride).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `ride_id` | UUID NOT NULL | FK → `rides(id)` ON DELETE CASCADE — mirrors `driver_locations.ride_id` |
| `driver_id` | UUID NOT NULL | FK → `profiles(id)` ON DELETE CASCADE — mirrors `driver_locations.driver_id` |
| `location` | `geometry(Point,4326)` NOT NULL | PostGIS, per constitution Data Standards; same shape as `driver_locations.location` |
| `recorded_at` | TIMESTAMPTZ NOT NULL | The ping's `client_timestamp`, reused as-is from the same request that updates `driver_locations` (research.md R1) — not a separate server-assigned insert time |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT NOW() | Row-insert time, for operational purposes only; `recorded_at` is the field any future model/ETL should use |

Indexes:
- `(ride_id, recorded_at)` — reconstruct one ride's full trace in order (FR-006).
- `(recorded_at)` — supports the retention job's `DELETE ... WHERE recorded_at < now() - interval '30 days'` (research.md R3).

Note: unlike `driver_locations`, there is deliberately no `UNIQUE (ride_id)` constraint and no
`ON CONFLICT` upsert — every ping produces its own row.

---

## Relationships

```
rides ──< driver_location_history >── profiles (driver)
```

Independent of `driver_locations` — this table is additive, not a replacement or a foreign-keyed
extension of it. No relationship exists between the two tables at the schema level; they are kept in
timestamp agreement only by both being written from values on the same incoming request
(research.md R1).

## RLS

`ENABLE ROW LEVEL SECURITY`, no public policies. This is internal ML telemetry, not surfaced in any
passenger/driver/admin UI (per spec Out-of-Scope) — same posture as `match_events`/`search_sessions`
(013-match-learning-foundation), and unlike `driver_locations`, which has driver/passenger RLS policies
because it backs a real-time, user-facing feature. Only the backend service-role connection can
read/write this table.

## Retention

30-day rolling window, enforced by `location_history_retention_loop()` (research.md R3) — the only
new table in this codebase whose retention is enforced by application code rather than left unbounded
or deferred to a future feature (contrast with `match_events`/`match_outcomes`, whose retention is
explicitly deferred to Phase 13 item 046).
