-- Phase 15 (interim): Manual Wallet Top-Up via Vodafone Cash
-- Creates: wallet_topup_requests table
-- Driver-initiated, admin-reviewed request layer in front of the existing Phase 8
-- ADMIN_CREDIT wallet top-up path (driver_wallets / driver_ledger_entries).
-- Submission does NOT credit the wallet; only an admin approval does, via the
-- existing wallet_service functions (see services/api/app/services/wallet_topup_service.py).
--
-- State machine (one-way, enforced in application code):
--   PENDING -> APPROVED   (admin approve)
--   PENDING -> REJECTED   (admin reject)
--   PENDING -> CANCELLED  (driver self-cancel)
-- APPROVED / REJECTED / CANCELLED are terminal.

CREATE TABLE public.wallet_topup_requests (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id           UUID            NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    amount_egp          NUMERIC(12, 2)  NOT NULL,
    payment_reference   TEXT            NOT NULL,
    screenshot_path     TEXT            NOT NULL,
    status              TEXT            NOT NULL DEFAULT 'PENDING',
    rejection_reason    TEXT,
    reviewed_by         UUID            REFERENCES auth.users(id),
    reviewed_at         TIMESTAMPTZ,
    ledger_entry_id     UUID            REFERENCES public.driver_ledger_entries(id),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_topup_amount_positive     CHECK (amount_egp > 0.00),
    CONSTRAINT chk_topup_reference_nonempty  CHECK (length(trim(payment_reference)) > 0),
    CONSTRAINT chk_topup_status              CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')),
    CONSTRAINT chk_topup_rejection_reason    CHECK (rejection_reason IS NULL OR status = 'REJECTED')
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

-- FR-005 / NFR-005 — reference number uniqueness among active requests, DB-enforced.
-- REJECTED/CANCELLED requests are excluded so their reference numbers can be reused.
CREATE UNIQUE INDEX uq_topup_reference_active
    ON public.wallet_topup_requests (payment_reference)
    WHERE status IN ('PENDING', 'APPROVED');

-- FR-004 — at most one PENDING request per driver, DB-enforced (closes the same
-- concurrent-submission race NFR-005 calls out for payment_reference).
CREATE UNIQUE INDEX uq_topup_one_pending_per_driver
    ON public.wallet_topup_requests (driver_id)
    WHERE status = 'PENDING';

-- FR-008 — admin queue, oldest-first.
CREATE INDEX idx_topup_pending_queue
    ON public.wallet_topup_requests (created_at)
    WHERE status = 'PENDING';

-- US3 — driver's own history, newest-first.
CREATE INDEX idx_topup_driver_history
    ON public.wallet_topup_requests (driver_id, created_at DESC);

-- ── RLS ───────────────────────────────────────────────────────────────────────
-- Mirrors driver_wallets/driver_ledger_entries: admin endpoints use the backend's
-- service-role connection (bypasses RLS); these policies cover any direct client access.

ALTER TABLE public.wallet_topup_requests ENABLE ROW LEVEL SECURITY;

-- Drivers may view and create only their own requests.
CREATE POLICY "driver_read_own_topup_request" ON public.wallet_topup_requests
    FOR SELECT USING (driver_id = auth.uid());

CREATE POLICY "driver_insert_own_topup_request" ON public.wallet_topup_requests
    FOR INSERT WITH CHECK (driver_id = auth.uid());

-- Drivers may update (cancel) only their own request, and only while it is still PENDING.
CREATE POLICY "driver_cancel_own_topup_request" ON public.wallet_topup_requests
    FOR UPDATE USING (driver_id = auth.uid() AND status = 'PENDING');

-- No DELETE policy for clients: requests are never deleted, only transitioned.
