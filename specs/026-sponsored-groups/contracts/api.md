# Phase 1 API Contract: Sponsored Groups

All endpoints require an authenticated session (`get_current_user`). Admin-facing endpoints additionally require `get_current_admin`. Error shape follows the existing platform convention: `{ "error": "<snake_case_code>", "message": "<human readable>" }`.

## Admin: Sponsored Group Management

Base path: `/api/admin/sponsored-groups` (new router, mounted alongside `admin_wallet_topup_router`).

### `POST /api/admin/sponsored-groups` — Create or auto-upgrade a sponsored group **[admin]**
Request: `{ domain: string, name?: string, funded_balance_egp: string, requested_group_type: 'company'|'university' }`
Behavior: if no group exists for `domain`, create a new one with `is_sponsored = true` and the given `funded_balance_egp`. If a non-sponsored group already exists for `domain`, auto-upgrade it in place — set `is_sponsored = true` and `funded_balance_egp` to the entered amount — instead of creating a second record (FR-003, clarification #1). If a sponsored group already exists for `domain`, `409 { error: "already_sponsored" }`.
Response `201`/`200`: full group object including `is_sponsored`, `funded_balance_egp`.
→ FR-001, FR-002, FR-003

### `POST /api/admin/sponsored-groups/{group_id}/add-funds` — Top up a sponsored group's balance **[admin]**
Request: `{ amount_egp: string }` (must be `> 0.00`).
Response `200`: `{ group_id, new_funded_balance_egp }`.
Errors: `404` unknown group, `422` group is not sponsored.

### `POST /api/admin/sponsored-groups/{group_id}/dashboard-contact` — Designate or reassign the dashboard contact **[admin]**
Request: `{ user_id: string }`. Target must already be a domain-verified member of this group (clarification #3, research.md §12).
Response `200`: `{ group_id, dashboard_contact_user_id }`.
Errors: `422 { error: "not_a_group_member" }` if the target hasn't joined yet, `404` unknown group.
→ FR-020

## Company Dashboard (read-only)

### `GET /api/groups/{group_id}/sponsorship-dashboard` — Read-only sponsorship summary **[dashboard contact only]**
Response `200`: `{ funded_balance_egp: string, member_count: int, recent_activity: [{ type: 'SPONSORED_RIDE_CREDIT'|'SPONSORED_RIDE_REVERSAL', amount_egp: string, ride_id: string, booking_id: string, created_at: string }] }`.
Errors: `403` caller is not this group's `dashboard_contact_user_id`, `404` group not found or not sponsored.
→ research.md §13

## Booking (existing endpoint, extended behavior — no new route)

### Existing `POST /api/v1/bookings` — sponsored settlement branch
When the target ride's group is sponsored, booking creation additionally (research.md §4, in the same transaction as the existing seat claim):
- Debits `groups.funded_balance_egp` by the seat price; rejects with `422 { error: "insufficient_funded_balance" }` if the balance can't cover it (FR-008) — no seats are claimed on this path.
- Credits the driver's wallet with the net-of-commission amount and records a `SPONSORED_RIDE_CREDIT` ledger entry.
- Sets the booking's `payment_source = 'SPONSORED'`.

No new request/response fields — a booking response for a sponsored booking is shaped identically to a cash one, since the client never chooses `payment_source` (clarification #2: always automatic).

## Driver Withdrawal Requests

Base path: `/api/wallet/withdrawals` (new router, mirrors `wallet_topup_router`'s shape in reverse).

### `POST /api/wallet/withdrawals` — Submit a withdrawal request **[driver]**
Request: `{ amount_egp: string, payout_reference: string }`
Behavior: rejects if `amount_egp` exceeds the driver's available balance (`balance_egp - reserved_egp`), or if the driver already has a `PENDING` request (`409 { error: "pending_request_exists" }`, FR-011/clarification #4, DB-enforced per research.md §9).
Response `201`: `{ id, status: 'PENDING', amount_egp, payout_reference, created_at }`.
→ FR-011

### `GET /api/wallet/withdrawals` — Driver's own withdrawal history **[driver]**
Query: `page?`
Response `200`: `{ items: [...], pagination: {...} }` — same shape as `GET /api/wallet/topup/history` (`wallet_topup_service.list_driver_history`), reversed direction.

## Admin: Withdrawal Review

Base path: `/api/admin/withdrawal-requests` (new router, mirrors `admin_wallet_topup_router` exactly).

### `GET /api/admin/withdrawal-requests` — Pending queue, oldest-first **[admin]**
Response `200`: `{ total, page, items: [{ id, driver_id, driver_name, driver_email, amount_egp, payout_reference, created_at }] }`.

### `GET /api/admin/withdrawal-requests/history` — Reviewed requests **[admin]**
Query: `page?`, `outcome?: 'APPROVED'|'REJECTED'`, `q?`
Response `200`: same shape as `wallet_topup_service.list_review_history`.

### `POST /api/admin/withdrawal-requests/{request_id}/approve` — Approve **[admin]**
Behavior: re-validates the driver's available balance under a wallet row lock at approval time (research.md §10) — `409 { error: "insufficient_balance_at_approval" }` if it no longer covers `amount_egp`. On success, debits the wallet, inserts a `WITHDRAWAL_DEBIT` ledger entry, sets `status = 'APPROVED'`.
Response `200`: `{ id, status, ledger_entry_id, new_balance_egp, reviewed_by, reviewed_at }`.

### `POST /api/admin/withdrawal-requests/{request_id}/reject` — Reject **[admin]**
Request: `{ reason: string }` (required, mirrors top-up rejection).
Response `200`: `{ id, status: 'REJECTED', rejection_reason, reviewed_by, reviewed_at }`.
