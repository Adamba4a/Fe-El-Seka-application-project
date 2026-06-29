# API Contracts: Financial System (Phase 8)

**Branch**: `011-financial-system` | **Date**: 2026-06-29

All endpoints require a valid Supabase Auth JWT (`Authorization: Bearer <token>`). Unauthenticated requests return HTTP 401. Role enforcement is noted per endpoint.

---

## New Endpoints

### GET /drivers/me/wallet

Retrieve the authenticated driver's wallet summary and paginated ledger history.

**Auth**: Driver role required. Returns HTTP 403 for non-drivers.

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number (1-indexed) |
| `per_page` | integer | 50 | Entries per page; max 50 |

**Response 200**:
```json
{
  "balance_egp": "47.50",
  "reserved_egp": "8.00",
  "available_egp": "39.50",
  "entries": [
    {
      "id": "uuid",
      "type": "COMMISSION_DEBIT",
      "amount_egp": "2.00",
      "ride_id": "uuid",
      "booking_id": "uuid",
      "fuel_cost_egp_snapshot": "40.00",
      "created_by": null,
      "note": null,
      "created_at": "2026-06-29T14:23:00Z"
    },
    {
      "id": "uuid",
      "type": "ADMIN_CREDIT",
      "amount_egp": "100.00",
      "ride_id": null,
      "booking_id": null,
      "fuel_cost_egp_snapshot": null,
      "created_by": "admin-uuid",
      "note": "Initial top-up",
      "created_at": "2026-06-28T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total_entries": 7,
    "total_pages": 1
  }
}
```

**Response 200 (no wallet)**: `{ "balance_egp": "0.00", "reserved_egp": "0.00", "available_egp": "0.00", "entries": [], "pagination": { "page": 1, "per_page": 50, "total_entries": 0, "total_pages": 0 } }`

**Performance**: p95 < 200ms (NFR-002).

---

### POST /admin/drivers/{driver_id}/wallet/topup

Credit a driver's wallet with a specified amount. Admin-only.

**Auth**: Admin role required. Returns HTTP 403 for non-admins.

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `driver_id` | UUID | Target driver's user ID |

**Request Body**:
```json
{
  "amount_egp": "200.00",
  "note": "Bank transfer received 2026-06-29"
}
```
- `amount_egp`: Required. Must be > 0.00. Returns HTTP 422 if zero or negative.
- `note`: Optional free-text annotation (max 500 characters).

**Response 200**:
```json
{
  "wallet_id": "uuid",
  "driver_id": "uuid",
  "new_balance_egp": "247.50",
  "ledger_entry_id": "uuid",
  "amount_credited_egp": "200.00",
  "created_at": "2026-06-29T15:00:00Z"
}
```

**Response 422** (invalid amount):
```json
{
  "error_code": "INVALID_TOPUP_AMOUNT",
  "message": "Top-up amount must be greater than 0.00 EGP.",
  "detail": { "amount_egp": "0.00" }
}
```

**Response 404**: Driver not found or not a verified driver.

---

### POST /admin/drivers/{driver_id}/wallet/adjust

Apply a corrective debit to a driver's wallet to reverse an erroneous top-up. Admin-only. Capped at the driver's current available balance.

**Auth**: Admin role required. Returns HTTP 403 for non-admins.

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `driver_id` | UUID | Target driver's user ID |

**Request Body**:
```json
{
  "amount_egp": "50.00",
  "note": "Reversal — entered 250 instead of 200"
}
```
- `amount_egp`: Required. Must be > 0.00 and ≤ driver's available balance.
- `note`: Strongly recommended but optional.

**Response 200**:
```json
{
  "wallet_id": "uuid",
  "driver_id": "uuid",
  "new_balance_egp": "197.50",
  "new_available_egp": "197.50",
  "ledger_entry_id": "uuid",
  "amount_debited_egp": "50.00",
  "created_at": "2026-06-29T15:05:00Z"
}
```

**Response 422** (exceeds available balance):
```json
{
  "error_code": "DEBIT_EXCEEDS_AVAILABLE_BALANCE",
  "message": "Debit amount exceeds available balance. Maximum allowable debit is 39.50 EGP.",
  "detail": {
    "requested_egp": "50.00",
    "available_egp": "39.50",
    "balance_egp": "47.50",
    "reserved_egp": "8.00"
  }
}
```

---

## Extended Endpoints

### POST /rides/ (Phase 4 extension)

Ride creation now includes a balance check gate and reservation creation.

**New behaviour** (inserted before ride INSERT):
1. Compute `max_commission = ROUND(fuel_cost_egp × 0.20, 2)`
2. Acquire `SELECT FOR UPDATE` on `driver_wallets` for this driver (create wallet row if absent)
3. Check `available_egp >= max_commission`; if not → HTTP 422 `INSUFFICIENT_WALLET_BALANCE`
4. Insert ride AND `CommissionReservation` atomically; increment `wallet.reserved_egp`

**New error response (HTTP 422)**:
```json
{
  "error_code": "INSUFFICIENT_WALLET_BALANCE",
  "message": "Insufficient available balance for this ride. A shorter ride with a lower commission may be possible.",
  "detail": {
    "available_egp": "4.00",
    "required_commission_egp": "5.08",
    "balance_egp": "12.00",
    "reserved_egp": "8.00"
  }
}
```

All other ride creation behaviour (validation, OSRM, fare calculation) is unchanged.

---

### POST /rides/{id}/complete (Phase 7 extension)

Ride completion now includes commission settlement atomically.

**New behaviour** (inserted inside the completion transaction, after bookings transition to `completed`):
1. Delete the ride's `CommissionReservation`; decrement `wallet.reserved_egp` by `reserved_amount_egp`
2. For each booking that transitioned `confirmed → completed`: insert `COMMISSION_DEBIT` ledger entry with `amount_egp = ROUND(fuel_cost_egp × 0.20 / total_seat_count, 2)`; decrement `wallet.balance_egp` by that amount
3. If zero confirmed bookings: step 2 is skipped; reservation is still deleted

**No change to response shape** — ride completion returns the same ride object as Phase 7. The financial settlement is a side effect inside the transaction.

---

### POST /rides/{id}/cancel (Phase 4/6 extension)

Ride or booking cancellation now releases the associated `CommissionReservation` atomically.

**New behaviour** (inserted inside the cancellation transaction):
1. Delete the ride's `CommissionReservation` (if exists); decrement `wallet.reserved_egp`
2. No ledger entry is created

Applies to all cancellation paths: driver-initiated, system-initiated (expiry), and admin-initiated.

**No change to response shape**.

---

## Structured Log Fields (NFR-007)

Every wallet write emits a structured log entry at INFO level:

```json
{
  "event": "wallet_write",
  "operation": "COMMISSION_DEBIT | ADMIN_CREDIT | ADMIN_DEBIT | RESERVATION_CREATE | RESERVATION_RELEASE",
  "driver_id": "uuid",
  "amount_egp": "2.00",
  "ride_id": "uuid | null",
  "booking_id": "uuid | null",
  "admin_actor_id": "uuid | null",
  "duration_ms": 45,
  "error": null
}
```
