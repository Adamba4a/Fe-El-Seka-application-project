-- Spec 026: Sponsored Groups
-- Extends groups/bookings/driver_ledger_entries and adds withdrawal_requests.

-- ── groups: sponsorship fields ──────────────────────────────────────────────

ALTER TABLE public.groups
    ADD COLUMN is_sponsored boolean NOT NULL DEFAULT false,
    ADD COLUMN funded_balance_egp numeric(12, 2) NOT NULL DEFAULT 0.00,
    ADD COLUMN dashboard_contact_user_id uuid NULL REFERENCES public.profiles(id);

ALTER TABLE public.groups
    ADD CONSTRAINT chk_groups_sponsored_type CHECK (NOT is_sponsored OR type IN ('company', 'university'));

ALTER TABLE public.groups
    ADD CONSTRAINT chk_groups_funded_balance_nonnegative CHECK (funded_balance_egp >= 0.00);

-- ── bookings: payment_source ─────────────────────────────────────────────────

ALTER TABLE public.bookings
    ADD COLUMN payment_source text NOT NULL DEFAULT 'CASH';

ALTER TABLE public.bookings
    ADD CONSTRAINT chk_bookings_payment_source CHECK (payment_source IN ('CASH', 'SPONSORED'));

-- ── driver_ledger_entries.type: new enum values ──────────────────────────────
-- Each ALTER TYPE ... ADD VALUE must be its own statement/transaction — it
-- cannot be combined with a statement that references the new value.

ALTER TYPE ledger_entry_type ADD VALUE IF NOT EXISTS 'SPONSORED_RIDE_CREDIT';
ALTER TYPE ledger_entry_type ADD VALUE IF NOT EXISTS 'SPONSORED_RIDE_REVERSAL';
ALTER TYPE ledger_entry_type ADD VALUE IF NOT EXISTS 'WITHDRAWAL_DEBIT';

-- ── withdrawal_requests: driver-initiated, admin-reviewed cash-out ──────────
-- Reverse-direction analog of wallet_topup_requests. Narrower state machine:
-- no CANCELLED state, no proof upload, no client UPDATE policy at all.
--   PENDING -> APPROVED   (admin approve; re-checks available balance under lock)
--   PENDING -> REJECTED   (admin reject, mandatory rejection_reason)
-- APPROVED / REJECTED are terminal.

CREATE TABLE public.withdrawal_requests (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id           UUID            NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    amount_egp          NUMERIC(12, 2)  NOT NULL,
    payout_reference    TEXT            NOT NULL,
    status              TEXT            NOT NULL DEFAULT 'PENDING',
    rejection_reason    TEXT,
    reviewed_by         UUID            REFERENCES auth.users(id),
    reviewed_at         TIMESTAMPTZ,
    ledger_entry_id     UUID            REFERENCES public.driver_ledger_entries(id),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_withdrawal_amount_positive       CHECK (amount_egp > 0.00),
    CONSTRAINT chk_withdrawal_reference_nonempty    CHECK (length(trim(payout_reference)) > 0),
    CONSTRAINT chk_withdrawal_status                CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    CONSTRAINT chk_withdrawal_rejection_reason      CHECK (rejection_reason IS NULL OR status = 'REJECTED')
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- FR-011/clarification #4 — at most one PENDING request per driver, DB-enforced.
CREATE UNIQUE INDEX uq_withdrawal_one_pending_per_driver
    ON public.withdrawal_requests (driver_id)
    WHERE status = 'PENDING';

-- Admin queue, oldest-first.
CREATE INDEX idx_withdrawal_pending_queue
    ON public.withdrawal_requests (created_at)
    WHERE status = 'PENDING';

-- Driver's own history, newest-first.
CREATE INDEX idx_withdrawal_driver_history
    ON public.withdrawal_requests (driver_id, created_at DESC);

-- ── RLS ───────────────────────────────────────────────────────────────────────
-- Mirrors wallet_topup_requests: admin endpoints use the backend's service-role
-- connection (bypasses RLS); these policies cover any direct client access.
-- No UPDATE policy at all (no self-cancel, unlike top-up) — status transitions
-- are admin/service-role only. No DELETE policy — requests are never deleted.

ALTER TABLE public.withdrawal_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY "driver_read_own_withdrawal_request" ON public.withdrawal_requests
    FOR SELECT USING (driver_id = auth.uid());

CREATE POLICY "driver_insert_own_withdrawal_request" ON public.withdrawal_requests
    FOR INSERT WITH CHECK (driver_id = auth.uid());
