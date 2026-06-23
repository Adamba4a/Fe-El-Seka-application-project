# Research: Passenger Experience

**Feature**: `009-passenger-experience` | **Date**: 2026-06-24

---

## 1. Atomic Seat Reservation

**Decision**: Conditional `UPDATE` on `booked_seats` with a row-count check — no explicit `SELECT FOR UPDATE`.

**Rationale**: The `rides` table uses a **generated column** (`available_seats SMALLINT GENERATED ALWAYS AS (total_seats - booked_seats) STORED`). Writing to `available_seats` directly is a PostgreSQL error. The correct pattern is:

```sql
UPDATE rides
SET booked_seats = booked_seats + 1
WHERE id = $1
  AND status = 'scheduled'
  AND booked_seats < total_seats
RETURNING id
```

If `RETURNING id` returns zero rows, the seat was already taken (or the ride is no longer `scheduled`). The `UPDATE` statement itself is atomic at the row level in PostgreSQL — no separate `SELECT FOR UPDATE` is needed because the conditional `WHERE booked_seats < total_seats` is evaluated and acted upon in a single operation. This is the same approach used in the existing `ride_service.py` `cancel_ride` pattern.

The booking creation must wrap this UPDATE and the `INSERT INTO bookings ...` in a single database transaction so that a seat increment without a booking record (or vice versa) is impossible.

**Seat release pattern** (cancellation): `UPDATE rides SET booked_seats = booked_seats - 1 WHERE id = $1 AND booked_seats > 0` — symmetric and safe.

**Alternatives considered**:
- `SELECT FOR UPDATE SKIP LOCKED`: More appropriate for queue-processing workers; adds unnecessary complexity for a simple booking flow.
- Optimistic locking (version column): Requires a retry loop in the application layer; more code for no benefit over the conditional UPDATE approach.

---

## 2. Notification System Alignment

**Decision**: Extend the existing `email_notifications` table and `notification_service.py` with booking-specific event types.

**Rationale**: The project already has a production-ready outbox pattern in `services/api/app/services/notification_service.py` backed by the `email_notifications` table (migration `20260617000001_ride_management.sql`). This table has a `notification_type TEXT` column currently storing only `'ride_cancelled'`. Phase 6 adds the following types to this column:

- `booking_confirmed`
- `booking_rejected`
- `booking_cancelled_by_passenger`
- `booking_cancelled_by_driver`
- `booking_expired`

The spec describes a conceptual `notification_events` / `NotificationEvent` entity. In the actual implementation, this maps to the existing `email_notifications` table. The spec entity's `status` field (`pending / dispatched / failed`) maps to the existing `email_notification_status` enum. The spec's `payload` JSONB field maps to a new `payload JSONB` column added to `email_notifications`.

**Phase 7 FCM alignment**: Phase 7 adds Firebase Cloud Messaging push notifications. When Phase 7 is built, it will consume the same `email_notifications` rows (filtered by a new `channel` column, or a parallel `push_notification_queue` table). Phase 6 does not implement FCM delivery — it only enqueues the notification rows, consistent with the spec's contract: "Phase 6 writes rows with `status = pending`; Phase 7 updates `status`."

**Migration needed**: Add `payload JSONB DEFAULT '{}'` column to `email_notifications` in the Phase 6 migration.

**Alternatives considered**:
- New `notification_events` table: Duplicates the existing outbox infrastructure; increases migration surface area; rejected in favour of extending what already exists.
- Direct API call to a Phase 7 endpoint: Phase 7 is not yet deployed; a synchronous call would introduce a hard runtime dependency between phases; rejected.
- Supabase Realtime broadcast: No durable queue; messages lost if no consumer is running; rejected.

---

## 3. Booking Expiry Background Task

**Decision**: Implement `booking_expiry_loop()` in `booking_service.py` using the same `asyncio.sleep` loop pattern as the existing `email_retry_loop()`.

**Rationale**: The project already registers `email_retry_loop` as an `asyncio` task at startup in `main.py` (`asyncio.create_task(email_retry_loop())`). A `booking_expiry_loop` follows the identical pattern:

```python
async def booking_expiry_loop() -> None:
    while True:
        try:
            await _expire_pending_bookings()
        except Exception as exc:
            logger.error("Booking expiry sweep error: %s", exc)
        await asyncio.sleep(600)  # 10-minute interval
```

The `_expire_pending_bookings()` function queries for bookings where `status = 'pending'` AND `created_at < NOW() - INTERVAL '24 hours'`, cancels each (updating `booked_seats`, inserting audit log rows, enqueuing notification rows), using `FOR UPDATE SKIP LOCKED` to support future multi-worker deployments without double-processing.

**Interval**: 10 minutes (`asyncio.sleep(600)`) — satisfies spec NFR-009 ("at least every 15 minutes").

**Alternatives considered**:
- APScheduler: External dependency; overkill for two background jobs; rejected.
- Supabase pg_cron: Requires access to Supabase pg_cron extension; not confirmed available; rejected.
- Cron-triggered HTTP endpoint: Adds operational complexity (who calls it?); rejected for MVP.

---

## 4. Passenger Authentication Dependency

**Decision**: Add `get_current_verified_passenger` to the existing `app/dependencies/verification.py` module.

**Rationale**: The existing `get_current_verified_driver` function validates the auth JWT and checks `role = 'driver'` + `verification_status = 'approved'`. The passenger equivalent checks `role` is NOT restricted to `driver` (any verified user can be a passenger) and `verification_status = 'approved'`. The dependency follows the same `Depends()` injection pattern used throughout the ride and vehicle routers.

The search endpoint uses this dependency. The booking creation endpoint uses this dependency. Driver-facing booking endpoints (confirm/reject) continue to use `get_current_verified_driver`.

---

## 5. Passenger Route Group

**Decision**: New `(passenger)/` route group under `apps/main/src/app/`, protected by the existing `middleware.ts`.

**Rationale**: The existing `(driver)/` route group demonstrates the established pattern: a `layout.tsx` that wraps passenger-specific navigation, with role-based access controlled by `middleware.ts`. The `(passenger)/` group mirrors this: same middleware file (updated with passenger route matchers), same Tailwind layout conventions, same shadcn/ui components.

No new Next.js app, no new `apps/` directory. This satisfies Constitution Principle VII (Shared Foundations, Independent Applications) — passenger and driver features share `apps/main`.

---

## 6. Ride Search Proxy

**Decision**: The `POST /api/v1/search/rides` endpoint is a thin FastAPI handler that validates the request, calls `candidate_service` directly (already imported in the rides router for Phase 5), and returns the serialized candidate list.

**Rationale**: `candidate_service.py` already implements the full Phase 5 pipeline: Stage 1 (SQL bounding-box + time-window filter), Stage 2 (OSRM compatibility computation), premium flag calculation, and default sort. The search endpoint in Phase 6 adds only: (a) passenger identity verification, (b) request validation/serialization, (c) response shaping for the passenger UI. No routing logic is duplicated.

**Phase 9 integration point**: The search endpoint will accept an optional `ranked_candidates` override from Phase 9 — or Phase 9 will call Phase 5 directly and return pre-ranked results to Phase 6's endpoint. The exact integration mechanism is defined in Phase 9's spec; Phase 6 must preserve the sort order received from Phase 5 as the default.
