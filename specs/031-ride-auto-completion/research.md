# Research: Ride Auto-Completion Timeout

## 1. Background loop pattern

**Decision**: Add `ride_timeout_sweep_loop()` to `services/api/app/services/ride_service.py`, following the exact shape of `recurring_ride_generation_loop()` (`app/services/recurring_ride_service.py:719-728`):

```python
async def ride_timeout_sweep_loop() -> None:
    while True:
        try:
            completed = await sweep_stale_rides()
            if completed:
                logger.info("ride_timeout_sweep_loop completed=%d", completed)
        except Exception as exc:
            logger.error("Ride timeout sweep loop error: %s", exc)
        await asyncio.sleep(600)
```

Wired into `app/main.py`'s lifespan the same way `recurring_generation_task` is (`app/main.py:99` for start, `:103` for shutdown `.cancel()`): one more `asyncio.create_task(...)` at startup, one more `.cancel()` at shutdown.

**Rationale**: This exact pattern (unbounded loop, per-tick try/except, fixed `asyncio.sleep`, started/cancelled alongside ~12 sibling loops already in `main.py`) is the established convention for every recurring background job in this codebase — reusing it is a zero-new-concepts change (NFR-001, NFR-004).

**Alternatives considered**: A dedicated `apscheduler`/cron-style scheduler was rejected — no other job in this codebase uses one, and introducing a new scheduling dependency for a single job would violate the "avoid unnecessary complexity" quality standard in the constitution's Development Workflow Standards.

## 2. Finding stale rides

