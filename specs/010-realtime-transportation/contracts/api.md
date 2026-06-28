# API Contracts: Real-Time Transportation

**Feature**: `010-realtime-transportation` | **Date**: 2026-06-28

All endpoints are prefixed `/api/v1`. All requests require a valid Supabase Auth JWT in the `Authorization: Bearer <token>` header. Authentication errors return `HTTP 401`. Authorization errors return `HTTP 403`. Validation errors return `HTTP 422`.

---

## Device Token Registration

### `POST /api/v1/users/me/device-tokens`

Register or refresh an FCM device token for the authenticated user. Idempotent: if the token already exists (for any user), `last_seen_at` is updated and the token is re-associated with the current user.

**Auth**: Any authenticated user (passenger or driver, any verification status).

**Request**:
```json
{
  "token": "fcm_registration_token_string",
  "platform": "web"
}
```

`platform` must be one of: `"web"`, `"android"`, `"ios"`.

**Response `200 OK`**:
```json
{
  "token_id": "uuid",
  "user_id": "uuid",
  "platform": "web",
  "last_seen_at": "2026-06-28T10:00:00Z"
}
```

**Error `422 Unprocessable Entity`**: `platform` value not in allowed set.

---

## Ride Lifecycle

### `POST /api/v1/rides/{ride_id}/start`

Start a scheduled ride. Transitions ride from `scheduled` → `in_progress`, records `started_at`, and inserts `ride_started` notification events for all confirmed passengers.

**Auth**: Verified driver who owns the ride. Returns `HTTP 403` for all other authenticated users.

**Request**: Empty body `{}`.

**Response `200 OK`**:
```json
{
  "ride": {
    "id": "uuid",
    "status": "in_progress",
    "started_at": "2026-06-28T08:00:00Z",
    "completed_at": null,
    ...
  }
}
```

The `ride` object shape is the same as the existing `GET /rides/{id}` response, extended with `started_at` and `completed_at` nullable fields.

**Error `409 Conflict`**: Ride is not in `scheduled` status. Body:
```json
{
  "error": "ride_not_editable",
  "message": "Only scheduled rides can be started.",
  "current_status": "in_progress"
}
```

**Error `409 Conflict`**: Ride departure time is in the future (existing guard in `ride_service.py`).

---

### `POST /api/v1/rides/{ride_id}/complete`

Complete an in-progress ride. Within a single database transaction: transitions ride to `completed`, records `completed_at`, executes Phase 6 booking completion cascade, and inserts `ride_completed` notification events for all passengers whose bookings were just completed.

**Auth**: Verified driver who owns the ride.

**Request**: Empty body `{}`.

**Response `200 OK`**:
```json
{
  "ride": {
    "id": "uuid",
    "status": "completed",
    "started_at": "2026-06-28T08:00:00Z",
    "completed_at": "2026-06-28T08:52:00Z",
    ...
  }
}
```

**Error `409 Conflict`**: Ride is not in `in_progress` status.
```json
{
  "error": "ride_not_editable",
  "message": "Only in-progress rides can be completed.",
  "current_status": "scheduled"
}
```

**Error `500 Internal Server Error`**: Transaction rollback — ride remains `in_progress`, no booking cascade fired (FR-019). Driver should retry.

---

## Driver Location

### `POST /api/v1/rides/{ride_id}/location`

Report the driver's current GPS position. Upserts into `driver_locations` (one record per ride, updated in place). The upsert triggers a Supabase Realtime UPDATE broadcast to subscribed confirmed passengers.

**Auth**: The ride's assigned driver only. All other users receive `HTTP 403`.

**Request**:
```json
{
  "lat": 30.0444,
  "lng": 31.2357,
  "bearing": 145,
  "speed_kmh": 42.5,
  "client_timestamp": "2026-06-28T08:15:30Z"
}
```

- `bearing`: optional integer 0–359. Omit or send `null` when device is stationary or bearing unavailable.
- `speed_kmh`: optional float. Stored for future analytics; not returned in GET responses.
- `client_timestamp`: ISO 8601 string, device-side time of GPS fix.

**Response `200 OK`**:
```json
{
  "location_id": "uuid",
  "ride_id": "uuid",
  "updated_at": "2026-06-28T08:15:30Z"
}
```

**Error `409 Conflict`**: Ride is not in `in_progress` status (FR-021).
```json
{
  "error": "ride_not_active",
  "message": "Location updates are only accepted for rides in progress."
}
```

---

### `GET /api/v1/rides/{ride_id}/location`

Retrieve the driver's most recently reported GPS position for an active or recently completed ride.

**Auth**: Passengers with a `confirmed` booking on this ride. All other users (including authenticated users without a confirmed booking) receive `HTTP 403`.

**Response `200 OK`**:
```json
{
  "ride_id": "uuid",
  "lat": 30.0444,
  "lng": 31.2357,
  "bearing": 145,
  "client_timestamp": "2026-06-28T08:15:30Z",
  "updated_at": "2026-06-28T08:15:30Z"
}
```

`bearing` is `null` when the driver is stationary. `speed_kmh` is intentionally omitted from this response.

**Error `404 Not Found`**: No location record exists for this ride yet (driver has not reported position).

**Error `403 Forbidden`**: Caller does not have a `confirmed` booking on this ride.

---

## Error Response Shape (all endpoints)

```json
{
  "error": "machine_readable_code",
  "message": "Human-readable description"
}
```

New Phase 7 error codes:

| Code | HTTP | Meaning |
|------|------|---------|
| `ride_not_active` | 409 | Location update rejected — ride not in `in_progress` |
| `ride_not_editable` | 409 | Start/complete rejected — wrong current status |
| `location_not_found` | 404 | No location record exists for this ride |
| `fcm_credentials_unavailable` | 503 | Firebase service account could not be loaded at startup (startup failure, not a runtime error) |
