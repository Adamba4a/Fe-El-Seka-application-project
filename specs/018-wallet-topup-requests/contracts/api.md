# API Contracts: Manual Wallet Top-Up via Vodafone Cash

**Branch**: `018-wallet-topup-requests` | **Date**: 2026-08-08

All endpoints require a valid Supabase Auth JWT (`Authorization: Bearer <token>`). Unauthenticated
requests return HTTP 401. Role enforcement is noted per endpoint. All monetary values are decimal
strings (`"200.00"`), matching `011-financial-system`'s convention.

---

## Driver-facing endpoints (`services/api/app/api/wallet_topup/router.py`)

### GET /wallet/topup/settings

Return the platform's current Vodafone Cash number for display on the request form (FR-001).

**Auth**: Any authenticated driver.

**Response 200**:
```json
{ "vodafone_cash_number": "01012345678" }
```

---

### POST /wallet/topup

Submit a new top-up request (US1, FR-002/FR-003).

**Auth**: Driver role required (`get_current_driver`). Returns HTTP 403 for non-drivers.

**Request Body** (`multipart/form-data`):
| Field | Type | Description |
|---|---|---|
| `amount_egp` | decimal string | Required, > 0 |
| `payment_reference` | string | Required, non-empty |
| `screenshot` | file | Required, JPEG or PNG, ≤10 MB |

**Response 201**:
```json
{
  "id": "uuid",
  "status": "PENDING",
  "amount_egp": "200.00",
  "payment_reference": "TXN123456",
  "created_at": "2026-08-08T10:00:00Z"
}
```

**Error responses**:
| Status | `error` | Condition |
|---|---|---|
| 422 | `validation_error` | Zero/negative/missing `amount_egp`, missing `payment_reference`, missing/invalid screenshot (FR-003) |
| 403 | `submission_locked` | Driver has 3 `REJECTED` outcomes in the current cycle (FR-014/FR-015); body includes `support_email` |
| 409 | `pending_request_exists` | Driver already has a `PENDING` request (FR-004); body includes the existing request's `id` and `amount_egp` |
| 409 | `duplicate_payment_reference` | `payment_reference` matches another `PENDING`/`APPROVED` request (FR-005); `error_code = DUPLICATE_PAYMENT_REFERENCE` |

---

### GET /wallet/topup

List the authenticated driver's own top-up requests, newest-first (US3, FR-006).

**Auth**: Driver role required.

**Query Parameters**: `page` (default 1), `per_page` (default 20, max 50).

**Response 200**:
```json
{
  "items": [
    {
      "id": "uuid",
      "amount_egp": "200.00",
      "payment_reference": "TXN123456",
      "status": "REJECTED",
      "rejection_reason": "Screenshot unreadable",
      "created_at": "2026-08-07T09:00:00Z",
      "reviewed_at": "2026-08-07T11:00:00Z"
    }
  ],
  "pagination": { "page": 1, "per_page": 20, "total_entries": 1, "total_pages": 1 },
  "is_locked": false
}
```

---

### POST /wallet/topup/{request_id}/cancel

Cancel the driver's own `PENDING` request (US3, FR-007).

**Auth**: Driver role required; the request must belong to the caller (else 403, FR-006).

**Response 200**:
```json
{ "id": "uuid", "status": "CANCELLED" }
```

**Error responses**:
| Status | `error` | Condition |
|---|---|---|
| 403 | `forbidden` | Request belongs to another driver |
| 409 | `not_cancellable` | Request is not `PENDING` |

---

## Admin endpoints (`services/api/app/api/admin/wallet_topup_router.py`)

### GET /admin/wallet-topup-requests

List `PENDING` requests, oldest-first (US2, FR-008).

**Auth**: Admin role required (`get_current_admin`). Returns HTTP 403 for non-admins.

**Query Parameters**: `page` (default 1), `limit` (default 20).

**Response 200**:
```json
{
  "total": 3,
  "page": 1,
  "items": [
    {
      "id": "uuid",
      "driver_id": "uuid",
      "driver_name": "Ahmed Hassan",
      "driver_phone": "+201012345678",
      "amount_egp": "200.00",
      "payment_reference": "TXN123456",
      "screenshot_url": "https://.../signed-url",
      "created_at": "2026-08-08T10:00:00Z"
    }
  ]
}
```

---

### GET /admin/wallet-topup-requests/history

List already-reviewed (`APPROVED`/`REJECTED`) requests, newest-first, so an admin can find a
currently-locked driver to unlock (FR-016) without needing the driver's ID out-of-band — mirrors
`GET /admin/verification/history`.

**Auth**: Admin role required.

**Query Parameters**: `page` (default 1), `outcome` (optional, `APPROVED` | `REJECTED`), `q` (optional, driver name/phone search).

**Response 200**:
```json
{
  "total": 12,
  "page": 1,
  "items": [
    {
      "request_id": "uuid",
      "driver_id": "uuid",
      "driver_name": "Ahmed Hassan",
      "amount_egp": "200.00",
      "status": "REJECTED",
      "rejection_reason": "Screenshot unreadable",
      "reviewed_by": "admin-uuid",
      "reviewed_at": "2026-08-07T11:00:00Z",
      "driver_is_locked": true
    }
  ]
}
```

---

### POST /admin/wallet-topup-requests/{request_id}/approve

Approve a `PENDING` request; credits the driver's wallet atomically (US2, FR-009, NFR-006).

**Auth**: Admin role required.

**Response 200**:
```json
{
  "id": "uuid",
  "status": "APPROVED",
  "ledger_entry_id": "uuid",
  "new_balance_egp": "247.50",
  "reviewed_by": "admin-uuid",
  "reviewed_at": "2026-08-08T10:05:00Z"
}
```

**Error responses**:
| Status | `error` | Condition |
|---|---|---|
| 404 | `not_found` | No such request |
| 409 | `conflict` | Request is not `PENDING` (FR-011) |

---

### POST /admin/wallet-topup-requests/{request_id}/reject

Reject a `PENDING` request; no wallet change (US2, FR-010).

**Auth**: Admin role required.

**Request Body**:
```json
{ "reason": "No matching transfer found for this reference" }
```

**Response 200**:
```json
{
  "id": "uuid",
  "status": "REJECTED",
  "rejection_reason": "No matching transfer found for this reference",
  "reviewed_by": "admin-uuid",
  "reviewed_at": "2026-08-08T10:05:00Z",
  "driver_locked": false
}
```

**Error responses**:
| Status | `error` | Condition |
|---|---|---|
| 400 | `validation_error` | Missing/empty `reason` (FR-010) |
| 404 | `not_found` | No such request |
| 409 | `conflict` | Request is not `PENDING` (FR-011) |

---

### POST /admin/wallet-topup-requests/drivers/{driver_id}/unlock

Unlock a submission-locked driver, resetting their cap cycle (FR-016).

**Auth**: Admin role required.

**Response 200**:
```json
{ "driver_id": "uuid", "is_topup_locked": false }
```

**Error responses**:
| Status | `error` | Condition |
|---|---|---|
| 404 | `not_found` | No such driver |
| 409 | `conflict` | Driver is not currently locked |

---

## Performance (NFR-001, NFR-004)

All endpoints above: p95 < 500ms under ≤1,000 active users. `GET /admin/wallet-topup-requests`: < 2s
render for up to 500 pending items.
