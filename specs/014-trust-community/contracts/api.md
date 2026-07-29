# Phase 1 Contracts: Trust & Community REST Endpoints

All endpoints are FastAPI routes under `services/api/app/api/`. Auth follows existing project
convention: bearer JWT validated via existing `get_current_user`/`get_current_admin` dependencies.
Error shape follows the existing `{"error": "<code>", "message": "<text>"}` convention used by
`verification_router.py`.

## Ratings — `app/api/ratings/router.py`

### `POST /ratings`

Submit a rating for a completed booking (FR-001–FR-005, FR-011).

**Request**:
```json
{ "booking_id": "uuid", "stars": 1-5, "comment": "string | null" }
```

**Responses**:
- `201` — `{ "rating_id": "uuid", "booking_id": "uuid", "revealed": false }`
- `400 validation_error` — stars out of range, comment exceeds 500 chars
- `403 authorization_error` — caller was not a party to the booking (FR-004)
- `404 not_found` — booking does not exist
- `409 conflict` — booking not `completed` (FR-003), duplicate rating for this direction (FR-005), or
  more than 14 days since ride completion (FR-011)

### `GET /profiles/{user_id}/rating`

Own aggregate + anonymized comments (FR-006, FR-007, FR-010). Callable only for `user_id == caller`.

**Response**:
```json
{
  "rating_avg": 4.8,
  "rating_count": 12,
  "comments": [ { "comment": "Great driver!", "created_at": "..." } ]
}
```
`rating_avg: null` when `rating_count == 0` ("not yet rated", FR-010). `comments` excludes any rater
identity and excludes any not-yet-revealed rating (FR-007, FR-008).

## Reports — `app/api/reports/router.py`

### `POST /reports`

Submit a safety report (FR-012–FR-015).

**Request**:
```json
{
  "ride_id": "uuid",
  "booking_id": "uuid",
  "reported_user_id": "uuid",
  "category": "unsafe_driving | harassment | no_show | fraud_or_scam | vehicle_mismatch | other",
  "description": "string"
}
```

**Responses**:
- `201` — `{ "report_id": "uuid", "status": "open" }`
- `400 validation_error` — missing category/description (FR-014), or `description` exceeds 1000 chars
- `403 authorization_error` — reporter was not a party to the ride/booking, or `reported_user_id ==` caller (FR-013)
- `404 not_found` — ride/booking does not exist
- `409 conflict` — ride not `in_progress` or `completed` (FR-015)

### `GET /reports/mine`

Reporter's own report history, status only (FR-016).

**Response**: `{ "items": [ { "report_id": "uuid", "category": "...", "status": "...", "created_at": "..." } ] }`
— never includes `resolution_action`, `resolution_reason`, or `resolved_by`.

## Admin Moderation — `app/api/admin/moderation_router.py`

Mirrors `verification_router.py`'s shape and auth (`get_current_admin`).

### `GET /admin/moderation/queue`

Open/under-review reports, newest-first (FR-018).

**Query params**: `page`, `limit` (same pagination convention as `verification_router.get_queue`)

**Response**:
```json
{
  "total": 0, "page": 1,
  "items": [ {
    "report_id": "uuid", "category": "...", "description": "...",
    "reporter": { "user_id": "uuid", "display_name": "..." },
    "reported_user": { "user_id": "uuid", "display_name": "..." },
    "ride_id": "uuid", "status": "open", "created_at": "..."
  } ]
}
```

### `GET /admin/moderation/flagged`

Users auto-flagged by rating/report thresholds, advisory-only (FR-019).

**Response**: `{ "items": [ { "user_id": "uuid", "display_name": "...", "reason": "low_rating | report_count", "rating_avg": 2.4, "recent_report_count": 4 } ] }`

### `POST /admin/moderation/reports/{report_id}/review`

Transition a report to `under_review` (FR-020). `200` — `{ "report_id": "uuid", "status": "under_review" }`.

### `POST /admin/moderation/reports/{report_id}/resolve`

Resolve a report with an action (FR-021, FR-023, FR-025).

**Request**: `{ "action": "warn | suspend | dismiss", "reason": "string" }`

**Responses**:
- `200` — `{ "report_id": "uuid", "status": "resolved" | "dismissed", "action": "...", "audit_log_id": "uuid" }`
- `400 validation_error` — missing reason
- `404 not_found` — report does not exist
- `409 conflict` — report already `resolved`/`dismissed`

Side effects: `suspend` sets `profiles.verification_status = 'suspended'` (FR-021, FR-024); all three
actions append to `admin_audit_logs` with `report_id` set (FR-023) and enqueue a
`notification_events` row informing the affected user of the outcome without exposing reporter
identity (FR-025).

### `POST /admin/moderation/users/{user_id}/reinstate`

Reinstate a suspended user (FR-022).

**Request**: `{ "reason": "string" }`

**Responses**:
- `200` — `{ "user_id": "uuid", "new_status": "verified", "audit_log_id": "uuid" }`
- `400 validation_error` — missing reason
- `404 not_found` — user does not exist
- `409 conflict` — user is not currently `suspended`

Mirrors `verification_router.unlock_user`'s shape exactly, substituting the reinstate transition for
the unlock transition.
