# Data Model: Ride Auto-Completion Timeout

## Modified Entity: `rides`

One new column, mirroring the existing `cancellation_source` column exactly.

| Column | Type | Nullable | Constraint | Notes |
|---|---|---|---|---|
| `completion_source` | `TEXT` | Yes | `CHECK (completion_source = ANY (ARRAY['driver','system']))` | Set when a ride transitions to `completed`. `'driver'` for a manual complete-tap, `'system'` for the timeout sweep. `NULL` for rides that are `scheduled`, `in_progress`, `cancelled`, or `completed` before this migration. |

**Migration**: new file `supabase/migrations/<YYYYMMDD>000001_ride_completion_source.sql` (next available date-ordered slot after `20260903000002_fraud_signal_capture.sql`), containing:

```sql
ALTER TABLE rides ADD COLUMN completion_source TEXT
  CHECK (completion_source = ANY (ARRAY['driver'::text, 'system'::text]));
```

Applied to local dev via `docker exec supabase_db_fe-el-seka psql -U postgres -d postgres -f -` (this session's established convention). **Not applied to prod** during planning — deploy is a separate, explicit step.

## State Transitions (no new `ride_status` enum values)

The existing `ride_status` enum (`scheduled`, `in_progress`, `completed`, `cancelled`) is unchanged. This feature only adds *how* a ride reaches `completed`, not a new state:

```
scheduled ──(driver taps Start)──────────────► in_progress
scheduled ──(2h past departure, sweep)───────► in_progress ──(same tick)──► completed [completion_source='system']
in_progress ──(driver taps Complete)─────────► completed [completion_source='driver']
in_progress ──(route_duration×2, floor 2h, sweep)──► completed [completion_source='system']
```

The `scheduled → in_progress → completed` double-hop for a never-started ride happens within the same sweep tick, back-to-back, using `started_at = departure_datetime` (not the sweep's wall-clock time) so the ride's recorded duration reflects the scheduled trip, not sweep latency (see research.md §3).

## Function Signature Changes

| Function | File | Change |
|---|---|---|
| `start_ride` | `app/services/ride_service.py` | New optional `system_started_at: Optional[datetime] = None` param. When set: use it as `started_at` instead of `now()`, and skip the `now() >= departure_datetime` early-start guard (already satisfied by construction — the sweep only calls this once a ride is 2h overdue). |
| `complete_ride` | `app/services/ride_service.py` | New optional `completion_source: str = "driver"` param, written into the new column. Existing driver-facing callers are unaffected (default preserves current behavior). |
| `start_ride`, `complete_ride` | `app/services/ride_service.py` | `UPDATE rides SET status = ... WHERE id = $1` → `WHERE id = $1 AND status = '<expected-prior-status>'`; raise `RideServiceError("ride_not_editable", ..., 409)` if no row comes back (see research.md §5). |

## New Function

| Function | File | Purpose |
|---|---|---|
| `sweep_stale_rides() -> int` | `app/services/ride_service.py` | Runs the two queries from research.md §2, drives each matching ride through §3's call sequence inside its own per-ride `try/except` (so one failure doesn't block the rest — NFR-003), returns the count successfully finalized (for the loop's log line). |
| `ride_timeout_sweep_loop() -> None` | `app/services/ride_service.py` | The `while True` background loop (research.md §1), wired into `app/main.py` alongside the other ~12 background loops. |

## No New Entities

No new tables. No new enum values. No new API request/response models — this feature has no new API surface (see Out-of-Scope: no new endpoints).
