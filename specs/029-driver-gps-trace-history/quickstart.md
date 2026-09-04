# Quickstart: Driver GPS Trace History

Validation scenarios proving the feature works end-to-end. Assumes local dev stack running
(`services/api`, Supabase local) with this feature's migration applied.

## Prerequisites

- `supabase db reset` (or `supabase migration up`) applied, including
  `20260903000001_driver_gps_trace_history.sql`.
- `services/api` running locally.
- A verified driver account with an active (`in_progress`) ride they can send location pings for.

## Scenario 1 — Every ping is preserved, not overwritten (User Story 1)

1. As the driver, `POST /api/v1/rides/{ride_id}/location` with a first `lat`/`lng`/`client_timestamp`.
2. Send a second `POST` to the same endpoint with a different `lat`/`lng` and a later
   `client_timestamp`.
3. Query: `SELECT lat, lng, recorded_at FROM driver_locations WHERE ride_id = '<ride_id>'` (via
   `ST_Y(location)`/`ST_X(location)`).
4. **Expected**: exactly one row — the second (latest) position — matching existing overwrite
   behavior (unchanged).
5. Query: `SELECT recorded_at, ST_X(location), ST_Y(location) FROM driver_location_history WHERE ride_id = '<ride_id>' ORDER BY recorded_at`.
6. **Expected**: two rows, one per ping, each `recorded_at` matching the `client_timestamp` sent in
   its request — both positions preserved even though `driver_locations` only kept the latest.

## Scenario 2 — History logging never blocks or fails the location update (User Story 1, FR-003/NFR-001)

1. Temporarily make `driver_location_history` unwritable (e.g. `REVOKE INSERT ON driver_location_history FROM <api role>;` or drop the table in a disposable local DB).
2. Send a location ping as in Scenario 1.
3. **Expected**: the `POST /{ride_id}/location` response still returns `200 OK` with the updated
   `driver_locations` row — the request must not error, hang, or slow down. Check application logs for
   a logged history-persistence failure.
4. Restore the table/grant before continuing.

## Scenario 3 — Full trace reconstruction ordering (FR-006)

1. Send at least 5 location pings for one ride, each with a distinct `client_timestamp` sent
   out of chronological order (e.g. shuffle the send order).
2. Query: `SELECT recorded_at FROM driver_location_history WHERE ride_id = '<ride_id>' ORDER BY recorded_at`.
3. **Expected**: rows come back sorted by `recorded_at` regardless of insertion order, reconstructing
   the ride's trace in the order the pings actually occurred.

## Scenario 4 — Retention purge (User Story 2, FR-004/FR-005)

1. Insert a test row directly with an old timestamp:
   `INSERT INTO driver_location_history (ride_id, driver_id, location, recorded_at) VALUES ('<ride_id>', '<driver_id>', ST_SetSRID(ST_MakePoint(31.2,30.0),4326), now() - interval '31 days');`
2. Manually invoke the retention purge (e.g. call `location_history_service.purge_expired()` from a
   local Python shell, or restart `services/api` and wait for the loop's first tick if testing the
   full loop).
3. Query: `SELECT count(*) FROM driver_location_history WHERE recorded_at < now() - interval '30 days'`.
4. **Expected**: `0` — the 31-day-old row was deleted; any rows within the 30-day window remain
   untouched.

## Scenario 5 — No client-visible or API-visible change (Out-of-Scope confirmation)

1. Compare the `POST /{ride_id}/location` response body before and after this feature's deployment.
2. **Expected**: identical shape — this feature adds no new response fields, headers, or endpoints.
