# Quickstart: Ride Management Validation

**Branch**: `004-ride-management` | **Date**: 2026-06-17

This guide documents runnable validation scenarios that prove Phase 4 Ride Management works end-to-end. Run these after implementation to confirm acceptance criteria are met.

---

## Prerequisites

1. Phases 1–3 fully implemented and operational:
   - Supabase project running with PostGIS extension enabled
   - FastAPI backend running at `http://localhost:8000`
   - `apps/main` Next.js app running at `http://localhost:3000`
2. A test driver account: phone-OTP registered, identity verified, vehicle registered (from Phase 3 flows)
3. The test driver's Supabase access token (obtained after OTP login)
4. `curl` or any HTTP client (Postman, Bruno, etc.)

**Set environment variables for the examples below**:
```bash
DRIVER_TOKEN="your-supabase-access-token"
BASE="http://localhost:8000"
```

---

## Scenario 1 — Create a Ride (SC-001, FR-001, FR-002, FR-007)

**Goal**: Verified driver creates a ride; it appears with status `scheduled` and `available_seats = total_seats`.

```bash
curl -s -X POST "$BASE/api/v1/rides" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "origin": {
      "coordinates": { "lat": 30.0444, "lng": 31.2357 },
      "address": "Tahrir Square, Cairo"
    },
    "destination": {
      "coordinates": { "lat": 29.9792, "lng": 31.1342 },
      "address": "Giza Pyramids, Giza"
    },
    "departure_datetime": "'"$(date -u -d '+1 day' '+%Y-%m-%dT08:00:00Z')"'",
    "total_seats": 3,
    "price_per_seat": "45.00"
  }' | jq .
```

**Expected**: `201 Created`, response contains `status: "scheduled"`, `total_seats: 3`, `booked_seats: 0`, `available_seats: 3`.

Save the returned `id` as `RIDE_ID` for subsequent scenarios.

---

## Scenario 2 — Rejection: Unverified Driver (SC-002, FR-001)

**Goal**: An unverified user cannot create a ride (enforced at the backend).

Use the token of a freshly registered user who has not completed identity verification:

```bash
curl -s -X POST "$BASE/api/v1/rides" \
  -H "Authorization: Bearer $UNVERIFIED_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ ... }' | jq .error
```

**Expected**: `403 Forbidden`, `error: "not_verified_driver"`.

---

## Scenario 3 — Rejection: Departure Beyond 48 Hours (SC-008, FR-004)

**Goal**: Ride creation is rejected if departure is more than 2 days away.

```bash
curl -s -X POST "$BASE/api/v1/rides" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "origin": { "coordinates": { "lat": 30.0444, "lng": 31.2357 }, "address": "Tahrir Square" },
    "destination": { "coordinates": { "lat": 29.9792, "lng": 31.1342 }, "address": "Giza" },
    "departure_datetime": "'"$(date -u -d '+3 days' '+%Y-%m-%dT08:00:00Z')"'",
    "total_seats": 2,
    "price_per_seat": "40.00"
  }' | jq .error
```

**Expected**: `400 Bad Request`, `error: "ride_departure_too_far"`.

---

## Scenario 4 — Edit a Ride (FR-009, FR-012)

**Goal**: Driver edits price and notes; change is saved and logged in history.

```bash
curl -s -X PATCH "$BASE/api/v1/rides/$RIDE_ID" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "price_per_seat": "40.00", "notes": "Updated note" }' | jq .ride.price_per_seat
```

**Expected**: `200 OK`, `price_per_seat: "40.00"`.

Verify history was recorded:

```bash
curl -s "$BASE/api/v1/rides/$RIDE_ID" \
  -H "Authorization: Bearer $DRIVER_TOKEN" | jq '.history[-1].action'
```

**Expected**: `"edited"` with `changed_fields` containing `price_per_seat`.

---

## Scenario 5 — Seat Management Invariant (SC-003, FR-025, FR-027)

**Goal**: `available_seats` always equals `total_seats - booked_seats`; cannot go negative.

After editing total seats down from 3 to 2:
```bash
curl -s -X PATCH "$BASE/api/v1/rides/$RIDE_ID" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "total_seats": 2 }' | jq '{ total: .ride.total_seats, booked: .ride.booked_seats, available: .ride.available_seats }'
```

**Expected**: `{ "total": 2, "booked": 0, "available": 2 }`.

---

