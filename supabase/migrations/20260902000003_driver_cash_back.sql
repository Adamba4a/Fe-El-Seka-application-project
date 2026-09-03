-- Post-Spec-028 pricing/loyalty overhaul, item 1: retire driver loyalty
-- points/car-maintenance-savings entirely in favor of a directly-withdrawable
-- "Cash Back" credit, paid straight into driver_wallets.sponsored_earnings_egp
-- (the same pool sponsored-ride settlements already use — see
-- 20260831000001_separate_sponsored_earnings_wallet.sql). The driver reward
-- catalog (car_maintenance / voucher entries) is dropped for drivers; only
-- passenger-facing catalog entries remain active.

-- ── driver_ledger_entries.type: new enum values ──────────────────────────────
-- Each ALTER TYPE ... ADD VALUE must be its own statement/transaction — it
-- cannot be combined with a statement that references the new value.

ALTER TYPE ledger_entry_type ADD VALUE IF NOT EXISTS 'CASH_BACK_CREDIT';
ALTER TYPE ledger_entry_type ADD VALUE IF NOT EXISTS 'CASH_BACK_REVERSAL';

-- ── drop the driver-facing reward catalog ────────────────────────────────────
-- Passengers still redeem 'both'-audience vouchers/discounts; only entries
-- scoped exclusively to drivers are deactivated.

UPDATE loyalty_reward_catalog SET active = false WHERE audience = 'driver';
