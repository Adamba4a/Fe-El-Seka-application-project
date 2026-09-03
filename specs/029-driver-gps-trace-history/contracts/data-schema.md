# Contract: Driver GPS Trace History Data Schema

This feature adds no new external REST endpoints and changes no existing request/response shapes —
`POST /{ride_id}/location` keeps its current API contract unchanged (per spec Out-of-Scope: backend-only,
no UI-visible or API-visible change). The interface this feature exposes is the **database schema
itself**, which is the direct input contract for the future route-overlap-pooling-optimization model
(roadmap TBD item, per the 2026-09-03 data-collection audit's gap #1).

## Consumers

- Future `route-overlap-pooling-optimization` model (roadmap TBD) — reads `driver_location_history`
  to reconstruct each ride's actual driven path, for computing route overlap between drivers/rides.
- Any future route-deviation analysis (planned route vs. actual path) — reads `driver_location_history`
  joined against `rides.route_geometry`, using `recorded_at` for time alignment (research.md R1).

## Guaranteed shape

See `data-model.md` for full column definitions. Consumers can rely on:

- Every GPS ping accepted on `POST /{ride_id}/location` for an active ride produces, on a best-effort
  basis, exactly one `driver_location_history` row — never updated or overwritten after insert
  (contrast with `driver_locations`, which holds only the single latest position per ride).
- `recorded_at` is the ping's own `client_timestamp`, identical to the value stored in
  `driver_locations.client_timestamp` for the same ping — consumers reconstructing a trace and
  cross-referencing the live-position table can join on this value with no clock-skew correction
  needed (research.md R1).
- Ordering a ride's full trace is `SELECT ... WHERE ride_id = $1 ORDER BY recorded_at` — supported
  directly by the `(ride_id, recorded_at)` index (FR-006).
- Rows older than a rolling 30-day window are periodically purged (FR-004/FR-005) — consumers MUST NOT
  assume any row survives indefinitely, and MUST treat the absence of rows older than 30 days as
  expected deletion, not data loss to investigate.
- Logging is best-effort (SC-001): an occasional missing ping within an otherwise-present ride trace is
  expected and does not indicate a bug — consumers must not assume 100% ping-to-row capture.
- No column in this schema is ever backfilled retroactively; a row's absence for a time period before
  this feature's deployment means no data exists for that period (see spec Business Objective).

## Non-goals of this contract

- No data-quality filtering, smoothing, or outlier removal — owned by the future consuming model.
- No guaranteed maximum latency between a ping being accepted and its row being queryable (fire-and-forget,
  best-effort, per FR-003/NFR-001).
- No relationship enforced at the schema level between `driver_location_history` and `driver_locations`
  — the two tables are populated from the same request but are otherwise independent (data-model.md
  Relationships).
