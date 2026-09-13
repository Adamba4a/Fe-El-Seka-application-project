# Quickstart: Validating Ride Auto-Completion Timeout

Manual validation against local dev once implemented. Assumes the local Supabase stack (`supabase_db_fe-el-seka`) and `services/api` are running.

## Prerequisites

- Migration from data-model.md applied locally:
  ```
  docker exec -i supabase_db_fe-el-seka psql -U postgres -d postgres -f - < supabase/migrations/<YYYYMMDD>000001_ride_completion_source.sql
  ```
- `services/api` restarted so `ride_timeout_sweep_loop()` is running (background loops start at app startup — see research.md §1).

## Scenario 1 — never-started ride gets auto-completed and charged

1. Create a ride as a driver with `departure_datetime` set to just over 2 hours in the past (or fast-forward by editing the row directly for test purposes):
   ```sql
   UPDATE rides SET departure_datetime = now() - interval '2 hours 5 minutes' WHERE id = '<ride_id>';
   ```
2. Confirm a booking on it as a passenger before backdating, so there's something to charge.
3. Wait for the next sweep tick (≤10 minutes), or trigger `sweep_stale_rides()` directly via a Python shell for faster iteration.
4. Verify:
   ```sql
   SELECT status, started_at, completed_at, completion_source FROM rides WHERE id = '<ride_id>';
   -- expect: completed | <departure_datetime> | <sweep run time> | system
   SELECT * FROM commission_reservations WHERE ride_id = '<ride_id>';
   -- expect: no row (released)
   SELECT status FROM bookings WHERE ride_id = '<ride_id>';
   -- expect: completed
   ```
5. Confirm a `ride_completed` notification event exists for the passenger, and a `COMMISSION_DEBIT` wallet ledger entry exists for the driver.

## Scenario 2 — unbooked never-started ride is quietly closed out

Same as Scenario 1 but skip step 2 (no booking). Expect the ride to reach `completed`/`system` with the reservation released, no commission ledger entry, and no notification sent (see spec Acceptance Scenario 1.2).

## Scenario 3 — in-progress ride overdue for its own route duration

1. Start a ride, then backdate its `started_at` past its own `route_duration_minutes × 2` (floor 2h):
   ```sql
   UPDATE rides SET started_at = now() - interval '5 hours' WHERE id = '<ride_id>';
   -- ride's route_duration_minutes should be < 150 so 2h floor applies, or set started_at further back for longer routes
   ```
2. Wait for the sweep, then verify the same outcome as Scenario 1 (`completed`/`system`, reservation released, bookings completed, notified).

## Scenario 4 — long intercity ride is left alone mid-trip

1. Start a ride whose `route_duration_minutes` is large (e.g. 240 → 8h grace window). Backdate `started_at` by only 3 hours.
2. Wait for a sweep tick and confirm the ride is untouched (`status` still `in_progress`) — matches spec Acceptance Scenario 2.2.

## Scenario 5 — concurrent driver action wins

1. Backdate a ride's `departure_datetime` as in Scenario 1.
2. In the moment right before the sweep would run, manually cancel the ride via the normal driver-cancel endpoint.
3. Confirm the sweep's next tick does not error and does not resurrect the ride — it should simply find zero matching rows for that ride (already `cancelled`, no longer `scheduled`).

## Scenario 6 — auditability

Query for rides completed by each source:
```sql
SELECT completion_source, count(*) FROM rides WHERE status = 'completed' GROUP BY completion_source;
```
Confirm driver-completed rides from before this feature show `NULL`, and newly driver-completed rides show `'driver'`.