**Decision**: Two read-only queries per tick, no new indexes required at current scale (mirrors the unindexed `rides.status`/`departure_datetime` filters already used elsewhere, e.g. `recurring_ride_service.py`'s own instance queries):

```sql
-- never-started
SELECT id FROM rides
WHERE status = 'scheduled'
  AND departure_datetime < now() - interval '2 hours';

-- started but never completed
SELECT id FROM rides
WHERE status = 'in_progress'
  AND started_at < now() - GREATEST(
        interval '2 hours',
        (COALESCE(route_duration_minutes, 0) * 2) * interval '1 minute'
      );
```

**Rationale**: Matches FR-010/FR-011 exactly. `COALESCE(route_duration_minutes, 0)` means a ride with no recorded route duration falls back to the flat 2-hour floor rather than erroring or never becoming eligible.

**Alternatives considered**: Doing this as a single `UNION` query was rejected — the two branches feed different follow-up logic (one needs a start backfilled first, one doesn't), so keeping them separate reads more clearly in the sweep function.

## 3. Reusing `start_ride` / `complete_ride` instead of a new transition function

**Decision**: Extend `start_ride()` with a `system_started_at: Optional[datetime] = None` parameter used in place of `now()` for the timestamp and to bypass the `now() >= departure_datetime` guard (which exists only to stop a *driver* from starting early — irrelevant once the sweep has already independently confirmed the ride is 2+ hours overdue). Extend `complete_ride()` with a `completion_source: str = "driver"` parameter threaded straight into the new `completion_source` column (§4). The sweep then does, per never-started ride:

```python
await start_ride(ride_id, driver_id, system_started_at=ride["departure_datetime"])
await complete_ride(ride_id, driver_id, completion_source="system")
```

and, per in-progress-too-long ride, just:

```python
await complete_ride(ride_id, driver_id, completion_source="system")
```

**Rationale**: `complete_ride()` already implements every consequence FR-003 requires (commission charge, reservation release, booking finalization, notification) — duplicating that logic in a new function would let the two paths drift out of sync over time, which the user's spec explicitly warns against ("reusing that logic rather than duplicating it"). Backfilling `started_at = departure_datetime` (not `now()`) keeps ride-duration-derived reporting (e.g. any future "how long did the ride take" metric) meaningful instead of showing a duration equal to however late the sweep happened to run.

**Alternatives considered**: A single new `force_complete_ride()` function that jumps `scheduled`/`in_progress` straight to `completed` in one transaction was considered (would avoid two round-trips for the never-started case) but rejected — it would duplicate both the `start_ride` and `complete_ride` bodies, doubling the maintenance surface FR-003 depends on staying in sync. Two sequential calls to already-correct functions is simpler and matches "solutions MUST favor simplicity" in the constitution.

## 4. `completion_source` column

**Decision**: New nullable `TEXT` column on `rides`:

```sql
ALTER TABLE rides ADD COLUMN completion_source TEXT
  CHECK (completion_source = ANY (ARRAY['driver'::text, 'system'::text]));
```

Set to `'driver'` by the existing driver-facing complete endpoint (default parameter value), `'system'` by the sweep. Nullable because every ride that is `scheduled`/`in_progress`/`cancelled`, and every already-`completed` ride from before this migration, has no meaningful value for it.

**Rationale**: Mirrors `rides.cancellation_source`'s existing CHECK-constraint pattern exactly (`rides_cancellation_source_check`, added in `supabase/migrations/20260617000001_ride_management.sql`) — same two-value vocabulary, same nullability rationale, satisfies FR-006/User Story 3 and the constitution's Auditability requirement ("ride operations... MUST be traceable and auditable") without inventing a new pattern.

**Alternatives considered**: Inferring source after the fact from `ride_history_logs` (e.g., "completed" log row with no matching prior "started" row within X minutes) was rejected — it's a fragile heuristic where a direct column is unambiguous and cheap.

## 5. Concurrency safety between the sweep and a driver's own action

**Finding**: `start_ride()` and `complete_ride()) currently guard status transitions purely in application code — `_fetch_own_ride()` does a plain `SELECT` (no `FOR UPDATE`), the status is checked in Python, and the subsequent `UPDATE rides SET status = ... WHERE id = $1` has no `AND status = 'expected'` clause (`ride_service.py:790-799`, `:860-866`, `:916-922`). Under Postgres READ COMMITTED, two concurrent transactions can each pass the Python-side check before either commits, then both proceed to update — a pre-existing latent race, not one this feature introduces, and out of scope to fully audit here.

**Decision**: Because the sweep runs unattended (unlike today's driver-tap callers, where genuine simultaneous double-taps are rare), narrow the fix to exactly the two functions this feature depends on: change both `UPDATE rides SET status = ... WHERE id = $1` statements to `WHERE id = $1 AND status = '<expected-prior-status>'`, and raise `RideServiceError("ride_not_editable", ..., 409)` when the returned row is `None` (zero rows updated) instead of assuming success. This closes the race for exactly the paths the sweep calls, satisfying FR-009/NFR-002, and also hardens the two existing driver-facing endpoints as a side effect.

**Rationale**: A full concurrency audit of every ride-mutating function (`cancel_ride` included) is explicitly out of scope for this feature (see spec Out-of-Scope) — fixing it everywhere would be an unrelated, unbounded refactor. Fixing it in the two functions this feature's sweep newly calls unattended is the minimal correct scope.

**Alternatives considered**: `SELECT ... FOR UPDATE` row locking inside `_fetch_own_ride()` was considered — it would also work, but changes the locking behavior of every caller of that shared helper (including all the other ride-mutating endpoints), which is a larger blast radius than the targeted `WHERE status = ...` guard for the two functions actually in scope.

## 6. Pending bookings at auto-completion time

**Decision**: No new code needed — `start_ride()` already expires any still-`pending` booking via `expire_one_pending_booking()` (`ride_service.py:890-898`) every time it runs, and the sweep's never-started path calls `start_ride()` before `complete_ride()`. For the in-progress-too-long path, the ride already passed through a real (or system-backfilled) `start_ride()` call in the past, so any pending requests were already expired at that time.

**Rationale**: Satisfies FR-005 with zero new code, confirming the "reuse, don't duplicate" approach extends cleanly to this requirement too.

## 7. Insufficient wallet balance at auto-completion

**Finding**: `deduct_commission()` (`commission_service.py:76-231`) has no insufficient-balance guard today — it locks the wallet row (`get_wallet_with_lock`) and unconditionally decrements it, for manual completions exactly as it would for auto-completions. This is pre-existing behavior, unchanged by this feature (confirmed in spec Assumptions: "this feature does not change what completion does, only when/how it gets triggered").

**Decision**: No new handling added — whatever the driver-facing manual "Complete" flow does today when balance is low, auto-completion does identically, since it's the same function call.

**Rationale**: Scoping a wallet-negative-balance policy change into this feature would silently expand it beyond "when a stale ride gets finalized" into "what completion means," which the spec's Out-of-Scope section explicitly excludes.
