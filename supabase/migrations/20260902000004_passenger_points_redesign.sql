-- Item 3: passenger points redesign — pay-with-points at booking creation,
-- earn formula moves to commission/4, split earn between completion (cash)
-- and confirmation (sponsored).

ALTER TABLE bookings
    ADD COLUMN points_redeemed INTEGER NOT NULL DEFAULT 0 CHECK (points_redeemed >= 0),
    ADD COLUMN points_discount_egp NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (points_discount_egp >= 0);

ALTER TYPE ledger_entry_type ADD VALUE IF NOT EXISTS 'POINTS_DISCOUNT_REIMBURSEMENT';
