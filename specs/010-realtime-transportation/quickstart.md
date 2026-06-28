# Quickstart Validation Guide: Real-Time Transportation

**Feature**: `010-realtime-transportation` | **Date**: 2026-06-28

---

## Prerequisites

- Phase 6 (Passenger Experience) fully deployed and working
- Supabase local instance running (`supabase start`)
- Phase 7 migrations applied (`supabase db push` or `supabase migration up`)
- **Supabase Realtime Authorization enabled** in project settings (Database → Replication → Realtime Authorization)
- Firebase project configured with a service account JSON stored in Supabase Vault under key `firebase_service_account`
- API running (`uvicorn app.main:app --reload`) — logs should include "FCM credentials loaded" at startup
- Frontend running (`pnpm --filter main dev`)
- Two test users in the database:
  - `driver@test.com` — role `driver`, `verification_status = approved`, active vehicle, one `scheduled` ride with confirmed bookings
  - `passenger@test.com` — role `passenger`, `verification_status = approved`, a `confirmed` booking on that ride

---

## Scenario 1: FCM Device Token Registration

**Goal**: Verify FR-001–FR-003 — token stored, duplicate upserted.

```bash
TOKEN=$(curl -s -X POST http://localhost:54321/auth/v1/token?grant_type=password \
  -H "apikey: <anon_key>" \
  -d '{"email":"passenger@test.com","password":"testpass"}' \
  | jq -r '.access_token')

# Register a token
curl -s -X POST http://localhost:8000/api/v1/users/me/device-tokens \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token": "fake_fcm_token_abc123", "platform": "web"}' | jq .
```

**Expected**: `200 OK` with `token_id`, `user_id`, `platform: "web"`, `last_seen_at`.

```bash
# Register same token again — should upsert, not duplicate
curl -s -X POST http://localhost:8000/api/v1/users/me/device-tokens \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token": "fake_fcm_token_abc123", "platform": "web"}' | jq .
```

**Verify in DB**:
```sql
SELECT COUNT(*) FROM user_device_tokens WHERE token = 'fake_fcm_token_abc123';
-- Expected: 1 (not 2)

SELECT last_seen_at FROM user_device_tokens WHERE token = 'fake_fcm_token_abc123';
-- Expected: timestamp updated to now
```

---

## Scenario 2: Start Ride → Notification Events Inserted

**Goal**: Verify FR-013–FR-015, data-model `started_at`, notification_events insertion.

```bash
DRIVER_TOKEN=$(curl -s -X POST http://localhost:54321/auth/v1/token?grant_type=password \
  -H "apikey: <anon_key>" \
  -d '{"email":"driver@test.com","password":"testpass"}' \
  | jq -r '.access_token')

RIDE_ID="<ride_id>"

curl -s -X POST http://localhost:8000/api/v1/rides/$RIDE_ID/start \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | jq .
```

**Expected**: `200 OK`, `ride.status = "in_progress"`, `ride.started_at` is a timestamp.

**Verify in DB**:
```sql
SELECT status, started_at FROM rides WHERE id = '<ride_id>';
-- Expected: in_progress, started_at = now (approximately)

SELECT event_type, status, recipient_user_id
FROM notification_events
WHERE payload->>'ride_id' = '<ride_id>'
  AND event_type = 'ride_started';
-- Expected: one row per confirmed passenger, status = 'pending'
```

**Error case** (try starting again):
```bash
curl -s -X POST http://localhost:8000/api/v1/rides/$RIDE_ID/start \
  -H "Authorization: Bearer $DRIVER_TOKEN" -d '{}' | jq .
-- Expected: HTTP 409, error = "ride_not_editable"
```

---

## Scenario 3: Driver Location Update

**Goal**: Verify FR-020–FR-022 — upsert driver_locations, reject wrong-status rides.

```bash
curl -s -X POST http://localhost:8000/api/v1/rides/$RIDE_ID/location \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "lat": 30.0444,
    "lng": 31.2357,
    "bearing": 145,
    "client_timestamp": "2026-06-28T08:05:00Z"
  }' | jq .
```

