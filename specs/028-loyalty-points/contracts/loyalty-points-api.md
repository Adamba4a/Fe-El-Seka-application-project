# API Contract: Loyalty Points

**Feature**: [spec.md](../spec.md) | **Data Model**: [data-model.md](../data-model.md)

All endpoints under `services/api` (FastAPI), auth via existing `get_current_user`/`get_current_passenger`/`get_current_driver`/`get_current_admin` dependencies. Errors follow the existing `{"error": "...", "message": "..."}` envelope with standard status codes (401/403/404/409).

## Passenger & Driver (shared shape, role resolved from the authenticated user)

### `GET /api/v1/loyalty/balance`
Returns the caller's points balance for their current role.
- Auth: `get_current_passenger` or `get_current_driver` (role read from `profile["role"]`)
- Response: `{ "account_id": uuid, "role": "passenger"|"driver", "balance": int }`

### `GET /api/v1/loyalty/transactions?page=1`
Paginated ledger history (FR-016), newest-first, mirrors `wallet_service.get_ledger_page`.
- Response: `{ "items": [{ "id", "delta", "reason", "balance_after", "ride_id", "booking_id", "redemption_request_id", "created_at" }], "total": int, "page": int }`

### `GET /api/v1/loyalty/catalog`
Browse redeemable rewards for the caller's role (`audience IN (role, 'both')`, `active = true`).
- Response: `{ "items": [{ "id", "type", "title", "description", "point_cost", "fulfillment_mode" }] }`

### `POST /api/v1/loyalty/catalog/{catalog_entry_id}/redeem`
Redeem a `voucher` or `car_maintenance` catalog entry (i.e. anything **not** `free_ride`/`discount` — those redeem inline at booking, see below). Points deducted immediately (FR-011); `instant` entries resolve `fulfilled` synchronously, `manual` entries return `pending`.
- 409 if `catalog_entry.type IN ('free_ride','discount')` — use the booking-creation flow instead.
- 409 if insufficient balance.
- Response: `{ "redemption_request_id", "status": "fulfilled"|"pending", "points_spent", "balance_after" }`

## Passenger booking-time redemption (extends existing booking creation)

### `POST /api/v1/rides/{ride_id}/bookings` (existing endpoint, extended)
New optional request field: `loyalty_redemption_catalog_entry_id: uuid | null`.
- When present, must reference an `active` `free_ride` or `discount` entry with `audience IN ('passenger','both')`.
- Rejected (409, `loyalty_redemption_conflict`) if the ride/booking already carries a sponsored-group discount (FR-005a).
- Rejected (409, `insufficient_points`) if balance < `point_cost`.
- On success, within the same transaction as booking creation: deduct points, insert a `fulfilled` `loyalty_redemption_requests` row (`ride_id`/`booking_id` set), and apply the fare adjustment — `free_ride` caps the passenger's payable fare at `loyalty_free_ride_max_fare_egp` (passenger pays any amount above the cap), `discount` reduces the fare by `loyalty_discount_percentage`.
- Response: existing booking response, plus `loyalty_redemption: { redemption_request_id, points_spent, fare_after_discount_egp } | null`.

## Admin

### `GET /api/v1/admin/loyalty/queue?page=1&limit=20`
Pending manual-fulfillment redemptions (`car_maintenance` + manually-flagged vouchers), oldest-first — generalizes `GET /api/v1/admin/car-maintenance`.
- Auth: `get_current_admin`
- Response: `{ "total", "page", "items": [{ "id", "user_id", "user_name", "user_email", "role", "catalog_entry": { "type", "title" }, "points_spent", "created_at" }] }`

### `POST /api/v1/admin/loyalty/queue/{redemption_request_id}/fulfill`
Marks a `pending` request `fulfilled`. No balance mutation (points already deducted at submission). Writes `admin_audit_logs` (`action_type='approved'`, `redemption_request_id` set) — generalizes `car_maintenance_router.fulfill_reward`.
- 404 if not found, 409 if not `pending`.
- Response: `{ "id", "status", "fulfilled_by", "fulfilled_at" }`

### `POST /api/v1/admin/loyalty/queue/{redemption_request_id}/reject`
Marks a `pending` request `rejected`, refunds `points_spent` back to the account via a `redemption_refund` transaction (FR-012). Writes `admin_audit_logs` (`action_type='rejected'`, `redemption_request_id` set).
- Body: `{ "reason": string }`
- Response: `{ "id", "status", "fulfilled_by", "fulfilled_at" }`

### `GET /api/v1/admin/loyalty/catalog` / `POST` / `PATCH /{id}` / `DELETE /{id}` (retire, not hard-delete)
Full CRUD for `voucher` entries; `PATCH` only (no create/delete) for the 3 system entries, restricted to `point_cost` and — for `free_ride`/`discount` — the paired `platform_settings` value (`loyalty_free_ride_max_fare_egp` / `loyalty_discount_percentage`). Generalizes the (currently nonexistent) car-maintenance catalog into an editable one.
- `DELETE` sets `active = false` (soft retirement — a redemption in flight for a retired entry still resolves per data-model.md edge case).

## Internal (not HTTP — service-layer hooks)

- `loyalty_service.award_passenger_points(conn, account_id, booking_id, ride_id, fare_paid_egp)` — called from `booking_service.complete_ride_bookings()` per booking (FR-001).
- `loyalty_service.award_driver_points(conn, driver_id, wallet_id, distance_fee_amount)` — replaces `car_maintenance_service.accumulate_and_maybe_grant()`, called from `commission_service.deduct_commission()` (FR-002).
- `loyalty_service.reverse_points(conn, account_id, ride_id, booking_id, points)` — called from ride/booking cancellation, refund, and fraud-flagging paths (FR-014), `GREATEST(balance - points, 0)` floor.
