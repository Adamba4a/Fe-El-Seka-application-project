# Data Model: Financial System (Phase 8)

**Branch**: `011-financial-system` | **Date**: 2026-06-29

---

## New Entities

### DriverWallet

One record per verified driver. Created automatically on first top-up, first commission deduction, or first ride creation (whichever comes first).

| Column | Type | Nullable | Constraints | Notes |
|--------|------|----------|-------------|-------|
| `id` | `UUID` | No | PK, DEFAULT gen_random_uuid() | |
| `driver_id` | `UUID` | No | FK → users(id), UNIQUE | One wallet per driver |
| `balance_egp` | `NUMERIC(12, 2)` | No | DEFAULT 0.00 | Materialized sum of ledger credits minus debits |
| `reserved_egp` | `NUMERIC(12, 2)` | No | DEFAULT 0.00 CHECK (reserved_egp >= 0) | Materialized sum of active CommissionReservation amounts |
| `created_at` | `TIMESTAMPTZ` | No | DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | No | DEFAULT now() | Updated on every balance or reservation change |

**Derived field** (never stored): `available_egp = balance_egp − reserved_egp`. All balance enforcement checks and driver UI displays use this derived value.

**Row-level locking**: Every write transaction acquires `SELECT ... FOR UPDATE` on this row before modifying `balance_egp` or `reserved_egp`.

**State invariants**:
- `balance_egp = SUM(ADMIN_CREDIT) - SUM(COMMISSION_DEBIT) - SUM(ADMIN_DEBIT)` from `driver_ledger_entries` where `driver_id` matches
- `reserved_egp = SUM(reserved_amount_egp)` from `commission_reservations` where `wallet_id` matches and the associated ride is not in a terminal status
- `reserved_egp >= 0` — enforced by DB constraint; negative reservation is a bug

---

### CommissionReservation

A temporary hold on a driver's available balance, created when a ride is posted and deleted when the ride reaches a terminal status (completed or cancelled). One per ride (enforced by `UNIQUE (ride_id)`).

| Column | Type | Nullable | Constraints | Notes |
|--------|------|----------|-------------|-------|
| `id` | `UUID` | No | PK, DEFAULT gen_random_uuid() | |
| `wallet_id` | `UUID` | No | FK → driver_wallets(id) | |
| `driver_id` | `UUID` | No | FK → users(id) | Denormalized for query efficiency |
| `ride_id` | `UUID` | No | FK → rides(id), UNIQUE | At most one reservation per ride (FR-023) |
| `reserved_amount_egp` | `NUMERIC(10, 2)` | No | CHECK (reserved_amount_egp > 0) | `ROUND(fuel_cost_egp × 0.20, 2)` at time of ride creation |
| `created_at` | `TIMESTAMPTZ` | No | DEFAULT now() | |

**Lifecycle**:
1. **Created** — atomically with ride INSERT when balance check passes; `wallet.reserved_egp += reserved_amount_egp`
2. **Deleted (completion)** — atomically with ride `completed` transition and `COMMISSION_DEBIT` ledger entries; `wallet.reserved_egp -= reserved_amount_egp`
3. **Deleted (cancellation)** — atomically with ride/booking cancellation; `wallet.reserved_egp -= reserved_amount_egp`; no ledger entry created

**Orphan invariant**: No `CommissionReservation` row should exist for a ride whose `status` is `completed` or `cancelled`. Detectable via: `SELECT cr.* FROM commission_reservations cr JOIN rides r ON r.id = cr.ride_id WHERE r.status IN ('completed', 'cancelled')`.

---

### DriverLedgerEntry

Immutable financial event record. Append-only: `UPDATE` and `DELETE` are revoked from the application database role at migration time.

| Column | Type | Nullable | Constraints | Notes |
|--------|------|----------|-------------|-------|
| `id` | `UUID` | No | PK, DEFAULT gen_random_uuid() | |
| `wallet_id` | `UUID` | No | FK → driver_wallets(id) | |
| `driver_id` | `UUID` | No | FK → users(id) | Denormalized for query efficiency |
| `type` | `ledger_entry_type` (enum) | No | | See enum values below |
| `amount_egp` | `NUMERIC(10, 2)` | No | CHECK (amount_egp >= 0) | Always non-negative; sign conveyed by `type` |
| `ride_id` | `UUID` | Yes | FK → rides(id) | Set for `COMMISSION_DEBIT` only |
| `booking_id` | `UUID` | Yes | FK → bookings(id) | Set for `COMMISSION_DEBIT` only |
| `fuel_cost_egp_snapshot` | `NUMERIC(10, 2)` | Yes | | Ride's stored fuel cost at time of deduction; set for `COMMISSION_DEBIT` only |
| `created_by` | `UUID` | Yes | FK → users(id) | Admin user ID; set for `ADMIN_CREDIT` / `ADMIN_DEBIT` only |
| `note` | `TEXT` | Yes | | Optional admin annotation |
| `created_at` | `TIMESTAMPTZ` | No | DEFAULT now() | |

