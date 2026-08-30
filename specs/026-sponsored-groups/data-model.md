# Phase 1 Data Model: Sponsored Groups

## `groups` (existing table, extended)

| Column | Type | Notes |
|---|---|---|
| `is_sponsored` | `boolean NOT NULL DEFAULT false` | Set true on admin creation or in-place upgrade of an existing group. The original `CHECK (NOT is_sponsored OR type IN ('company','university'))` constraint was dropped along with `groups.type`/`groups.domain` by the Groups (024) open-membership redesign (`supabase/migrations/20260830000004_open_groups_multi_domain_sponsorship.sql`) — any group, regardless of type (which no longer exists), can be flagged sponsored. |
| `funded_balance_egp` | `numeric(12,2) NOT NULL DEFAULT 0.00` | Company's remaining sponsorship budget. `CHECK (funded_balance_egp >= 0.00)`. Debited per sponsored booking (research.md §4), credited back on cancellation reversal (§11), incremented by an admin's add-funds action. |
| `dashboard_contact_user_id` | `uuid NULL REFERENCES profiles(id)` | The domain-verified member who can view the read-only company dashboard (FR-020). Must already be a member of this group at both initial designation and reassignment — enforced at the service layer (research.md §12), not a DB constraint. |

**Validation**: `funded_balance_egp` is only ever mutated inside a transaction that holds `SELECT ... FOR UPDATE` on the group row (booking creation, cancellation reversal, admin add-funds) — same locking discipline as `driver_wallets.balance_egp`.

## `group_sponsor_domains` (new table, added 2026-08-30)

Added by `supabase/migrations/20260830000004_open_groups_multi_domain_sponsorship.sql` to fix a fragmentation bug in the original one-domain-per-group design: a university's several per-faculty email domains (e.g., `eng-st.cu.edu.eg`, `med-st.cu.edu.eg`) previously each spawned a separate Groups (024) company/university group even though those students ride the same routes. This table lets one sponsored group list many eligible domains instead.

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid PK default gen_random_uuid()` | |
| `group_id` | `uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE` | The sponsored group this domain grants sponsorship eligibility for. |
| `domain` | `text NOT NULL UNIQUE` | Lowercased email domain. Globally unique across all sponsored groups — one domain can only ever grant eligibility on a single group (FR-003, `domain_already_sponsored` on conflict). |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | |

Backfilled at migration time from every pre-existing `groups.domain` value (the column dropped in the same migration), so no eligible domain was lost during the redesign. Admin-managed via `add_sponsor_domain`/`remove_sponsor_domain` in `sponsored_group_service.py`.

**Validation**: `domain` normalized lowercase, checked against the platform's public-provider blocklist (same list as Groups' FR-011) before insert, at the service layer.

## `bookings` (existing table, extended)

| Column | Type | Notes |
|---|---|---|
| `payment_source` | `text NOT NULL DEFAULT 'CASH' CHECK (payment_source IN ('CASH','SPONSORED'))` | Set once at booking-creation time (research.md §3), immutable afterward. `SPONSORED` iff the ride's group was sponsored at the moment this booking was created. |

## `driver_ledger_entries.type` (existing Postgres enum `ledger_entry_type`, extended)

Three new values added via `ALTER TYPE ledger_entry_type ADD VALUE`:

| Value | Meaning | Written by |
|---|---|---|
| `SPONSORED_RIDE_CREDIT` | Driver's net-of-commission credit for one sponsored booking, at booking-creation time. | `booking_service.create_booking` (research.md §4) |
| `SPONSORED_RIDE_REVERSAL` | Reverses a `SPONSORED_RIDE_CREDIT` when its booking is cancelled. | Booking cancellation flow (research.md §11) |
| `WITHDRAWAL_DEBIT` | Debits the driver's wallet when an admin approves a withdrawal request. | Withdrawal approval (research.md §10) |

Every new entry carries `ride_id`/`booking_id` (for the two sponsored types) exactly like `COMMISSION_DEBIT` already does, so a company dashboard or admin financial report can trace each credit/reversal back to its ride and booking.

## `withdrawal_requests` (new table)

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid PK default gen_random_uuid()` | |
| `driver_id` | `uuid NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT` | |
| `amount_egp` | `numeric(12,2) NOT NULL CHECK (amount_egp > 0.00)` | Validated against the driver's *available* balance (`balance_egp - reserved_egp`) at submission time (FR-011 area). |
| `payout_reference` | `text NOT NULL CHECK (length(trim(payout_reference)) > 0)` | Driver-supplied payout destination (e.g. their Vodafone Cash number) — the reverse-direction analog of `wallet_topup_requests.payment_reference`. |
| `status` | `text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','REJECTED'))` | No `CANCELLED` state (research.md §8) — narrower state machine than `wallet_topup_requests`. |
| `rejection_reason` | `text NULL` | `CHECK (rejection_reason IS NULL OR status = 'REJECTED')`, mirrors `wallet_topup_requests`. |
| `reviewed_by` | `uuid NULL REFERENCES auth.users(id)` | |
| `reviewed_at` | `timestamptz NULL` | |
| `ledger_entry_id` | `uuid NULL REFERENCES driver_ledger_entries(id)` | Set on approval, points at the `WITHDRAWAL_DEBIT` entry. |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | |

