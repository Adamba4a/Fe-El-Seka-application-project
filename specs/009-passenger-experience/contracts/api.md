# API Contracts: Passenger Experience

**Feature**: `009-passenger-experience` | **Date**: 2026-06-24

All endpoints are prefixed `/api/v1`. All requests require a valid Supabase Auth JWT in the `Authorization: Bearer <token>` header unless noted otherwise.

Authentication errors return `HTTP 401`. Authorization errors (e.g., acting on another user's resource) return `HTTP 403`. Validation errors return `HTTP 422`.

---

## Search

### `POST /api/v1/search/rides`

Search for compatible ride candidates for a passenger journey.

**Auth**: Verified passenger (`verification_status = approved`). Returns `HTTP 403` if not verified.

**Request**:
```json
{
  "origin": { "lat": 30.0626, "lng": 31.2497 },
  "destination": { "lat": 30.0444, "lng": 31.2357 },
  "desired_departure_at": "2026-07-01T08:00:00Z"
}
```

**Response `200 OK`**:
```json
{
  "candidates": [
    {
      "ride_id": "uuid",
      "driver": {
        "display_name": "Ahmed Hassan",
        "avatar_url": "https://...",
        "is_verified": true
      },
      "departure_datetime": "2026-07-01T08:00:00Z",
      "available_seats": 2,
      "per_seat_price": "45.00",
      "candidate_type": "standard",
      "compatibility": {
        "overlap_percentage": 82.5,
        "pickup_walk_meters": 210,
        "dropoff_walk_meters": 180,
        "driver_detour_km": 0.4,
        "driver_detour_minutes": 2,
        "is_compatible": true,
        "premium_pickup_available": false,
        "premium_pickup_fee": null,
        "premium_dropoff_available": false,
        "premium_dropoff_fee": null
      }
    }
  ],
  "total": 3,
  "no_rides_found": false
}
```

**Empty result `200 OK`**:
```json
{ "candidates": [], "total": 0, "no_rides_found": true }
```

**Error `503 Service Unavailable`**: Phase 5 OSRM routing unavailable.

---

## Ride Detail

### `GET /api/v1/rides/{ride_id}/passenger-detail`

Full ride detail for a specific passenger journey (requires the passenger's origin/destination to compute boarding/alighting points).

**Auth**: Any authenticated user.

**Query parameters**:
- `origin_lat`, `origin_lng` — passenger origin (required)
- `destination_lat`, `destination_lng` — passenger destination (required)

**Response `200 OK`**:
```json
{
  "ride": {
    "id": "uuid",
    "status": "scheduled",
    "driver": {
      "display_name": "Ahmed Hassan",
      "avatar_url": "https://...",
      "is_verified": true
    },
    "departure_datetime": "2026-07-01T08:00:00Z",
    "available_seats": 2,
    "per_seat_price": "45.00",
    "route_geometry": "encoded_polyline_string",
    "route_distance_km": 18.4,
    "route_duration_minutes": 32
  },
  "passenger_context": {
    "boarding_point": { "lat": 30.0631, "lng": 31.2481 },
    "alighting_point": { "lat": 30.0451, "lng": 31.2349 },
    "pickup_walk_meters": 210,
    "dropoff_walk_meters": 180,
    "estimated_travel_minutes": 28,
    "premium_pickup_available": false,
    "premium_pickup_fee": null,
    "premium_dropoff_available": false,
    "premium_dropoff_fee": null
  }
}
```

**Error `410 Gone`**: Ride is `cancelled` or `completed` — no longer bookable.

---

## Bookings

### `POST /api/v1/bookings`

Create a booking. Atomically increments `rides.booked_seats`.

**Auth**: Verified passenger.

**Request**:
```json
{
  "ride_id": "uuid",
  "boarding_point": { "lat": 30.0631, "lng": 31.2481 },
  "alighting_point": { "lat": 30.0451, "lng": 31.2349 },
  "premium_pickup_requested": false,
  "premium_dropoff_requested": false
}
```

**Response `201 Created`**:
```json
{
  "booking_id": "uuid",
  "ride_id": "uuid",
  "status": "pending",
  "per_seat_price": "45.00",
  "total_price": "45.00",
  "premium_pickup_requested": false,
  "premium_dropoff_requested": false,
  "premium_pickup_fee": null,
  "premium_dropoff_fee": null,
  "created_at": "2026-06-24T10:00:00Z"
}
```

**Error `409 Conflict`**: No seats available, or passenger already has an active booking for this ride.

**Error `422 Unprocessable Entity`**: Ride is not `scheduled`, or departure time is in the past.

---

### `GET /api/v1/bookings`

List the authenticated passenger's bookings.

**Auth**: Any authenticated user (returns only their own bookings).

**Query parameters**:
- `status` (optional) — filter by `pending` | `confirmed` | `cancelled` | `completed`
- `page` (optional, default 1), `page_size` (optional, default 20)

**Response `200 OK`**:
```json
{
  "bookings": [
    {
      "booking_id": "uuid",
      "ride_id": "uuid",
      "status": "confirmed",
      "driver_display_name": "Ahmed Hassan",
      "departure_datetime": "2026-07-01T08:00:00Z",
      "per_seat_price": "45.00",
      "total_price": "45.00",
      "premium_pickup_requested": false,
      "premium_dropoff_requested": false,
      "created_at": "2026-06-24T10:00:00Z",
      "confirmed_at": "2026-06-24T10:05:00Z",
      "cancelled_at": null
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

---

### `GET /api/v1/bookings/{booking_id}`

Get a single booking detail.

**Auth**: Booking's passenger or ride's driver.

**Response `200 OK`**: Same shape as individual item in list above, with additional `boarding_point`, `alighting_point`, and `cancellation_reason` fields.

**Error `404 Not Found`**: Booking does not exist or caller has no access.

---

### `POST /api/v1/bookings/{booking_id}/cancel`

Passenger cancels their own booking.

**Auth**: Booking's passenger only.

**Request** (optional):
```json
{ "reason": "Plans changed" }
```

**Response `200 OK`**:
```json
{
  "booking_id": "uuid",
  "status": "cancelled",
  "cancelled_by": "passenger",
  "late_cancellation": false,
  "cancelled_at": "2026-06-24T11:00:00Z"
}
```

**Error `409 Conflict`**: Booking is already `cancelled` or `completed`.

---

## Driver Booking Actions

### `GET /api/v1/rides/{ride_id}/bookings`

Driver lists all bookings for their ride.

**Auth**: Verified driver who owns the ride.

**Query parameters**:
- `status` (optional) — filter by `pending` | `confirmed` | `cancelled` | `completed`

**Response `200 OK`**:
```json
{
  "bookings": [
    {
      "booking_id": "uuid",
      "passenger": {
        "display_name": "Sara Ahmed",
        "avatar_url": "https://..."
      },
      "status": "pending",
      "per_seat_price": "45.00",
      "total_price": "45.00",
      "boarding_point": { "lat": 30.0631, "lng": 31.2481 },
      "alighting_point": { "lat": 30.0451, "lng": 31.2349 },
      "premium_pickup_requested": false,
      "premium_pickup_fee": null,
      "premium_dropoff_requested": false,
      "premium_dropoff_fee": null,
      "created_at": "2026-06-24T10:00:00Z"
    }
  ],
  "total": 1
}
```

---

### `POST /api/v1/rides/{ride_id}/bookings/{booking_id}/confirm`

Driver confirms a pending booking.

**Auth**: Verified driver who owns the ride.

**Request**: empty body `{}`

**Response `200 OK`**:
```json
{
  "booking_id": "uuid",
  "status": "confirmed",
  "confirmed_at": "2026-06-24T10:05:00Z"
}
```

**Error `409 Conflict`**: Booking is not in `pending` status.

---

### `POST /api/v1/rides/{ride_id}/bookings/{booking_id}/reject`

Driver rejects a pending booking. Applies premium fallback rule if applicable.

**Auth**: Verified driver who owns the ride.

**Request** (optional):
```json
{ "reason": "Route conflict" }
```

**Response `200 OK`**:
```json
{
  "booking_id": "uuid",
  "status": "cancelled",
  "cancelled_by": "driver",
  "fallback_applied": false
}
```

Where `fallback_applied: true` means the premium request was declined but the booking was kept as a standard confirmed booking (see spec FR-021).

**Error `409 Conflict`**: Booking is not in `pending` status.

---

### `POST /api/v1/rides/{ride_id}/bookings/{booking_id}/cancel`

Driver cancels a specific confirmed or pending booking without cancelling the entire ride.

**Auth**: Verified driver who owns the ride.

**Request** (optional):
```json
{ "reason": "Passenger no-show" }
```

**Response `200 OK`**:
```json
{
  "booking_id": "uuid",
  "status": "cancelled",
  "cancelled_by": "driver",
  "late_cancellation": false
}
```

**Error `409 Conflict`**: Booking is already `cancelled` or `completed`.

---

## Error Response Shape (all endpoints)

```json
{
  "error": "machine_readable_code",
  "message": "Human-readable description"
}
```

Common `error` codes for Phase 6:

| Code | HTTP | Meaning |
|------|------|---------|
| `not_verified` | 403 | Passenger verification not approved |
| `no_seats_available` | 409 | Ride fully booked at booking creation time |
| `duplicate_booking` | 409 | Passenger already has an active booking for this ride |
| `ride_not_schedulable` | 422 | Ride is not in `scheduled` status |
| `ride_departed` | 422 | Ride departure time is in the past |
| `booking_not_pending` | 409 | Action requires `pending` status |
| `booking_terminal` | 409 | Booking is already `cancelled` or `completed` |
| `routing_unavailable` | 503 | Phase 5 OSRM routing service is down |
