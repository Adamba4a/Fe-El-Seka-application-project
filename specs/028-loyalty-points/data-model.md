# Data Model: Loyalty Points

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

Generalizes `driver_wallets.car_maintenance_savings_egp` + `car_maintenance_rewards` (see research.md Decisions 1-2). All new tables live in `supabase/migrations/`, UUID primary keys per Constitution Data Standards.

## Entities

### `loyalty_points_accounts`

The points balance for one user in one role. Backs FR-003 (separate balances per role).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID NOT NULL REFERENCES profiles(id) | |
| `role` | `loyalty_account_role` ENUM (`passenger`, `driver`) | |
| `balance` | INTEGER NOT NULL DEFAULT 0 CHECK (`balance >= 0`) | Never negative (FR-010) |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

`UNIQUE (user_id, role)`. Row is created lazily (`INSERT ... ON CONFLICT DO NOTHING`) the same way `driver_wallets` rows are, via a `get_or_create_account()` / `get_account_with_lock()` pair mirroring `wallet_service.get_wallet_with_lock()`.

### `loyalty_points_transactions`

Immutable ledger entry for every balance change (FR-013). Append-only — never updated or deleted.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `account_id` | UUID NOT NULL REFERENCES loyalty_points_accounts(id) | |
| `delta` | INTEGER NOT NULL | Positive = earn/refund, negative = redeem/reversal |
| `reason` | `loyalty_transaction_reason` ENUM (`ride_completed_earn`, `redemption_spend`, `redemption_refund`, `ride_reversal_clawback`, `admin_adjustment`) | |
| `ride_id` | UUID NULL REFERENCES rides(id) | Set for earn/clawback entries |
| `booking_id` | UUID NULL REFERENCES bookings(id) | Set for earn/clawback entries |
| `redemption_request_id` | UUID NULL REFERENCES loyalty_redemption_requests(id) | Set for spend/refund entries |
| `balance_after` | INTEGER NOT NULL | Snapshot for auditability, matches `driver_ledger_entries` convention |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

Index: `(account_id, created_at DESC)` for history pagination (FR-016), mirroring `wallet_service.get_ledger_page()`.

### `loyalty_reward_catalog`

Redeemable rewards. Four fixed system entries (`free_ride`, `discount`, `car_maintenance`) are seeded via migration; admins additionally create/retire generic `voucher` entries (FR-007/FR-008).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `type` | `loyalty_reward_type` ENUM (`free_ride`, `discount`, `car_maintenance`, `voucher`) | |
| `title` | TEXT NOT NULL | |
| `description` | TEXT NOT NULL | |
| `audience` | `loyalty_audience` ENUM (`passenger`, `driver`, `both`) | |
| `point_cost` | INTEGER NOT NULL CHECK (`point_cost > 0`) | System entries' cost reads from `platform_settings` at seed/update time; generic vouchers set directly by admin |
| `fulfillment_mode` | `loyalty_fulfillment_mode` ENUM (`instant`, `manual`) | Default `instant` for `voucher`; always `manual` for `car_maintenance`; N/A stored as `instant` for `free_ride`/`discount` since they resolve inline at booking time (research.md Decision 4) |
| `active` | BOOLEAN NOT NULL DEFAULT true | Retired entries (FR edge case) hidden from catalog browse but still resolvable for in-flight redemptions |
| `created_by` | UUID NULL REFERENCES profiles(id) | NULL for the 3 seeded system entries |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

The 3 system entries (`type IN ('free_ride','discount','car_maintenance')`) are singleton rows — admin CRUD (FR-008a) edits their `point_cost` and the accompanying `platform_settings` cap/percentage in place; admin CRUD (FR-008) for `voucher` rows supports full create/edit/retire.

### `loyalty_redemption_requests`

