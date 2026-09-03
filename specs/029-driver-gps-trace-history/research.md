# Phase 0 Research: Driver GPS Trace History

## R1: Timestamp source for each history row

**Decision**: Reuse the request's already-validated `client_timestamp` (the same value
`location_service.upsert_location` already writes to `driver_locations.client_timestamp`) as the
history row's `recorded_at`. Do not introduce a second, server-assigned timestamp.

**Rationale**: `client_timestamp` is already validated Pydantic input (`LocationUpdateRequest`) on
every location-ping request — no new field, no new client contract. Using the identical value keeps
the history row and the live-position row in agreement about "when" for the same ping, which matters
for any future planned-vs-actual route-deviation analysis that needs to line trace points up against
`rides.route_geometry` timing.

**Alternatives considered**:
- `now()` at insert time — rejected: introduces clock skew between when the driver's device actually
  recorded the position and when the fire-and-forget task happens to execute, which is exactly the
  kind of imprecision a route-deviation model would need to correct for later if not avoided now.

---

## R2: Fire-and-forget persistence mechanism (no external queue)

**Decision**: `asyncio.create_task(...)` fired from `update_driver_location`
(`services/api/app/api/rides/router.py`) immediately after `location_service.upsert_location(...)`
succeeds. The task acquires its own short-lived connection from the existing `asyncpg` pool and
performs a single INSERT; the request handler does not `await` it, and the service function wraps the
insert in its own try/except so a failure only logs, never raises.

**Rationale**: Identical mechanism and rationale to `match_logging_service.persist_match_events`
(013-match-learning-foundation, research.md R3) — the codebase already has a proven, dependency-free
pattern for "log this, but never let logging affect the request it instruments." Reusing it exactly
avoids introducing a second logging idiom for what is functionally the same problem (best-effort,
loss-tolerant instrumentation on a hot request path). GPS pings arrive far more frequently per ride
than search requests, so keeping this off the synchronous path matters even more here.

**Alternatives considered**:
- A durable queue drained by a worker — rejected: at-least-once delivery is unnecessary complexity for
  data whose own success criteria (SC-001) already tolerate best-effort loss, same reasoning as 013.
- Writing the history row inside the same `conn`/request scope as the `driver_locations` upsert,
  synchronously — rejected: would add a second write to the hot ping path with no async boundary,
  directly risking NFR-001 (no measurable added latency) at high ping frequency.

---

## R3: Retention job mechanism

**Decision**: A new recurring in-process loop, `location_history_retention_loop()`, registered in
`main.py`'s `lifespan` alongside the existing 12 background loops (e.g. `retraining_scheduler_loop`,
`booking_expiry_loop`). Each tick runs a single `DELETE FROM driver_location_history WHERE
recorded_at < now() - interval '30 days'` and sleeps 24 hours before the next tick.

**Rationale**: The project already has a proven convention for periodic backend maintenance work — an
`async def ..._loop(): while True: try: ...; except Exception: log; await asyncio.sleep(N)` task
started at startup and cancelled at shutdown — used for retraining, booking expiry, driver reminders,
and config refresh. A 30-day rolling window only needs to be enforced roughly daily (rows aging past
the cutoff between ticks is invisible to any consumer, since nothing reads history rows on a tighter
cadence than that), so a 24-hour sleep is enough; this avoids adding a new scheduling dependency (e.g.
`pg_cron`, an external cron container) for a single DELETE statement.

**Alternatives considered**:
- PostgreSQL `pg_cron` extension — rejected: not currently used anywhere else in the project's Supabase
  setup; would introduce a second scheduling mechanism to operate and reason about for one query.
- A row-level TTL trigger (delete-on-insert-if-stale) — rejected: needlessly couples retention to the
  write path (violates NFR-001-style "don't add cost to the hot path" thinking) and only fires when new
  pings arrive, so a ride that stops generating pings would never have its own old rows purged.

---

## R4: Data model shape

Confirmed against the existing `match_events`/`search_sessions` precedent (013-match-learning-foundation):
one new table, `driver_location_history`, UUID-keyed, `asyncpg` raw SQL, no ORM, RLS enabled with no
public policies (service-role only — this table has no direct client read/write path, matching the
"internal ML telemetry, not surfaced in any UI" posture already established for `match_events`). See
`data-model.md`.
