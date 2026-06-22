-- Phase 5: Route Intelligence — Pricing Configuration
-- Singleton table: always exactly one row.
-- Admin edits values directly via the Supabase dashboard.

CREATE TABLE public.pricing_config (
    id                          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pricing formula parameters (FR-024, FR-025)
    fuel_price_per_litre        NUMERIC(10, 2)  NOT NULL DEFAULT 15.00,
    safety_margin               NUMERIC(10, 2)  NOT NULL DEFAULT 5.00,

    -- Compatibility thresholds (FR-005, FR-010, FR-014)
    corridor_buffer_radius_m    INTEGER         NOT NULL DEFAULT 150,
    min_overlap_pct             NUMERIC(5, 2)   NOT NULL DEFAULT 50.00,
    max_pickup_walk_m           INTEGER         NOT NULL DEFAULT 500,
    max_dropoff_walk_m          INTEGER         NOT NULL DEFAULT 500,
    max_detour_km               NUMERIC(10, 2)  NOT NULL DEFAULT 3.00,
    max_detour_minutes          INTEGER         NOT NULL DEFAULT 10,
    max_premium_detour_km       NUMERIC(10, 2)  NOT NULL DEFAULT 2.00,
    time_window_minutes         INTEGER         NOT NULL DEFAULT 30,

    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT now()
);

ALTER TABLE public.pricing_config ENABLE ROW LEVEL SECURITY;

-- Seed the single default row
INSERT INTO public.pricing_config (id)
VALUES (gen_random_uuid());

-- Keep updated_at current on every write
CREATE OR REPLACE FUNCTION public.set_pricing_config_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER pricing_config_updated_at
    BEFORE UPDATE ON public.pricing_config
    FOR EACH ROW EXECUTE FUNCTION public.set_pricing_config_updated_at();