**Expected**: `200 OK`, `location_id`, `ride_id`, `updated_at`.

**Verify in DB**:
```sql
SELECT ST_Y(location::geometry) AS lat, ST_X(location::geometry) AS lng, bearing
FROM driver_locations
WHERE ride_id = '<ride_id>';
-- Expected: lat ≈ 30.0444, lng ≈ 31.2357, bearing = 145

-- Send a second update — verify single-row upsert (not append):
-- count should remain 1
SELECT COUNT(*) FROM driver_locations WHERE ride_id = '<ride_id>';
-- Expected: 1
```

**Auth check** (passenger trying to POST location):
```bash
curl -s -X POST http://localhost:8000/api/v1/rides/$RIDE_ID/location \
  -H "Authorization: Bearer $TOKEN" -d '{"lat":30.0,"lng":31.0,"client_timestamp":"..."}' | jq .
-- Expected: HTTP 403
```

---

## Scenario 4: Passenger Reads Driver Location

**Goal**: Verify FR-024 — confirmed passenger can read, others cannot.

```bash
curl -s -X GET http://localhost:8000/api/v1/rides/$RIDE_ID/location \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected**: `200 OK` with `lat`, `lng`, `bearing`, `client_timestamp`, `updated_at`. No `speed_kmh` field.

**Auth check** (unauthenticated user):
```bash
curl -s http://localhost:8000/api/v1/rides/$RIDE_ID/location | jq .
-- Expected: HTTP 401
```

---

## Scenario 5: FCM Dispatcher Dispatches Pending Events

**Goal**: Verify NFR-001, FR-006–FR-010 — dispatcher processes notification_events.

Note: In local dev, FCM sends will fail unless connected to real Firebase. Verify dispatcher behavior using a `failed` or `dispatched` status update instead.

```sql
-- Insert a test pending event
INSERT INTO notification_events (recipient_user_id, event_type, payload, status)
VALUES (
  '<passenger_user_id>',
  'booking_confirmed',
  '{"ride_id":"<ride_id>","booking_id":"<booking_id>","driver_name":"Ahmed","departure_datetime":"2026-07-01T08:00:00Z","deep_link":"/(passenger)/bookings/<booking_id>"}',
  'pending'
);
```

Wait up to 30 seconds (one dispatcher cycle), then:
```sql
SELECT status, retry_count, dispatched_at
FROM notification_events
WHERE recipient_user_id = '<passenger_user_id>'
  AND event_type = 'booking_confirmed';
-- Expected: status = 'dispatched' (real Firebase) or 'failed' (local dev, no valid token)
-- retry_count should be 0 if dispatched, or ≤ 3 if failed
```

**Idempotency check**:
```sql
-- Mark a dispatched event back to pending (simulate duplicate run)
UPDATE notification_events SET status = 'dispatched' WHERE id = '<event_id>';
-- Wait for next dispatcher run
-- Verify: no second FCM send (status unchanged, dispatched_at unchanged)
```

---

## Scenario 6: Complete Ride → Booking Cascade + Notifications

**Goal**: Verify FR-016–FR-019 — atomic completion, booking cascade, notification events.

```bash
curl -s -X POST http://localhost:8000/api/v1/rides/$RIDE_ID/complete \
  -H "Authorization: Bearer $DRIVER_TOKEN" -d '{}' | jq .
```

**Expected**: `200 OK`, `ride.status = "completed"`, `ride.completed_at` timestamp present.

**Verify in DB**:
```sql
SELECT status, completed_at FROM rides WHERE id = '<ride_id>';
-- Expected: completed, completed_at = now

SELECT status FROM bookings WHERE ride_id = '<ride_id>' AND status = 'confirmed';
-- Expected: 0 rows — all confirmed bookings cascaded to completed

SELECT COUNT(*) FROM bookings WHERE ride_id = '<ride_id>' AND status = 'completed';
-- Expected: N (all previously confirmed bookings)

SELECT event_type, status FROM notification_events
WHERE payload->>'ride_id' = '<ride_id>'
  AND event_type = 'ride_completed';