**State transitions**: `PENDING → APPROVED` (admin approve, re-checks available balance under lock per research.md §10) or `PENDING → REJECTED` (admin reject, mandatory `rejection_reason`, mirrors `wallet_topup_service.reject_request`). Both are terminal — no further transitions.

**Indexes**:
- `uq_withdrawal_one_pending_per_driver ON withdrawal_requests (driver_id) WHERE status = 'PENDING'` — DB-enforced FR-011 (research.md §9).
- `idx_withdrawal_pending_queue ON withdrawal_requests (created_at) WHERE status = 'PENDING'` — admin queue, oldest-first, mirrors `idx_topup_pending_queue`.
- `idx_withdrawal_driver_history ON withdrawal_requests (driver_id, created_at DESC)` — driver's own history.

## Relationships

```text
groups 1───1 profiles          (dashboard_contact_user_id, nullable)
groups 1───* group_sponsor_domains   (a sponsored group's eligible email domains, domain globally unique)
groups 1───* bookings          (via rides.group_id → bookings.ride_id; payment_source distinguishes sponsored)
groups.funded_balance_egp ──── debited/credited by bookings whose ride.group_id = this group
profiles(driver) 1───* withdrawal_requests
withdrawal_requests 1───0..1 driver_ledger_entries   (ledger_entry_id, set on approval)
bookings(payment_source='SPONSORED') 1───1 driver_ledger_entries   (SPONSORED_RIDE_CREDIT, via booking_id)
```

## RLS Summary (detail in `contracts/api.md` and the migration itself)

- `groups`: existing `SELECT` policy unchanged (directory browsing already open to authenticated users); `is_sponsored`/`funded_balance_egp`/`dashboard_contact_user_id` are only ever written via the backend's service-role connection (admin sponsorship endpoints) — no new client-writable columns.
- `group_sponsor_domains`: `SELECT` open to any authenticated user (mirrors `groups`); `INSERT`/`DELETE` service-role only (admin add/remove-domain endpoints).
- `bookings`: existing RLS unchanged; `payment_source` is set by the service-role connection at insert time, never client-supplied.
- `withdrawal_requests`: mirrors `wallet_topup_requests` exactly — `driver_read_own_withdrawal_request` (SELECT own), `driver_insert_own_withdrawal_request` (INSERT own). No client UPDATE policy at all (no self-cancel, unlike top-up) — status transitions are admin/service-role only. No DELETE policy — requests are never deleted.
