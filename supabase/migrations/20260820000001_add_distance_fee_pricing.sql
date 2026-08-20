-- Add a per-km distance fee to the pricing formula, kept 100% as platform
-- revenue (same treatment as the flat safety margin — no extra 20% cut is
-- taken on top of it). Also bumps the default fuel price.

ALTER TABLE public.pricing_config
    ADD COLUMN distance_rate_per_km NUMERIC(10, 2) NOT NULL DEFAULT 0.30;

ALTER TABLE public.rides
    ADD COLUMN distance_fee_egp NUMERIC(10, 2) NULL;

UPDATE public.pricing_config
SET fuel_price_per_litre = 22.25,
    distance_rate_per_km = 0.30;
