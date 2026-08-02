# Phase 1 Contracts: Admin Operations (Full) REST Endpoints

All endpoints are FastAPI routes, admin-only via the existing `get_current_admin` dependency
(`app/dependencies/roles.py`) — every non-admin caller receives `403 forbidden` (FR-022, NFR-005).
Error shape follows the existing `{"error": "<code>", "message": "<text>"}` convention.

## Dashboard — `app/api/admin/dashboard_router.py` (new), prefix `/api/admin/dashboard`

### `GET /overview`

Platform KPIs + trend series for a selectable period (FR-001–004).

**Query params**: `period` = `today | 7d | 30d | 90d` (default `7d`)

**Response**:
```json
{
  "period": "7d",
  "users_by_role": { "passenger": 0, "driver": 0, "admin": 0 },
  "rides_created": 0,
  "rides_completed": 0,
  "commission_collected_egp": "0.00",
  "pending_verifications": 0,
  "open_reports": 0,
  "drivers_at_or_below_zero": 0,
  "trends": {
    "rides_completed": { "granularity": "day", "points": [ { "date": "2026-07-27", "value": 0 } ] },
    "commission_collected_egp": { "granularity": "day", "points": [ { "date": "2026-07-27", "value": "0.00" } ] }
  }
}
```
- `400 validation_error` — `period` not one of the four allowed values
- All counts/sums zero and both trend series zero-filled (never omitted days) for a period with no
  activity (Acceptance Scenario 6)

## User Management — `app/api/admin/users_router.py` (extended)

### `GET /` *(new)*

Search/filter/paginate the user list (FR-005–007).

**Query params**: `q` (matches `display_name` or `email`, `ILIKE '%q%'`), `role` (`passenger|driver|admin`),
`status` (`unverified|pending_review|verified|rejected|suspended`), `page` (default 1), `limit`
(default 20, max 100)

**Response**:
```json
{
  "total": 0, "page": 1,
  "items": [ {
    "user_id": "uuid", "display_name": "...", "email": "...", "role": "passenger",
    "verification_status": "verified", "created_at": "..."
  } ]
}
```
Zero-match search returns `{"total": 0, "page": 1, "items": []}`, not an error (spec Edge Cases).

### `GET /{user_id}` *(new)*

Unified per-user detail view (FR-008).

**Response**:
```json
{
  "profile": { "user_id": "uuid", "display_name": "...", "email": "...", "role": "driver",
               "verification_status": "verified", "created_at": "...", "is_admin_role": false },
  "rides": [ { "ride_id": "uuid", "status": "completed", "created_at": "..." } ],
  "bookings": [ { "booking_id": "uuid", "status": "completed", "created_at": "..." } ],
  "ratings_received": { "rating_avg": 4.8, "rating_count": 12, "items": [ { "stars": 5, "comment": "...", "created_at": "..." } ] },
  "reports": { "filed_by_user": [ { "report_id": "uuid", "status": "open", "created_at": "..." } ],
               "filed_against_user": [ ] },
  "wallet": { "balance_egp": "120.00", "available_egp": "100.00", "recent_ledger": [ ] }
}
```
- `rides` populated only when `role == 'driver'`; `bookings` only when `role == 'passenger'`; `wallet`
  only when `role == 'driver'` (else omitted entirely, not `null`)
- `404 not_found` — user does not exist
- Each section renders its own empty state on the frontend when its array/object is empty (spec
  Acceptance Scenario 8) — the backend returns empty arrays/zeroed aggregates, not `404`s per-section

### `POST /{user_id}/suspend` *(extended)*

Unchanged request/response shape from the existing endpoint. **New precondition**: rejects before
the existing `verification_status` check.

**Responses** (new, in addition to the existing `400`/`404`/`409`):
- `403 forbidden` — `{"error": "forbidden", "message": "Admin-role accounts cannot be suspended through this mechanism"}` when the target user's `role == 'admin'` (FR-009, Acceptance Scenario 9). Checked even when `user_id` is the acting admin's own id.

### `POST /{user_id}/reinstate`

Unchanged — no modification needed (FR-010, FR-011).

## Enhanced Verification Queue — `app/api/admin/verification_router.py` (extended)

### `GET /queue` *(extended)*

**New query params**: `q` (matches joined `profiles.display_name`/`email`, `ILIKE`)

**Response** — existing shape, each item gains:
```json
{ "pending_seconds": 12345, "is_aged": false }
```
`is_aged = pending_seconds > 86400` (FR-012).

### `GET /history` *(extended)*

**New query params**: `q` (same search), `outcome` = `approved | rejected` (FR-013, FR-014)

### `POST /{submission_id}/approve`, `POST /{submission_id}/reject`, `POST /users/{user_id}/unlock`

Unchanged (FR-015, FR-016) — reused as-is from `003-auth-verification`, only newly reachable from the
enhanced queue/history UI.

## Financial Reporting — `app/api/admin/financial_router.py` (new), prefix `/api/admin/financial`

### `GET /report`

Aggregate revenue/commission report for a date range (FR-017, FR-018).

**Query params**: `start` (date, required), `end` (date, required, inclusive)

**Response**:
```json
{
  "range": { "start": "2026-07-01", "end": "2026-07-31" },
  "commission_collected_egp": "0.00",
  "admin_credits_egp": "0.00",
  "admin_debits_egp": "0.00",
  "net_revenue_egp": "0.00",
  "trend": { "granularity": "day", "points": [ { "date": "2026-07-01", "value": "0.00" } ] }
}
```
- `400 validation_error` — `end` before `start`, or either param missing/malformed
- `trend.granularity` is `"week"` when `(end - start) > 60 days`, else `"day"` (FR-018)
- All-zero response with an empty (zero-filled) trend for a range with no ledger activity (Acceptance
  Scenario 6)

### `GET /report/export`

Same `start`/`end` params as `GET /report`. Returns `StreamingResponse` (`media_type="text/csv"`,
`Content-Disposition: attachment; filename="financial_report_<start>_<end>.csv"`). Row totals are
byte-for-byte derived from the same `financial_report_service.get_report()` call `GET /report` uses —
no separate code path that could drift (FR-020, Acceptance Scenario 5). No file is written to disk or
Supabase Storage (NFR-007).

### `GET /drivers/balances`

Driver balance overview, sorted ascending by available balance (FR-019, FR-021).

**Response**:
```json
{
  "items": [ {
    "driver_id": "uuid", "display_name": "...", "balance_egp": "0.00",
    "reserved_egp": "0.00", "available_egp": "0.00", "is_at_risk": true
  } ]
}
```
Includes every profile with `role = 'driver'`, even those with no `driver_wallets` row (`balance_egp`/
`reserved_egp`/`available_egp` all `"0.00"`, `is_at_risk: true`) — FR-021.
