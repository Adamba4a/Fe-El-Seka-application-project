# API Contract: Ride Management

**Branch**: `004-ride-management` | **Date**: 2026-06-17

**Base URL**: `http://localhost:8000` (local) | `https://api.felseka.com` (production)

**Auth header**: `Authorization: Bearer {supabase_access_token}` on all protected endpoints.

**Content-Type**: `application/json`

---

## Error Response Schema

All error responses follow the same shape as Phase 3:

```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "detail": null
}
```

**Error codes introduced in this phase**:

| Code | Meaning |
|---|---|
| `not_verified_driver` | Caller is not a verified driver with an approved vehicle |
| `ride_not_found` | Ride does not exist or does not belong to the caller |
| `ride_not_editable` | Ride status is not `scheduled`; edit/cancel blocked |
| `ride_time_conflict` | Driver already has a ride within the 2-hour window |
| `ride_departure_past` | Departure time is in the past |
| `ride_departure_too_far` | Departure time is more than 48 hours from now |
| `ride_same_locations` | Origin and destination coordinates are identical |
| `seat_count_invalid` | Seat count is zero, negative, or exceeds vehicle capacity |
| `start_too_early` | Departure time has not yet been reached |
| `reason_required` | Cancellation reason is missing or empty |

---

## Ride Object (response schema)

```json
{
  "id": "uuid",
  "driver_id": "uuid",
  "vehicle_id": "uuid",
  "origin": {
    "coordinates": { "lat": 30.0444, "lng": 31.2357 },
    "address": "Tahrir Square, Cairo"
  },
  "destination": {
    "coordinates": { "lat": 29.9792, "lng": 31.1342 },
    "address": "Giza Pyramids, Giza"
  },
  "departure_datetime": "2026-06-18T08:00:00Z",
  "total_seats": 3,
  "booked_seats": 0,
  "available_seats": 3,
  "price_per_seat": "45.00",
  "status": "scheduled",
  "cancellation_reason": null,
  "cancellation_source": null,
  "notes": "No smoking please",
  "created_at": "2026-06-17T10:00:00Z",
  "updated_at": "2026-06-17T10:00:00Z"
}
```

---

## 1. Create Ride

### POST /api/v1/rides

Create a new scheduled ride. Caller must be a verified driver with an approved vehicle.

**Request**:
```json
{
  "origin": {
    "coordinates": { "lat": 30.0444, "lng": 31.2357 },
    "address": "Tahrir Square, Cairo"
  },
  "destination": {
    "coordinates": { "lat": 29.9792, "lng": 31.1342 },
    "address": "Giza Pyramids, Giza"
  },
  "departure_datetime": "2026-06-18T08:00:00Z",
  "total_seats": 3,
  "price_per_seat": "45.00",
  "notes": "No smoking please"
}
```

**Responses**:
- `201 Created` — ride created
```json
{ "ride": { /* Ride Object */ } }
```
- `400` — validation failure
```json
{ "error": "ride_same_locations", "message": "Origin and destination must be different locations." }
```
- `400` — departure time invalid
```json
{ "error": "ride_departure_past", "message": "Departure time must be in the future." }
```
- `400` — departure too far ahead
```json
{ "error": "ride_departure_too_far", "message": "Rides can only be scheduled up to 48 hours in advance." }
```
- `400` — seat count invalid
```json
{ "error": "seat_count_invalid", "message": "Seat count must be between 1 and your vehicle's capacity (N)." }
```
- `403` — caller not a verified driver
```json
{ "error": "not_verified_driver", "message": "Complete identity and vehicle verification before creating rides." }
```
- `409` — time conflict
```json
{ "error": "ride_time_conflict", "message": "You already have a ride within 2 hours of this departure time." }
```

---

## 2. List Driver's Rides

### GET /api/v1/rides

Return the authenticated driver's rides, newest first.

**Query parameters**:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `status` | string | (all) | Filter by status: `scheduled`, `in_progress`, `completed`, `cancelled` |
| `page` | integer | 1 | Page number |
| `page_size` | integer | 20 | Results per page (max 50) |