Generalizes `car_maintenance_rewards`. One row per redemption attempt.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `account_id` | UUID NOT NULL REFERENCES loyalty_points_accounts(id) | |
| `catalog_entry_id` | UUID NOT NULL REFERENCES loyalty_reward_catalog(id) | |
| `points_spent` | INTEGER NOT NULL | Snapshot of `point_cost` at redemption time |
| `fulfillment_mode` | `loyalty_fulfillment_mode` ENUM | Snapshot from catalog entry at redemption time |
| `status` | `loyalty_redemption_status` ENUM (`pending`, `fulfilled`, `rejected`) | `instant` mode rows are inserted directly as `fulfilled`; `manual` mode rows start `pending` |
| `ride_id` | UUID NULL REFERENCES rides(id) | Set for `free_ride`/`discount` (the booking's ride) |
| `booking_id` | UUID NULL REFERENCES bookings(id) | Set for `free_ride`/`discount` |
| `fulfilled_by` | UUID NULL REFERENCES profiles(id) | Admin who fulfilled/rejected a manual request |
| `fulfilled_at` | TIMESTAMPTZ NULL | |
| `rejection_reason` | TEXT NULL | |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

Index: `(status, created_at ASC) WHERE status = 'pending'` mirroring `car_maintenance_rewards`' admin-queue index.

## Extended entities

### `admin_audit_logs` (+1 column)

`redemption_request_id UUID NULL REFERENCES loyalty_redemption_requests(id)` — same pattern as `car_maintenance_reward_id`/`withdrawal_request_id`. No `action_type` CHECK change (`'approved'`/`'rejected'` reused).

### `notification_event_type` (+4 enum values)

`loyalty_points_earned`, `loyalty_redemption_fulfilled`, `loyalty_redemption_rejected`, `loyalty_threshold_reached` — added via `ALTER TYPE ... ADD VALUE IF NOT EXISTS`.

### `platform_settings` (+5 seeded keys)

| Key | Default | Used by |
|---|---|---|
| `loyalty_free_ride_point_cost` | `"500"` | `free_ride` catalog entry point cost |
| `loyalty_free_ride_max_fare_egp` | `"100.00"` | FR-004 cap; passenger pays fare above this |
| `loyalty_discount_point_cost` | `"200"` | `discount` catalog entry point cost |
| `loyalty_discount_percentage` | `"10"` | FR-005 fare percentage |
| `loyalty_car_maintenance_point_cost` | `"3000"` | `car_maintenance` catalog entry cost (1:1 with the retired `CAR_MAINTENANCE_THRESHOLD_EGP`) |
| `loyalty_passenger_earn_points_per_egp_fare` | `"1"` | FR-001 passenger earn rate |

### `driver_wallets` / `car_maintenance_rewards` (deprecated, not dropped)

`car_maintenance_savings_egp` stops being written to (superseded by `loyalty_points_accounts`); column stays for historical read access. `car_maintenance_rewards` stops receiving new rows; existing rows remain as an archival record (research.md Decision 2).

## Relationships

```
profiles ──< loyalty_points_accounts (role-scoped, unique per user+role)
                 │
                 ├──< loyalty_points_transactions (immutable ledger)
                 │        ├── ride_id / booking_id  (earn / clawback)
                 │        └── redemption_request_id (spend / refund)
                 │
                 └──< loyalty_redemption_requests
                          ├── catalog_entry_id ──> loyalty_reward_catalog
                          ├── ride_id / booking_id  (free_ride / discount only)
                          └── fulfilled_by ──> profiles (admin)

admin_audit_logs.redemption_request_id ──> loyalty_redemption_requests
```

## State transitions — `loyalty_redemption_requests.status`

```
                     ┌─────────────┐
  instant mode  ───▶ │  fulfilled  │  (inserted directly; free_ride/discount/instant voucher)
                     └─────────────┘

  manual mode   ───▶ │  pending    │ ──▶ fulfilled  (admin fulfills; car_maintenance / manual voucher)
                     └─────────────┘ ──▶ rejected   (admin rejects → refund_points transaction, FR-012)
```

## Validation rules

- `loyalty_points_accounts.balance` never negative (DB CHECK + `GREATEST(x-y,0)` guard on any defensive decrement, mirroring `wallet_service.decrement_car_maintenance_savings`).
- A redemption is only accepted when `account.balance >= catalog_entry.point_cost` (checked under `SELECT ... FOR UPDATE` on the account row, same lock discipline as `wallet_service.get_wallet_with_lock`) — prevents double-spend under NFR-002.
- `free_ride`/`discount` redemption is rejected if the booking already carries an active sponsored-group discount (FR-005a), checked in the same booking-creation transaction.
- Ride/booking cancellation, refund, or fraud-flagging reverses the earn transaction via a `ride_reversal_clawback` entry capped at the account's current balance (`GREATEST` floor) — never drives balance negative (FR-014).