**Enum: `ledger_entry_type`**

```sql
CREATE TYPE ledger_entry_type AS ENUM (
  'COMMISSION_DEBIT',  -- commission deducted from driver wallet on ride completion
  'ADMIN_CREDIT',      -- admin manual top-up
  'ADMIN_DEBIT'        -- admin corrective debit (reversal of erroneous top-up)
);
```

**Sign convention**: `amount_egp` is always stored as a positive value. Whether it increases or decreases `balance_egp` is determined by `type`:
- `ADMIN_CREDIT` → `balance_egp += amount_egp`
- `COMMISSION_DEBIT` → `balance_egp -= amount_egp`
- `ADMIN_DEBIT` → `balance_egp -= amount_egp`

**Database privileges** (set in migration):
```sql
GRANT INSERT, SELECT ON driver_ledger_entries TO app_role;
REVOKE UPDATE, DELETE ON driver_ledger_entries FROM app_role;
```

---

## Modified Entities (no new columns)

### rides (Phase 4)

Phase 8 reads but does not modify the schema. The relevant existing columns are:
- `fuel_cost_egp` (`NUMERIC(10,2)`) — written by Phase 5 at ride creation; read by Phase 8 to compute reservations and deductions
- `total_seat_count` (`INTEGER`) — written by Phase 4; read by Phase 8 for `commission_per_booking = fuel_cost_egp × 0.20 / total_seat_count`
- `status` — Phase 8 hooks into `scheduled → cancelled` and `in_progress → completed` transitions (written by Phase 4/7)
- `driver_id` — used to identify the wallet to credit/debit

### bookings (Phase 6)

Phase 8 reads but does not modify the schema. The relevant existing columns are:
- `status` — Phase 8 counts `confirmed` bookings transitioning to `completed` to determine commission deduction count
- `fare_amount_egp` — stored by Phase 6 at booking creation; not used in the commission formula (commission is derived from `fuel_cost_egp`, not `fare_amount_egp`)
- `ride_id`, `id` — linked in each `COMMISSION_DEBIT` ledger entry for full auditability

---

## Row-Level Security (RLS) Summary

| Table | Driver | Passenger | Admin (service role) |
|-------|--------|-----------|----------------------|
| `driver_wallets` | SELECT own row | No access | SELECT all |
| `commission_reservations` | SELECT own rows | No access | SELECT all |
| `driver_ledger_entries` | SELECT own rows | No access | SELECT all |

All INSERT operations use service role (backend only). No application RLS policy allows driver or passenger INSERT into wallet tables.

---

## State Machine: Commission Reservation Lifecycle

```
[Ride Created]
     │
     ▼
CommissionReservation CREATED
wallet.reserved_egp += amount
     │
     ├─── ride cancelled ──────────▶ CommissionReservation DELETED
     │                               wallet.reserved_egp -= amount
     │                               (no ledger entry)
     │
     └─── ride completed ──────────▶ CommissionReservation DELETED
                                     wallet.reserved_egp -= amount
                                     COMMISSION_DEBIT × confirmed_bookings CREATED
                                     wallet.balance_egp -= sum(deductions)
                                     (empty seat amount silently released)
```

---

## Indexes

```sql
-- driver_wallets: primary lookup is by driver_id (1:1 so UNIQUE index already covers it)
CREATE UNIQUE INDEX idx_driver_wallets_driver_id ON driver_wallets(driver_id);

-- commission_reservations: lookup by driver for available-balance computation
CREATE INDEX idx_commission_reservations_driver_id ON commission_reservations(driver_id);

-- driver_ledger_entries: history queries are always by driver_id ordered by created_at DESC
CREATE INDEX idx_driver_ledger_driver_created ON driver_ledger_entries(driver_id, created_at DESC);
-- ride-level audit lookup
CREATE INDEX idx_driver_ledger_ride_id ON driver_ledger_entries(ride_id) WHERE ride_id IS NOT NULL;
```
