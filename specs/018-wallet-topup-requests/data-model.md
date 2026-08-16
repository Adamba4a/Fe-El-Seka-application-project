# Data Model: Manual Wallet Top-Up via Vodafone Cash

**Feature**: `018-wallet-topup-requests` | **Date**: 2026-08-08

All new SQL objects are additive — no existing table's columns are removed or retyped. See
`research.md` for the rationale behind each design choice referenced below.

---

## 1. New table: `wallet_topup_requests`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | |
| `driver_id` | `UUID` | `NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT` | Same FK target/delete rule as `driver_wallets.driver_id` |
| `amount_egp` | `NUMERIC(12,2)` | `NOT NULL CHECK (amount_egp > 0)` | Matches `011-financial-system`'s `NUMERIC(12,2)` convention (FR-003) |
| `payment_reference` | `TEXT` | `NOT NULL CHECK (length(trim(payment_reference)) > 0)` | Free text (Assumptions); uniqueness enforced via partial index below, not a table-level UNIQUE |
| `screenshot_path` | `TEXT` | `NOT NULL` | Storage object path in the private `topup-proofs` bucket, not a public URL |
| `status` | `TEXT` | `NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','REJECTED','CANCELLED'))` | |
| `rejection_reason` | `TEXT` | `NULL`, `CHECK (rejection_reason IS NULL OR status = 'REJECTED')` | Set only on rejection (FR-010) |
| `reviewed_by` | `UUID` | `NULL REFERENCES auth.users(id)` | Admin who approved/rejected |
| `reviewed_at` | `TIMESTAMPTZ` | `NULL` | |
| `ledger_entry_id` | `UUID` | `NULL REFERENCES public.driver_ledger_entries(id)` | Set only on approval (FR-009, SC-003) |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT now()` | |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT now()` | Bumped by trigger or explicit `SET updated_at = now()` on every status transition |

**Indexes / constraints**:

```sql
-- FR-005 / NFR-005 — reference number uniqueness among active requests, DB-enforced.
-- Normalized (lower/trim) so case/whitespace variants of the same real-world
-- reference still collide (post-review fix, 20260814000002).
CREATE UNIQUE INDEX uq_topup_reference_active
    ON wallet_topup_requests (lower(trim(payment_reference)))
    WHERE status IN ('PENDING', 'APPROVED');

-- FR-004 — at most one PENDING request per driver, DB-enforced (closes the same
-- concurrent-submission race NFR-005 calls out for payment_reference)
CREATE UNIQUE INDEX uq_topup_one_pending_per_driver
    ON wallet_topup_requests (driver_id)
    WHERE status = 'PENDING';

-- FR-008 — admin queue ordered oldest-first
CREATE INDEX idx_topup_pending_queue
    ON wallet_topup_requests (created_at)
    WHERE status = 'PENDING';

-- US3 — driver's own history, newest-first
CREATE INDEX idx_topup_driver_history
    ON wallet_topup_requests (driver_id, created_at DESC);
```

**State transitions** (all one-way, enforced in application code — no CHECK can express this):

```
PENDING → APPROVED   (admin approve, FR-009)
PENDING → REJECTED   (admin reject, FR-010)
PENDING → CANCELLED  (driver self-cancel, FR-007)
```

`APPROVED`, `REJECTED`, `CANCELLED` are terminal — FR-011/NFR-003 (no repeat actions on a decided
request) and FR-007 (only `PENDING` is cancellable) are enforced by checking `status = 'PENDING'`
before any transition, inside the same transaction as the write.

**RLS** (mirrors `driver_wallets`/`driver_ledger_entries` RLS shape):

- `SELECT`/`INSERT`: driver may act only where `driver_id = auth.uid()` (FR-002, FR-006).
- `UPDATE` (cancel): driver may update only their own row, only while `status = 'PENDING'`, and the
  `WITH CHECK` requires the resulting row to have `status = 'CANCELLED'` (FR-007) — mirrors
  `passenger_cancel_own_bookings`'s pattern (`20260624000001_phase6_bookings.sql`). Without this
  explicit `WITH CHECK`, Postgres reuses the `USING` clause for it, which would let a driver update
  `amount_egp`/`payment_reference`/`screenshot_path` on their own row while leaving it `PENDING`
  (post-review fix, `20260814000001`).
