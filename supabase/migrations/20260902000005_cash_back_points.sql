-- Cash Back becomes points-first: earnings that used to land directly in
-- sponsored_earnings_egp now accrue as redeemable points (1 pt = 1 EGP).
-- sponsored_earnings_egp keeps its existing meaning going forward — the
-- withdrawable cash balance — populated only by the new redeem action.
-- Existing sponsored_earnings_egp balances are left untouched (grandfathered
-- as already-withdrawable cash); only future earnings accrue as points.

ALTER TABLE driver_wallets
    ADD COLUMN cash_back_points_egp NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (cash_back_points_egp >= 0);

ALTER TYPE ledger_entry_type ADD VALUE IF NOT EXISTS 'CASH_BACK_REDEEMED';
