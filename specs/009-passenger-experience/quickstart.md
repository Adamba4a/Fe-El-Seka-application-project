# Quickstart Validation Guide: Passenger Experience

**Feature**: `009-passenger-experience` | **Date**: 2026-06-24

This guide describes how to validate that the Phase 6 implementation works end-to-end. Run these scenarios after the Phase 6 migration and backend deployment.

---

## Prerequisites

- Phase 5 (Route Intelligence) fully deployed and OSRM service running
- Two verified test users in the database:
  - `driver@test.com` — role `driver`, `verification_status = approved`, active vehicle, at least one `scheduled` ride with a Phase 5-calculated route polyline
  - `passenger@test.com` — role `passenger`, `verification_status = approved`
- Supabase local instance running (`supabase start`)
- API running (`uvicorn app.main:app --reload`)
- Frontend running (`pnpm --filter main dev`)

---

## Scenario 1: Ride Search Returns Candidates

**Goal**: Verify the search endpoint delegates to Phase 5 and returns formatted results.

```bash
# Get a passenger JWT
TOKEN=$(curl -s -X POST http://localhost:54321/auth/v1/token?grant_type=password \
  -H "apikey: <anon_key>" \
  -d '{"email":"passenger@test.com","password":"testpass"}' \
  | jq -r '.access_token')

# Search with origin near the driver's ride origin, destination near ride destination
curl -s -X POST http://localhost:8000/api/v1/search/rides \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "origin": {"lat": 30.0626, "lng": 31.2497},
    "destination": {"lat": 30.0444, "lng": 31.2357},
    "desired_departure_at": "2026-07-01T08:00:00Z"
  }' | jq .
```

**Expected**: Response with `candidates` array containing the driver's ride, each candidate including `ride_id`, `driver`, `available_seats`, `per_seat_price`, and `compatibility` fields. `no_rides_found: false`.

---

## Scenario 2: Create a Booking (Happy Path)

**Goal**: Verify atomic seat reservation and audit log creation.

```bash
RIDE_ID="<ride_id_from_scenario_1>"

# Create booking
BOOKING=$(curl -s -X POST http://localhost:8000/api/v1/bookings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"ride_id\": \"$RIDE_ID\",
    \"boarding_point\": {\"lat\": 30.0631, \"lng\": 31.2481},
    \"alighting_point\": {\"lat\": 30.0451, \"lng\": 31.2349},
    \"premium_pickup_requested\": false,
    \"premium_dropoff_requested\": false
  }")
echo $BOOKING | jq .
BOOKING_ID=$(echo $BOOKING | jq -r '.booking_id')
```

**Expected**: `status: "pending"`, `booking_id` returned. Verify in database:
```sql
SELECT status, per_seat_price FROM bookings WHERE id = '<booking_id>';
-- Expected: pending, price matches ride price_per_seat

SELECT booked_seats, available_seats FROM rides WHERE id = '<ride_id>';
-- Expected: booked_seats incremented by 1

SELECT event_type, actor_role FROM booking_audit_log WHERE booking_id = '<booking_id>';
-- Expected: one row with event_type='created', actor_role='passenger'
```

---

## Scenario 3: Duplicate Booking Rejected

**Goal**: Verify FR-014 (one active booking per passenger per ride).

```bash
curl -s -X POST http://localhost:8000/api/v1/bookings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"ride_id\": \"$RIDE_ID\", ...same payload...}" | jq .
```

**Expected**: `HTTP 409` with `"error": "duplicate_booking"`.

---

## Scenario 4: Driver Confirms Booking

**Goal**: Verify confirmation transitions booking to `confirmed` and sends notification.

```bash
DRIVER_TOKEN=$(curl -s -X POST http://localhost:54321/auth/v1/token?grant_type=password \
  -H "apikey: <anon_key>" \
  -d '{"email":"driver@test.com","password":"testpass"}' \
  | jq -r '.access_token')

curl -s -X POST http://localhost:8000/api/v1/rides/$RIDE_ID/bookings/$BOOKING_ID/confirm \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | jq .
```