- Admin queue/approve/reject endpoints use the service-role key (same pattern as
  `admin/wallet_router.py`), bypassing RLS under application-level `get_current_admin` authorization
  (FR-012) — consistent with how `admin/verification_router.py` and `admin/wallet_router.py` already
  operate.

---

## 2. New columns on `profiles`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `is_topup_locked` | `BOOLEAN` | `NOT NULL DEFAULT FALSE` | Mirrors `is_submission_locked`, but a **separate** flag — see `research.md` §5 for why identity-verification and top-up cycles must not share one lock |
| `topup_lock_reset_at` | `TIMESTAMPTZ` | `NULL` | Boundary marker: the cutoff after which `REJECTED` requests count toward the FR-014 cap. `NULL` means "since account creation." Updated on admin unlock and on any `APPROVED` outcome. |

No changes to existing `profiles` columns or their CHECK constraints.

---

## 3. New column on `admin_audit_logs`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `topup_request_id` | `UUID` | `NULL REFERENCES wallet_topup_requests(id)` | Sibling of the existing nullable `submission_id`/`report_id` columns; disambiguates a top-up review audit row from a verification/moderation one (FR-013) |

`action_type` CHECK constraint (`'approved','rejected','suspended','reinstated','unlocked'`) is
reused unchanged — a top-up approval logs `action_type = 'approved'` with `topup_request_id` set and
`submission_id` left `NULL`, exactly the inverse of how a verification approval already logs today.

---

## 4. New `platform_settings` row

| `key` | `value` (seed default) |
|---|---|
| `vodafone_cash_number` | Platform's actual Vodafone Cash number (operator-provided at migration time, or a placeholder updated before launch) |

No schema change — `platform_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TIMESTAMPTZ)`
already exists and already has admin-only `UPDATE`/`INSERT` RLS policies and authenticated `SELECT`
(`supabase/migrations/20260614000005_create_platform_settings.sql`,
`20260614000006_rls_policies.sql`). FR-001 is satisfied by one `INSERT ... ON CONFLICT DO NOTHING` seed row.

**Post-review fix (`20260814000003`)**: the original seed value (`'01000000000'`) was a
validly-formatted Egyptian mobile number, indistinguishable from a real one to a driver — if an
operator forgot to edit it before launch, drivers could send real money to a fake number with no
signal anything was wrong. The seed/fallback value is now the obviously-invalid sentinel
`'VODAFONE_CASH_NUMBER_NOT_CONFIGURED'`, so an unconfigured platform fails visibly instead of
silently looking legitimate. **An operator must still set the real number via direct DB edit before
this feature is exposed to drivers.**

---

## 5. New Storage bucket: `topup-proofs`

Private bucket (mirrors `identity-documents`), object path convention
`{driver_id}/{request_id}.{ext}` (ext ∈ `jpg`, `png`), matching `identity-documents`'s
`{user_id}/{doc}_{submission_id}.{ext}` convention. Access exclusively via
`storage_service.upload_file()` / `.download_file()` / `.generate_signed_url()` — no public bucket
policy (NFR-002).

---

## 6. Key Entity cross-reference (spec.md → schema)

| spec.md `WalletTopupRequest` attribute | Column |
|---|---|
| `id` | `wallet_topup_requests.id` |
| `driver_id` | `wallet_topup_requests.driver_id` |
| `amount_egp` | `wallet_topup_requests.amount_egp` |
| `payment_reference` | `wallet_topup_requests.payment_reference` |
| `screenshot_url` | `wallet_topup_requests.screenshot_path` (signed URL generated on read, never stored as a URL) |
| `status` | `wallet_topup_requests.status` |
| `rejection_reason` | `wallet_topup_requests.rejection_reason` |
| `reviewed_by` | `wallet_topup_requests.reviewed_by` |
| `reviewed_at` | `wallet_topup_requests.reviewed_at` |
| `ledger_entry_id` | `wallet_topup_requests.ledger_entry_id` |
| `created_at` / `updated_at` | as named |
| "Platform Vodafone Cash Number" setting | `platform_settings` row, `key='vodafone_cash_number'` |
