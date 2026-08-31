-- Spec 026 round-3: split driver_wallets.balance_egp into two genuinely separate
-- pools. balance_egp is the driver's cash wallet — self-funded top-ups used to pay
-- ride commissions on non-sponsored rides, plus admin credits/debits (including the
-- promotional free-ride top-up). sponsored_earnings_egp is what sponsored-group rides
-- pay the driver, net of commission, and is the ONLY balance withdrawal requests may
-- draw from. Previously SPONSORED_RIDE_CREDIT/REVERSAL landed in balance_egp too,
-- which meant a driver could withdraw promotional cash top-ups as if they were real
-- sponsored earnings — this column separates the two pools so that can't happen.
ALTER TABLE public.driver_wallets
    ADD COLUMN sponsored_earnings_egp NUMERIC(12, 2) NOT NULL DEFAULT 0.00
        CHECK (sponsored_earnings_egp >= 0);

-- One-time backfill: move any already-credited sponsored-ride net amounts (still
-- sitting in balance_egp from before this split) into the new column, so existing
-- drivers' true sponsored earnings aren't lost or duplicated.
WITH sponsored_net AS (
    SELECT wallet_id,
           COALESCE(SUM(CASE WHEN type = 'SPONSORED_RIDE_CREDIT' THEN amount_egp
                              WHEN type = 'SPONSORED_RIDE_REVERSAL' THEN -amount_egp
                              ELSE 0 END), 0) AS net_egp
    FROM public.driver_ledger_entries
    WHERE type IN ('SPONSORED_RIDE_CREDIT', 'SPONSORED_RIDE_REVERSAL')
    GROUP BY wallet_id
)
UPDATE public.driver_wallets w
SET balance_egp = GREATEST(w.balance_egp - sn.net_egp, 0),
    sponsored_earnings_egp = w.sponsored_earnings_egp + sn.net_egp
FROM sponsored_net sn
WHERE sn.wallet_id = w.id AND sn.net_egp <> 0;
