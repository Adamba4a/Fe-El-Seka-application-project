-- Widen compatibility thresholds to match Cairo's road network reality.
--
-- corridor_buffer_radius_m: 150 → 500
--   Cairo roads are wide and OSRM may route via parallel arterials (e.g. Ring Road
--   vs. Salah Salem). A 150m corridor (300m total width) misses routes on adjacent
--   roads. 500m captures parallel roads within walking distance.
--
-- min_overlap_pct: 50 → 30
--   With a larger buffer the measured overlap naturally rises, but the passenger's
--   route and the driver's road path can still diverge where the driver uses a
--   faster bypass. 30% is sufficient to confirm the driver is heading in the same
--   direction; pickup/dropoff walk limits already gate exact boarding/alighting.

UPDATE public.pricing_config
SET
    corridor_buffer_radius_m = 500,
    min_overlap_pct          = 30.00;
