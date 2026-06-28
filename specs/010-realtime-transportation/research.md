# Research: Real-Time Transportation

**Feature**: `010-realtime-transportation` | **Date**: 2026-06-28

---

## 1. FCM Notification Dispatch — firebase-admin HTTP v1 API

**Decision**: Use the `firebase-admin` Python SDK with `messaging.send_each_for_multicast()` (HTTP v1 API) for FCM dispatch. Load Firebase service account credentials from Supabase Vault at FastAPI startup using the Supabase REST API with the service role key.

**Rationale**: The Firebase Legacy API (`/fcm/send`) is deprecated and will be shut down in June 2024 (already past). The HTTP v1 API via `firebase-admin` is the current standard. `send_each_for_multicast()` (introduced in firebase-admin 6.x as the successor to the deprecated `send_multicast()`) sends to a list of tokens and returns a `BatchResponse` where each `SendResponse` indicates per-token success or failure — critical for identifying and deregistering expired tokens (FR-004) without affecting other tokens for the same user.

**Credential loading pattern**:
```python
# At startup in lifespan(), call:
async def _load_fcm_credentials() -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        secret = await conn.fetchval(
            "SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = 'firebase_service_account'"
        )
    cred = credentials.Certificate(json.loads(secret))
    firebase_admin.initialize_app(cred)
```
The Vault query uses the `vault.decrypted_secrets` view, which requires the database role to have Vault access. The service account JSON is never written to disk or logs.

**Notification payload structure** (per FR-011):
```python
message = messaging.MulticastMessage(
    tokens=token_list,
    notification=messaging.Notification(title=title, body=body),
    data={
        "event_type": event_type,
        "ride_id": str(ride_id),
        "booking_id": str(booking_id) if booking_id else "",
        "deep_link": deep_link_path,
    },
    android=messaging.AndroidConfig(priority="high"),
    apns=messaging.APNSConfig(headers={"apns-priority": "10"}),
)
response = messaging.send_each_for_multicast(message)
```

**Token error handling**: If `send_response.exception` is a `FirebaseError` with code `messaging/registration-token-not-registered` or `messaging/invalid-registration-token`, the token must be deleted from `user_device_tokens` (FR-004).

**Alternatives considered**:
- FCM Legacy API: Deprecated, shut down — rejected.
- `httpx` direct HTTP calls to FCM REST API: More code, manual token refresh, no SDK benefits — rejected.
- `send_multicast()` (old API): Deprecated in firebase-admin 6.x, removed in 6.3+ — use `send_each_for_multicast()`.

---

## 2. notification_events Table — New Table, Not email_notifications Extension

**Decision**: Create a new `notification_events` table dedicated to FCM push notification dispatch. The existing `email_notifications` table is left unchanged and continues to serve email-only flows.

**Rationale**: The spec describes `NotificationEvent` as "extended from Phase 6," but Phase 6's actual implementation mapped this concept to the `email_notifications` table (a TEXT `notification_type` column, no enum, email-specific `passenger_email` field). FCM push dispatch has a fundamentally different shape: recipients are identified by device tokens (not email addresses), dispatch status semantics differ (`dispatched` vs `sent`), and the retry model differs (3 retries vs 5-tier exponential). Extending `email_notifications` with a `channel` discriminator would mix two unrelated delivery mechanisms in one table, complicating queries and future maintenance.

**Approach**: Phase 7 creates `notification_events` as a new table. Phase 6 booking service functions (`confirm_booking`, `reject_booking`, `cancel_booking`, `booking_expiry_loop`) are extended to insert rows into **both** `email_notifications` (existing email delivery) **and** `notification_events` (new FCM delivery) within the same transaction, so both channels are notified atomically.

**notification_event_type enum values** (all 8 from FR-007 plus `booking_received`):
`booking_received`, `booking_confirmed`, `booking_rejected`, `booking_cancelled`, `booking_expired`, `ride_cancelled`, `ride_started`, `ride_completed`

**Alternatives considered**:
- Extend `email_notifications` with `channel` column: Mixes email and FCM, complicates status semantics, adds nullable FCM-specific columns to an email-purpose table — rejected.
- Single unified outbox for all channels: Correct long-term design but premature abstraction for MVP with only two channels — rejected.

---

## 3. Background Task Pattern — asyncio.create_task Loops

**Decision**: The FCM notification dispatcher and driver reminder check are implemented as two separate `asyncio` coroutine loops registered at FastAPI startup using `asyncio.create_task()`, consistent with the existing `email_retry_loop`, `booking_expiry_loop`, and `pricing_config_refresh_loop` in `main.py`.

**Rationale**: The project already uses a well-established `while True: ... await asyncio.sleep(N)` pattern. Adding two more tasks follows zero new infrastructure. The FCM dispatcher sleeps 30 seconds between runs (NFR-001); the driver reminder loop sleeps 300 seconds (5 minutes) — sufficient resolution for a 2-hour reminder window with at most 5-minute delivery latency.

**FCM dispatcher loop sketch**:
```python
async def notification_dispatcher_loop() -> None:
    while True:
        try:
            await _process_pending_notifications()
        except Exception as exc:
            logger.error("FCM dispatcher error: %s", exc)
        await asyncio.sleep(30)
```

**Driver reminder loop sketch**:
```python
async def driver_reminder_loop() -> None:
    while True:
        try:
            await _check_overdue_pending_bookings()
        except Exception as exc:
            logger.error("Driver reminder sweep error: %s", exc)
        await asyncio.sleep(300)
```

