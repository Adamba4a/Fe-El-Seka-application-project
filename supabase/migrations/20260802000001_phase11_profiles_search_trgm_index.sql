-- Phase 11 (admin operations): trigram indexes for ILIKE search on profiles.
-- NFR-002 requires GET /api/admin/users?q=... to stay <=300ms p95. At ~50,000
-- profiles a sequential ILIKE scan cost ~57ms, run twice per request (count +
-- page), which alone consumed most of the budget.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_profiles_display_name_trgm
    ON public.profiles USING gin (display_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_profiles_email_trgm
    ON public.profiles USING gin (email gin_trgm_ops);
