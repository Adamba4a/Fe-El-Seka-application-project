-- "Nearby endpoint" self-transfer matching.
--
-- Context: a driver's route ending in one satellite city (e.g. Sheikh Zayed)
-- is a genuinely useful ride for a passenger headed to a neighboring one
-- (e.g. 6th of October) who is willing to arrange their own onward transport
-- from the driver's dropoff point. That case previously fell through every
-- match category: too far for the dropoff-walk cap, too far for a premium
-- detour (the driver isn't detouring at all — they already end there), and
-- outside any bounding box unless it happened to be the exact same district.
--
-- max_nearby_endpoint_km: straight road-distance cap between the driver's
-- own destination and the passenger's real destination for this new,
-- no-detour-required, no-fee match category. 15km covers adjacent Cairo
-- satellite cities/districts without surfacing rides that end across town.

ALTER TABLE public.pricing_config
    ADD COLUMN IF NOT EXISTS max_nearby_endpoint_km NUMERIC(10, 2) NOT NULL DEFAULT 15.00;