**Expected**: `status: "confirmed"`, `confirmed_at` timestamp present. Verify:
```sql
SELECT status FROM bookings WHERE id = '<booking_id>';
-- Expected: confirmed

SELECT event_type FROM booking_audit_log WHERE booking_id = '<booking_id>' ORDER BY created_at;
-- Expected: created, confirmed

SELECT notification_type, status, payload FROM email_notifications
WHERE payload->>'booking_id' = '<booking_id>';
-- Expected: one row with notification_type='booking_confirmed', status='pending'
```

---

## Scenario 5: Passenger Cancels a Confirmed Booking

**Goal**: Verify seat release and late_cancellation flag.

```bash
# Cancel a confirmed booking (use a booking with departure > 1h away for non-late cancellation)
curl -s -X POST http://localhost:8000/api/v1/bookings/$BOOKING_ID/cancel \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Plans changed"}' | jq .
```

**Expected**: `status: "cancelled"`, `cancelled_by: "passenger"`. Verify:
```sql
SELECT booked_seats FROM rides WHERE id = '<ride_id>';
-- Expected: restored to pre-booking value

SELECT late_cancellation FROM bookings WHERE id = '<booking_id>';
-- Expected: false (departure > 1 hour away)
```

---

## Scenario 6: No Seats Available (Race Condition Simulation)

**Goal**: Verify exactly one booking succeeds when two requests race for the last seat.

Using a ride with exactly 1 remaining seat:

```bash
# Fire two concurrent booking requests
curl -s -X POST http://localhost:8000/api/v1/bookings \
  -H "Authorization: Bearer $TOKEN_A" ... &
curl -s -X POST http://localhost:8000/api/v1/bookings \
  -H "Authorization: Bearer $TOKEN_B" ... &
wait
```

**Expected**: One response is `201 Created`, the other is `409 Conflict` with `"error": "no_seats_available"`. After both settle:
```sql
SELECT COUNT(*) FROM bookings WHERE ride_id = '<ride_id>' AND status = 'pending';
-- Expected: 1 (not 2)

SELECT booked_seats FROM rides WHERE id = '<ride_id>';
-- Expected: total_seats (not exceeded)
```

---

## Scenario 7: Booking Expiry Loop

**Goal**: Verify pending bookings older than 24 hours are automatically cancelled.

```sql
-- Manually age a pending booking for testing
UPDATE bookings SET created_at = NOW() - INTERVAL '25 hours' WHERE id = '<booking_id>';
```

Then wait for the next expiry sweep (or trigger it via a test endpoint if implemented), then:

```sql
SELECT status, cancelled_by FROM bookings WHERE id = '<booking_id>';
-- Expected: cancelled, system

SELECT booked_seats FROM rides WHERE id = '<ride_id>';
-- Expected: decremented (seat released)

SELECT event_type FROM booking_audit_log WHERE booking_id = '<booking_id>';
-- Expected: created, expired
```

---

## Frontend Smoke Test

1. Log in as `passenger@test.com` in the browser
2. Navigate to `/search`
3. Enter origin and destination (geocode picker), set departure time, submit
4. Verify `RideCard` list appears with at least one result
5. Tap a card → `/rides/{id}` loads with map, driver info, and "Book Seat" button
6. Tap "Book Seat" → confirmation sheet appears with price summary
7. Confirm → redirected to `/bookings/{id}` showing "Awaiting Confirmation" status
8. Log in as `driver@test.com`, navigate to `/driver/rides/{ride_id}/bookings`
9. Verify the pending booking card appears; tap "Confirm"
10. Log back in as passenger, refresh `/bookings/{id}` → status shows "Confirmed"

---

## Key Files to Review After Implementation

| File | What to verify |
|------|----------------|
| `supabase/migrations/20260624000001_phase6_bookings.sql` | `bookings`, `booking_audit_log` tables created; RLS policies active |
| `services/api/app/services/booking_service.py` | `create_booking`, `confirm_booking`, `cancel_booking`, `booking_expiry_loop` |
| `services/api/app/api/bookings/router.py` | All 6 endpoints registered with correct auth dependencies |
| `services/api/app/api/search/router.py` | Delegates to `candidate_service`; returns shaped response |
| `apps/main/src/app/(passenger)/search/page.tsx` | Search form submits, renders `RideCard` list |
| `apps/main/src/app/(passenger)/rides/[id]/page.tsx` | Map renders, premium options shown when applicable |
