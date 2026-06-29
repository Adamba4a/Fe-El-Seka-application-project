-- Phase 8: Financial System — driver wallet
-- Creates: driver_wallets table
-- One row per verified driver. Holds two materialized running totals:
--   balance_egp  = sum of ADMIN_CREDIT - sum of COMMISSION_DEBIT - sum of ADMIN_DEBIT (from driver_ledger_entries)
--   reserved_egp = sum of active CommissionReservation amounts (from commission_reservations)
-- available_egp is always derived: balance_egp - reserved_egp (never stored).
-- All balance-mutating transactions must acquire SELECT ... FOR UPDATE on this row before writing.

CREATE TABLE public.driver_wallets (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id       UUID            NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    balance_egp     NUMERIC(12, 2)  NOT NULL DEFAULT 0.00,
    reserved_egp    NUMERIC(12, 2)  NOT NULL DEFAULT 0.00,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_driver_wallet         UNIQUE (driver_id),
    CONSTRAINT chk_reserved_non_negative CHECK (reserved_egp >= 0.00)
);

-- Driver wallet lookup (SELECT FOR UPDATE in balance operations)
CREATE UNIQUE INDEX idx_driver_wallets_driver_id
    ON public.driver_wallets (driver_id);

ALTER TABLE public.driver_wallets ENABLE ROW LEVEL SECURITY;

-- Drivers read their own wallet only; all writes are service-role only (backend)
CREATE POLICY "driver_read_own_wallet" ON public.driver_wallets
    FOR SELECT USING (driver_id = auth.uid());

-- No client INSERT/UPDATE/DELETE: backend service role only
