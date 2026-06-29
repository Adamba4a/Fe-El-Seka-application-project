-- Phase 8: Financial System — additional performance indexes
-- The per-table indexes (driver_id lookups, ride_id lookups) were created in their
-- respective migration files. This file adds composite and admin-facing indexes that
-- reference multiple Phase 8 tables or support admin panel queries.

-- Admin panel: all ledger entries for a specific wallet (admin wallet history view)
CREATE INDEX idx_driver_ledger_wallet_created
    ON public.driver_ledger_entries (wallet_id, created_at DESC);

-- Admin panel: locate all wallets with a balance below a threshold (future low-balance alerts)
CREATE INDEX idx_driver_wallets_balance
    ON public.driver_wallets (balance_egp);

-- Orphan-detection check (SC-008): find reservations for rides in terminal status.
-- Used by the integrity check in quickstart.md and periodic monitoring.
-- SELECT cr.id FROM commission_reservations cr
-- JOIN rides r ON r.id = cr.ride_id
-- WHERE r.status IN ('completed', 'cancelled');
-- No partial index here — the join is across tables; a standard ride_id index suffices.
-- (idx_commission_reservations_driver_id already covers the driver-scoped lookup.)
