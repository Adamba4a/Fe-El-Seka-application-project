-- Widen walk and premium-detour thresholds for Cairo district-level searching.
--
-- Context: Nominatim geocodes district names (e.g. "Nasr City") to the district
-- centroid, which can be 1.5–2 km from where the driver's route actually passes.
-- The old 500m dropoff walk and 2km premium detour limits reject these valid matches.
--
-- max_dropoff_walk_m / max_pickup_walk_m: 500 → 1500
--   Passengers searching by district name get centroid coordinates; 1.5km covers
--   most centroid-to-route gaps while still being reasonable to walk.
--
-- max_premium_detour_km: 2 → 5
--   A driver detouring to drop a passenger in Nasr City while going to Cairo
--   University adds ~5 km. 5km allows this while rejecting truly out-of-way requests.

UPDATE public.pricing_config
SET
    max_pickup_walk_m       = 1500,
    max_dropoff_walk_m      = 1500,
    max_premium_detour_km   = 5.00;
