-- Phase 10: Trust & Community
-- Creates: report_category, report_status, report_resolution_action, rater_role enums
--          ratings table, reports table, moderation_config table (singleton, mirrors ranking_config)
-- Extends: profiles (rating_avg, rating_count), admin_audit_logs (action_type gains 'warned',
--          adds report_id reference column)

-- ── Enums ──────────────────────────────────────────────────────────────────

CREATE TYPE report_category AS ENUM (
    'unsafe_driving', 'harassment', 'no_show', 'fraud_or_scam', 'vehicle_mismatch', 'other'
);

CREATE TYPE report_status AS ENUM ('open', 'under_review', 'resolved', 'dismissed');

CREATE TYPE report_resolution_action AS ENUM ('warn', 'suspend', 'dismiss');

CREATE TYPE rater_role AS ENUM ('passenger', 'driver');

-- ── ratings ─────────────────────────────────────────────────────────────────

CREATE TABLE public.ratings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id  UUID NOT NULL REFERENCES public.bookings(id) ON DELETE RESTRICT,
    ride_id     UUID NOT NULL REFERENCES public.rides(id) ON DELETE RESTRICT,
    rater_id    UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    ratee_id    UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    rater_role  rater_role NOT NULL,
    stars       SMALLINT NOT NULL CHECK (stars BETWEEN 1 AND 5),
    comment     TEXT CHECK (char_length(comment) <= 500),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- At most one rating per direction per booking (FR-005)
    CONSTRAINT ratings_booking_rater_unique UNIQUE (booking_id, rater_id)
);

-- Ratee's own anonymized comment list (FR-007)
CREATE INDEX idx_ratings_ratee_created
    ON public.ratings (ratee_id, created_at DESC);

ALTER TABLE public.ratings ENABLE ROW LEVEL SECURITY;

-- Party-scoped SELECT only; no client INSERT/UPDATE/DELETE — writes go through the
-- backend using the service-role key inside a validated transaction.
CREATE POLICY "rating_party_select" ON public.ratings
    FOR SELECT USING (auth.uid() IN (rater_id, ratee_id));

-- ── reports ─────────────────────────────────────────────────────────────────

CREATE TABLE public.reports (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ride_id            UUID NOT NULL REFERENCES public.rides(id) ON DELETE RESTRICT,
    booking_id         UUID NOT NULL REFERENCES public.bookings(id) ON DELETE RESTRICT,
    reporter_id        UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    reported_user_id   UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    category           report_category NOT NULL,
    description        TEXT NOT NULL CHECK (char_length(description) BETWEEN 1 AND 1000),
    status             report_status NOT NULL DEFAULT 'open',
    resolution_action  report_resolution_action,
    resolution_reason  TEXT,
    resolved_by        UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at        TIMESTAMPTZ,

    CHECK (reported_user_id != reporter_id)
);

-- Admin moderation queue ordering (FR-018)
CREATE INDEX idx_reports_status_created
    ON public.reports (status, created_at DESC);

-- Rolling 30-day report-count check (FR-019b)
CREATE INDEX idx_reports_reported_user_created
    ON public.reports (reported_user_id, created_at DESC);

-- Reporter's own history view (FR-016)
CREATE INDEX idx_reports_reporter_created
    ON public.reports (reporter_id, created_at DESC);

ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY;

-- Reporter sees only their own report history (status only, FR-016); the reported user has
-- no SELECT policy at all — they never see who reported them or that a report exists
-- (spec Edge Cases). No client INSERT/UPDATE/DELETE — writes go through the backend.
CREATE POLICY "reporter_select_own_reports" ON public.reports
    FOR SELECT USING (auth.uid() = reporter_id);

-- ── moderation_config (singleton, mirrors ranking_config) ────────────────────

CREATE TABLE public.moderation_config (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rating_floor            NUMERIC(2, 1) NOT NULL DEFAULT 3.0,
    rating_window           SMALLINT NOT NULL DEFAULT 10,
    rating_min_count        SMALLINT NOT NULL DEFAULT 5,
    report_count_threshold  SMALLINT NOT NULL DEFAULT 3,
    report_window_days      SMALLINT NOT NULL DEFAULT 30,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed the single default row
INSERT INTO public.moderation_config (id)
VALUES (gen_random_uuid());

-- Keep updated_at current on every write
CREATE OR REPLACE FUNCTION public.set_moderation_config_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER moderation_config_updated_at
    BEFORE UPDATE ON public.moderation_config
    FOR EACH ROW EXECUTE FUNCTION public.set_moderation_config_updated_at();

-- Service-role only — no client policies, mirroring ranking_config
ALTER TABLE public.moderation_config ENABLE ROW LEVEL SECURITY;

-- ── profiles: rating aggregate columns ───────────────────────────────────────

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS rating_avg   NUMERIC(3, 2),
    ADD COLUMN IF NOT EXISTS rating_count INTEGER NOT NULL DEFAULT 0;

-- ── admin_audit_logs: extend action_type, add report_id reference ───────────

-- Drop whatever the action_type CHECK constraint is actually named (don't assume the
-- Postgres-default auto-generated name survived unchanged) to avoid silently adding a second,
-- conflicting CHECK that would reject every 'warned' write at runtime.
DO $$
DECLARE
    existing_constraint text;
BEGIN
    SELECT conname INTO existing_constraint
    FROM pg_constraint
    WHERE conrelid = 'public.admin_audit_logs'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%action_type%';

    IF existing_constraint IS NOT NULL THEN
        EXECUTE format('ALTER TABLE public.admin_audit_logs DROP CONSTRAINT %I', existing_constraint);
    END IF;
END $$;

ALTER TABLE public.admin_audit_logs
    ADD CONSTRAINT admin_audit_logs_action_type_check
        CHECK (action_type IN ('approved', 'rejected', 'suspended', 'reinstated', 'unlocked', 'warned'));

ALTER TABLE public.admin_audit_logs
    ADD COLUMN IF NOT EXISTS report_id UUID REFERENCES public.reports(id) ON DELETE SET NULL;
