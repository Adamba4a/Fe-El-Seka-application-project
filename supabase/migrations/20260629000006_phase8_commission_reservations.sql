-- Phase 8: Financial System — commission reservation
-- Creates: commission_reservations table
-- A temporary hold placed on a driver's available balance when a ride is created.
-- One record per ride (enforced by UNIQUE (ride_id)).
-- Lifecycle:
--   INSERT  — atomically with ride INSERT when balance check passes; wallet.reserved_egp += reserved_amount_egp
--   DELETE  — atomically with ride completion (then COMMISSION_DEBIT entries created) or cancellation (no ledger entry)
-- Orphan invariant: no row should exist for a ride with status 'completed' or 'cancelled'.

CREATE TABLE public.commission_reservations (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_id           UUID            NOT NULL REFERENCES public.driver_wallets(id) ON DELETE RESTRICT,
    driver_id           UUID            NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    ride_id             UUID            NOT NULL REFERENCES public.rides(id) ON DELETE RESTRICT,
    reserved_amount_egp NUMERIC(10, 2)  NOT NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_commission_reservation_ride UNIQUE (ride_id),
    CONSTRAINT chk_reservation_positive CHECK (reserved_amount_egp > 0.00)
);

-- Driver-scoped lookup (available balance computation, driver dashboard)
CREATE INDEX idx_commission_reservations_driver_id
    ON public.commission_reservations (driver_id);

ALTER TABLE public.commission_reservations ENABLE ROW LEVEL SECURITY;

-- Drivers can read their own reservations (for wallet summary display)
CREATE POLICY "driver_read_own_reservations" ON public.commission_reservations
    FOR SELECT USING (driver_id = auth.uid());

-- No client INSERT/UPDATE/DELETE: backend service role only