**Response** `200 OK`:
```json
{
  "rides": [ /* Ride Object array */ ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

---

## 3. Get Ride Detail

### GET /api/v1/rides/{ride_id}

Return a single ride with its full history log.

**Response** `200 OK`:
```json
{
  "ride": { /* Ride Object */ },
  "history": [
    {
      "id": "uuid",
      "actor_id": "uuid",
      "action": "created",
      "changed_fields": null,
      "reason": null,
      "created_at": "2026-06-17T10:00:00Z"
    },
    {
      "id": "uuid",
      "actor_id": "uuid",
      "action": "edited",
      "changed_fields": {
        "price_per_seat": { "before": "50.00", "after": "45.00" }
      },
      "reason": null,
      "created_at": "2026-06-17T11:30:00Z"
    }
  ]
}
```

- `403` — ride belongs to another driver
```json
{ "error": "ride_not_found", "message": "Ride not found." }
```

---

## 4. Edit Ride

### PATCH /api/v1/rides/{ride_id}

Update one or more editable fields on a `scheduled` ride. Only include fields to change.

**Request** (all fields optional):
```json
{
  "destination": {
    "coordinates": { "lat": 30.0626, "lng": 31.2497 },
    "address": "Heliopolis, Cairo"
  },
  "departure_datetime": "2026-06-18T09:00:00Z",
  "total_seats": 2,
  "price_per_seat": "40.00",
  "notes": "Updated note"
}
```

**Responses**:
- `200 OK` — updated ride returned
- `400` — validation error (same codes as create)
- `403` — not the ride owner
- `409` — ride is not `scheduled`
```json
{ "error": "ride_not_editable", "message": "Only scheduled rides can be edited." }
```

---

## 5. Cancel Ride

### POST /api/v1/rides/{ride_id}/cancel

Cancel a `scheduled` ride. Reason is mandatory.

**Request**:
```json
{ "reason": "Change of plans, no longer making this trip." }
```

**Responses**:
- `200 OK` — cancelled ride returned
- `400` — missing reason
```json
{ "error": "reason_required", "message": "A cancellation reason is required." }
```
- `409` — ride is not `scheduled`
```json
{ "error": "ride_not_editable", "message": "Only scheduled rides can be cancelled." }
```

---

## 6. Start Ride

### POST /api/v1/rides/{ride_id}/start

Mark a `scheduled` ride as `in_progress`. Only allowed at or after the departure time.

**Request**: empty body `{}`

**Responses**:
- `200 OK` — updated ride (status: `in_progress`) returned
- `409` — not yet departure time
```json
{ "error": "start_too_early", "message": "You can only start this ride at or after its scheduled departure time." }
```
- `409` — ride not in `scheduled` status
```json
{ "error": "ride_not_editable", "message": "Only scheduled rides can be started." }
```

---

## 7. Complete Ride

### POST /api/v1/rides/{ride_id}/complete

Mark an `in_progress` ride as `completed`.

**Request**: empty body `{}`

**Responses**:
- `200 OK` — updated ride (status: `completed`) returned
- `409` — ride not `in_progress`
```json
{ "error": "ride_not_editable", "message": "Only in-progress rides can be completed." }
```

---

## 8. Internal — Driver Revocation Webhook

### POST /api/v1/internal/driver-revocation

Called by Supabase Database Webhook when a driver's verification status or vehicle is revoked. Not accessible to clients.

**Auth**: `X-Webhook-Secret: {shared_secret}` header (value stored in Supabase Vault).

**Request**:
```json
{
  "driver_id": "uuid",
  "revocation_type": "identity"
}
```

`revocation_type`: `"identity"` (user verification_status changed) | `"vehicle"` (vehicle active set to false)

**Response** `200 OK`:
```json
{
  "cancelled_rides": 2,
  "notification_emails_queued": 0
}
```

- `401` — missing or invalid webhook secret
- `404` — driver not found