## Scenario 6 — Cancel a Ride (SC-004, FR-014, FR-015, FR-016)

**Goal**: Driver cancels a scheduled ride with a reason; status becomes `cancelled`.

```bash
curl -s -X POST "$BASE/api/v1/rides/$RIDE_ID/cancel" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "reason": "Change of plans." }' | jq .ride.status
```

**Expected**: `200 OK`, `status: "cancelled"`.

Verify that a cancellation without a reason is blocked:
```bash
curl -s -X POST "$BASE/api/v1/rides/$RIDE_ID/cancel" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | jq .error
```

**Expected**: `400 Bad Request`, `error: "reason_required"`.

---

## Scenario 7 — Ride Status Lifecycle (FR-022, FR-023, FR-024)

**Goal**: Ride moves `scheduled` → `in_progress` → `completed` via explicit driver actions; skipping steps is blocked.

Create a new ride with a departure time in the past (for testing — override validation in test env, or use a seeded test fixture):

```bash
# Start the ride (should succeed at/after departure time)
curl -s -X POST "$BASE/api/v1/rides/$RIDE_ID_2/start" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -d '{}' | jq .ride.status
# Expected: "in_progress"

# Complete the ride
curl -s -X POST "$BASE/api/v1/rides/$RIDE_ID_2/complete" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -d '{}' | jq .ride.status
# Expected: "completed"

# Attempt to skip in_progress (scheduled → completed directly) — should fail
# (Use a fresh scheduled ride)
curl -s -X POST "$BASE/api/v1/rides/$RIDE_ID_3/complete" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -d '{}' | jq .error
# Expected: "ride_not_editable"
```

---

## Scenario 8 — Verification Revocation Auto-Cancellation (SC-007, FR-018–FR-020)

**Goal**: When a driver's verification is revoked, all their `scheduled` rides are cancelled within 1 minute.

1. Create 2 scheduled rides as the test driver.
2. As an admin, suspend the driver via the Phase 3 admin dashboard (or directly call the Supabase admin API to set `verification_status = 'suspended'`).
3. The Supabase Database Webhook fires and POSTs to `/api/v1/internal/driver-revocation`.
4. Within 1 minute, verify both rides are `cancelled`:

```bash
curl -s "$BASE/api/v1/rides?status=scheduled" \
  -H "Authorization: Bearer $DRIVER_TOKEN" | jq .total
# Expected: 0

curl -s "$BASE/api/v1/rides?status=cancelled" \
  -H "Authorization: Bearer $DRIVER_TOKEN" | jq '.rides[0].cancellation_source'
# Expected: "system"
```

5. Verify the driver cannot create a new ride while suspended:

```bash
curl -s -X POST "$BASE/api/v1/rides" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -d '{ ... }' | jq .error
# Expected: "not_verified_driver"
```

---

## Scenario 9 — Dashboard (FR-028, FR-029, NFR-005)

**Goal**: Driver ride dashboard lists rides filtered by status and renders in under 2 seconds.

Open `http://localhost:3000/driver/rides` in a browser logged in as the test driver.

- Verify the dashboard shows rides grouped/filterable by status.
- Verify each listed ride shows: origin, destination, departure date/time, available/total seats, price per seat, and status.
- In browser DevTools (Network tab), confirm the page load completes within 2 seconds.

---

## Scenario 10 — Access Control (FR-027, FR-031)

**Goal**: Driver cannot access or modify another driver's ride.

With a second driver's `RIDE_ID_OTHER`:
```bash
curl -s "$BASE/api/v1/rides/$RIDE_ID_OTHER" \
  -H "Authorization: Bearer $DRIVER_TOKEN" | jq .error
# Expected: "ride_not_found" (ownership enforced; 403 returned as 404 for security)
```

---

## Map Pin Drop UI Validation (FR-002)

Open the "Post a Ride" screen in the Main App at `http://localhost:3000/driver/rides/new`.

1. Verify an interactive map renders (OpenStreetMap tiles visible).
2. Tap/click a location for origin — confirm a pin appears and a reverse-geocoded address label is shown below the map.
3. Tap/click a different location for destination — confirm a second pin and address label.
4. Submit the form — verify ride is created with both coordinate pairs stored.

---

## Artifact References

- Data model: [`data-model.md`](data-model.md)
- API contracts: [`contracts/rides-api.md`](contracts/rides-api.md)
- Functional requirements: [`spec.md`](spec.md)