-- Expected: one row per completed booking, status = 'pending'
```

**Atomicity check** (only verifiable via error injection in tests):
- If any step in the transaction fails, all state should roll back; ride remains `in_progress`, no bookings cascade, no notification_events inserted.

---

## Scenario 7: Driver Pending-Booking Reminder

**Goal**: Verify FR-031–FR-033 — reminder sent once after 2-hour threshold.

```sql
-- Create a pending booking and age it to simulate 2+ hours without response
INSERT INTO bookings (ride_id, passenger_id, status, per_seat_price, total_price,
    passenger_pickup_point, passenger_dropoff_point, created_at)
VALUES ('<ride_id>', '<passenger_id>', 'pending', 45.00, 45.00,
    ST_SetSRID(ST_MakePoint(31.24, 30.06), 4326),
    ST_SetSRID(ST_MakePoint(31.23, 30.04), 4326),
    NOW() - INTERVAL '2 hours 5 minutes');
```

Wait for the reminder loop cycle (up to 5 minutes), then:
```sql
SELECT event_type, status, recipient_user_id
FROM notification_events
WHERE event_type = 'booking_received'
  AND payload->>'booking_id' = '<booking_id>';
-- Expected: one row, status = 'pending', recipient = driver's user_id

-- Verify exactly one reminder (FR-032):
-- Wait another 5 minutes — confirm no second row inserted
SELECT COUNT(*) FROM notification_events
WHERE event_type = 'booking_received'
  AND payload->>'booking_id' = '<booking_id>';
-- Expected: still 1 (not 2)
```

---

## Scenario 8: Live Tracking Frontend

**Goal**: Verify Story 3 end-to-end — passenger sees driver pin move.

1. Log in as `passenger@test.com` in browser tab A
2. Navigate to `/(passenger)/bookings/<booking_id>` — verify status shows "In Progress" with a link to tracking
3. Open `/(passenger)/rides/<ride_id>/tracking` — map loads with driver pin at last reported position
4. In a second terminal, POST a new location update as the driver every 5 seconds
5. Verify: map pin moves within ~3 seconds of each POST (Realtime event triggers GET refresh)
6. Stop sending updates, wait 60 seconds — verify "location may be outdated" banner appears
7. From the driver terminal, POST `complete` to finish the ride
8. Verify: tracking screen shows "Ride Completed" banner for ~3 seconds, then auto-redirects to `/(passenger)/bookings/<booking_id>`

---

## Key Files to Review After Implementation

| File | What to verify |
|------|----------------|
| `supabase/migrations/20260628000001_phase7_device_tokens.sql` | `user_device_tokens` created with `UNIQUE (token)` and RLS active |
| `supabase/migrations/20260628000002_phase7_notification_events.sql` | `notification_event_type` enum + `notification_events` table + dispatcher index |
| `supabase/migrations/20260628000003_phase7_driver_locations.sql` | `driver_locations` PostGIS geometry column + RLS enforcing confirmed booking membership |
| `supabase/migrations/20260628000004_phase7_rides_lifecycle.sql` | `started_at`/`completed_at` columns added; `bookings` and `driver_locations` in Realtime publication |
| `services/api/app/services/fcm_service.py` | Credentials loaded from Vault; `send_each_for_multicast()` used; expired token deregistration |
| `services/api/app/services/notification_dispatcher.py` | `FOR UPDATE SKIP LOCKED`; 3-retry limit; idempotent skip of `dispatched`/`failed` rows |
| `services/api/app/services/ride_service.py` | `start_ride()` sets `started_at` and inserts notification_events; `complete_ride()` sets `completed_at` |
| `services/api/app/services/booking_service.py` | `create_booking()` inserts `booking_received` event; confirm/reject/cancel insert corresponding events |
| `apps/main/src/app/(passenger)/rides/[id]/tracking/page.tsx` | Realtime cleanup in useEffect; 3-second auto-redirect on completion; stale indicator at 60 s |
| `apps/main/src/lib/hooks/useDriverLocation.ts` | Channel subscription cleaned up on unmount; stale detection logic |