**Note on clarification language**: The Phase 7 spec clarification described this as "separate APScheduler jobs." In the actual codebase, APScheduler is not used (it was explicitly rejected in Phase 6 research as an unnecessary dependency). The intent of the clarification — separate jobs with different intervals — is achieved by two independent asyncio loops, which is architecturally equivalent.

**Alternatives considered**:
- APScheduler: Not installed, rejected in Phase 6, unnecessary dependency for two loops — rejected.
- Single loop handling both dispatcher and reminder: Tightly couples concerns, makes interval tuning harder — rejected.

---

## 4. driver_locations — PostGIS Upsert

**Decision**: Single-row upsert per ride using `INSERT ... ON CONFLICT (ride_id) DO UPDATE SET ...`. The `location` column uses `ST_SetSRID(ST_MakePoint($lng, $lat), 4326)` to store coordinates as a PostGIS `geometry(Point, 4326)` — SRID 4326 (WGS 84), consistent with all other geometry columns in the project.

**Upsert pattern**:
```sql
INSERT INTO driver_locations
    (ride_id, driver_id, location, bearing, speed_kmh, client_timestamp, updated_at)
VALUES
    ($1, $2, ST_SetSRID(ST_MakePoint($3, $4), 4326), $5, $6, $7, now())
ON CONFLICT (ride_id) DO UPDATE SET
    location         = EXCLUDED.location,
    bearing          = EXCLUDED.bearing,
    speed_kmh        = EXCLUDED.speed_kmh,
    client_timestamp = EXCLUDED.client_timestamp,
    updated_at       = now();
```

The `ride_id` column has a `UNIQUE` constraint (enforced by the `ON CONFLICT` target). This keeps the table O(active rides) in size — roughly ≤50 rows at MVP scale.

**GET response**: Returns `ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng` plus `bearing`, `client_timestamp`, `updated_at`. `speed_kmh` is stored but NOT returned in the GET response (clarification 2026-06-28: stored for future analytics only).

---

## 5. SELECT FOR UPDATE SKIP LOCKED — Dispatcher Concurrency

**Decision**: Identical pattern to the existing `notification_service.py` email retry loop. The dispatcher claims a batch of pending notification_event rows within a transaction using `FOR UPDATE SKIP LOCKED`, processes them, and marks each `dispatched` or increments `retry_count` before releasing the lock.

**Pattern** (abbreviated):
```sql
SELECT id, recipient_user_id, event_type, payload, retry_count
FROM notification_events
WHERE status = 'pending'
ORDER BY created_at ASC
LIMIT 100
FOR UPDATE SKIP LOCKED
```

This prevents duplicate dispatch under concurrent FastAPI worker processes. The batch limit (100 per run) combined with the 30-second interval supports up to 200 dispatches/minute — well above the ≤1,000 pending events threshold in NFR-001.

---

## 6. Supabase Realtime Authorization — Server-Side RLS Filtering

**Decision**: Enable **Supabase Realtime Authorization** in the project dashboard (Database → Replication → Realtime Authorization toggle). Without this setting, Postgres Changes events bypass RLS and all row changes are broadcast to any connected client — violating NFR-005 and NFR-009.

**Enablement**: One-time project settings change (not a migration or code change). Must be completed before Phase 7 deployment.

**Frontend subscription pattern** (using `@supabase/supabase-js` v2 with Realtime Authorization):
```typescript
// In a useEffect with cleanup:
const channel = supabase
  .channel(`driver-location-${rideId}`)
  .on(
    'postgres_changes',
    {
      event: 'UPDATE',
      schema: 'public',
      table: 'driver_locations',
      filter: `ride_id=eq.${rideId}`,
    },
    (payload) => {
      // payload.new contains updated row
      setLocation({ lat: payload.new.lat, lng: payload.new.lng, bearing: payload.new.bearing });
    }
  )
  .subscribe();

return () => { supabase.removeChannel(channel); };
```

The `driver_locations` table does not expose `lat`/`lng` directly — they are stored as a PostGIS geometry. A database view or computed columns will need to expose `lat` and `lng` as plain floats for the Realtime payload to be useful on the frontend. See data-model.md for the `driver_locations_view` definition.

**Realtime publication**: The `bookings` and `driver_locations` tables must be added to the Supabase Realtime publication (`supabase_realtime`). This is done in migration `20260628000004_phase7_rides_lifecycle.sql`:
```sql
ALTER PUBLICATION supabase_realtime ADD TABLE public.bookings;
ALTER PUBLICATION supabase_realtime ADD TABLE public.driver_locations;
```

---

## 7. Live Tracking Map — Leaflet (Existing Library)

**Decision**: Use the existing Leaflet setup already installed in `apps/main`. The `LiveTrackingMap` component follows the same pattern as `RideMap.tsx` (imperative ref-based Leaflet initialization in `useEffect`). The driver pin is a `L.marker` that calls `.setLatLng()` on each Realtime location update — no full re-render required.

**Bearing-aware pin**: When `bearing` is non-null, apply a CSS `rotate(${bearing}deg)` transform to a custom directional icon. When `bearing` is null (stationary driver), use a standard circle marker without rotation.

**Stale location indicator**: A `lastUpdated` state tracks `updated_at` from the most recent Realtime event. If `Date.now() - lastUpdated > 60_000`, display the "location may be stale" banner (FR-026, Scenario 6).

**Alternatives considered**:
- Google Maps: Requires API key billing — rejected for MVP.
- Mapbox GL JS: Additional dependency, cost — rejected.
- React-Leaflet: Adds abstraction layer over the already-working imperative Leaflet pattern — rejected.
