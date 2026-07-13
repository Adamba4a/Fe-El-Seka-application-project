-- Phase 13: Match Learning Foundation
-- Creates: match_outcome_transition enum
--          search_sessions, match_events, match_outcomes, ranking_config tables
-- Internal ML telemetry, not surfaced in any UI — RLS enabled, no public policies
-- (service-role backend access only). See specs/013-match-learning-foundation/data-model.md.

-- ── Enums ──────────────────────────────────────────────────────────────────

CREATE TYPE match_outcome_transition AS ENUM (
    'requested', 'accepted', 'rejected', 'completed', 'cancelled', 'rated'
);

-- ── search_sessions ────────────────────────────────────────────────────────
-- Groups all match events returned from one passenger search request.

CREATE TABLE public.search_sessions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    passenger_id          UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    origin_point          geometry(Point, 4326) NOT NULL,
    destination_point     geometry(Point, 4326) NOT NULL,
    desired_departure_at  TIMESTAMPTZ NOT NULL,
    ai_available          BOOLEAN NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_search_sessions_passenger_created
    ON public.search_sessions (passenger_id, created_at DESC);

-- ── match_events ───────────────────────────────────────────────────────────
-- One record per ride candidate shown to a passenger in a search response.

CREATE TABLE public.match_events (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_id             UUID NOT NULL REFERENCES public.search_sessions(id) ON DELETE RESTRICT,
    passenger_id          UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    candidate_ride_id     UUID NOT NULL REFERENCES public.rides(id) ON DELETE RESTRICT,
    feature_vector        JSONB NOT NULL,
    predicted_score       NUMERIC(5, 4),
    rank_position         INTEGER NOT NULL,
    exploration_selected  BOOLEAN NOT NULL DEFAULT FALSE,
    ai_scored             BOOLEAN NOT NULL,
    model_version         TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_match_events_search_id
    ON public.match_events (search_id);

CREATE INDEX idx_match_events_candidate_passenger_created
    ON public.match_events (candidate_ride_id, passenger_id, created_at DESC);

-- ── match_outcomes ─────────────────────────────────────────────────────────
-- Append-only log of observed downstream results for a match event.
-- Never updated after insert.

CREATE TABLE public.match_outcomes (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_event_id   UUID NOT NULL REFERENCES public.match_events(id) ON DELETE RESTRICT,
    transition_type  match_outcome_transition NOT NULL,
    transition_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata         JSONB NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_match_outcomes_event_transition
    ON public.match_outcomes (match_event_id, transition_at ASC);

-- ── ranking_config ─────────────────────────────────────────────────────────
-- Singleton table: always exactly one row. Admin edits values directly via the
-- Supabase dashboard. Mirrors pricing_config's shape and refresh convention.

CREATE TABLE public.ranking_config (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exploration_rate  NUMERIC(5, 4) NOT NULL DEFAULT 0.1250,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed the single default row
INSERT INTO public.ranking_config (id)
VALUES (gen_random_uuid());

-- Keep updated_at current on every write
CREATE OR REPLACE FUNCTION public.set_ranking_config_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER ranking_config_updated_at
    BEFORE UPDATE ON public.ranking_config
    FOR EACH ROW EXECUTE FUNCTION public.set_ranking_config_updated_at();

-- ── RLS ────────────────────────────────────────────────────────────────────
-- Internal ML telemetry, never surfaced in any passenger/driver/admin UI.
-- No public policies — only the backend service-role connection (asyncpg pool)
-- can read/write these tables.

ALTER TABLE public.search_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.match_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.match_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ranking_config ENABLE ROW LEVEL SECURITY;
