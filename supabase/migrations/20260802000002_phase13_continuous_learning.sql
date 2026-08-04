-- Phase 13 (016-continuous-learning-pipeline): Continuous Learning Pipeline
-- Creates: model_promotion_status, monitoring_metric_type enums
--          dataset_snapshots, model_versions, shadow_comparisons,
--          model_monitoring_metrics, model_spot_audits, continuous_learning_config tables
--          match_events.shadow_score / shadow_model_version / served_variant columns
-- Internal ML governance state, not surfaced in any UI — RLS enabled, no public
-- policies (service-role/asyncpg-only access), same rationale as
-- 20260714000001_phase13_match_learning.sql. See
-- specs/016-continuous-learning-pipeline/data-model.md.

-- ── Enums ──────────────────────────────────────────────────────────────────

CREATE TYPE model_promotion_status AS ENUM (
    'candidate', 'rejected', 'shadow', 'partial_rollout', 'champion', 'retired'
);

CREATE TYPE monitoring_metric_type AS ENUM (
    'prediction_distribution', 'acceptance_rate', 'completion_rate'
);

-- ── dataset_snapshots ──────────────────────────────────────────────────────
-- One row per dataset-pipeline run (FR-001). Bulk labeled rows live in Storage
-- (training-datasets bucket) as Parquet; this table is the queryable index.

CREATE TABLE public.dataset_snapshots (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_type        TEXT NOT NULL,
    storage_path      TEXT NOT NULL,
    row_count         INTEGER NOT NULL,
    excluded_count    INTEGER NOT NULL DEFAULT 0,
    date_range_start  TIMESTAMPTZ NOT NULL,
    date_range_end    TIMESTAMPTZ NOT NULL,
    exclusion_summary JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_dataset_snapshots_model_type_created
    ON public.dataset_snapshots (model_type, created_at DESC);

-- ── model_versions ─────────────────────────────────────────────────────────
-- Governance state machine for trained candidates (FR-006 through FR-012).
-- At most one 'champion' row per model_type is enforced in
-- model_lifecycle_service.py (transactional check-then-set across two rows),
-- not a DB constraint — see data-model.md.

CREATE TABLE public.model_versions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_type           TEXT NOT NULL,
    storage_version      TEXT NOT NULL,
    dataset_snapshot_id  UUID NOT NULL REFERENCES public.dataset_snapshots(id) ON DELETE RESTRICT,
    promotion_status     model_promotion_status NOT NULL DEFAULT 'candidate',
    evaluation_score     NUMERIC(6, 4) NOT NULL,
    comparison_margin    NUMERIC(6, 4),
    rollout_pct          NUMERIC(5, 2) NOT NULL DEFAULT 0,
    shadow_started_at    TIMESTAMPTZ,
    promoted_at          TIMESTAMPTZ,
    retired_at           TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (model_type, storage_version)
);

CREATE INDEX idx_model_versions_type_status
    ON public.model_versions (model_type, promotion_status);

CREATE INDEX idx_model_versions_dataset_snapshot
    ON public.model_versions (dataset_snapshot_id);

-- ── shadow_comparisons ─────────────────────────────────────────────────────
-- Persisted burn-in comparison report (FR-010, User Story 3).

CREATE TABLE public.shadow_comparisons (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_version_id    UUID NOT NULL REFERENCES public.model_versions(id) ON DELETE RESTRICT,
    champion_version_id     UUID NOT NULL REFERENCES public.model_versions(id) ON DELETE RESTRICT,
    burn_in_start           TIMESTAMPTZ NOT NULL,
    burn_in_end             TIMESTAMPTZ NOT NULL,
    agreement_rate          NUMERIC(5, 4) NOT NULL,
    outcome_alignment_rate  NUMERIC(5, 4),
    sample_size             INTEGER NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shadow_comparisons_candidate
    ON public.shadow_comparisons (candidate_version_id);

-- ── model_monitoring_metrics ───────────────────────────────────────────────
-- Hourly per-zone tracked metrics for the live model (FR-013, FR-014).

CREATE TABLE public.model_monitoring_metrics (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_version_id   UUID NOT NULL REFERENCES public.model_versions(id) ON DELETE RESTRICT,
    zone               TEXT NOT NULL,
    metric_type        monitoring_metric_type NOT NULL,
    time_window_start  TIMESTAMPTZ NOT NULL,
    time_window_end    TIMESTAMPTZ NOT NULL,
    value              NUMERIC(8, 4) NOT NULL,
    baseline           NUMERIC(8, 4),
    alert_raised       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_model_monitoring_metrics_lookup
    ON public.model_monitoring_metrics (model_version_id, zone, metric_type, time_window_start);

-- ── model_spot_audits ──────────────────────────────────────────────────────
-- Human spot-audit sampling and findings (FR-015).

CREATE TABLE public.model_spot_audits (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_version_id    UUID NOT NULL REFERENCES public.model_versions(id) ON DELETE RESTRICT,
    match_event_id      UUID NOT NULL REFERENCES public.match_events(id) ON DELETE RESTRICT,
    reviewer_admin_id   UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    finding             TEXT,
    triggered_rollback  BOOLEAN NOT NULL DEFAULT FALSE,
    sampled_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at         TIMESTAMPTZ
);

CREATE INDEX idx_model_spot_audits_version_reviewed
    ON public.model_spot_audits (model_version_id, reviewed_at);

-- ── continuous_learning_config ─────────────────────────────────────────────
-- Singleton table: always exactly one row. Admin edits values directly via the
-- Supabase dashboard. Mirrors pricing_config/ranking_config's shape and
-- refresh convention (NFR-005 — adjustable without a code deployment).

CREATE TABLE public.continuous_learning_config (
    id                             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    min_dataset_size               INTEGER NOT NULL DEFAULT 500,
    retraining_cadence_hours       INTEGER NOT NULL DEFAULT 168,
    promotion_margin               NUMERIC(5, 4) NOT NULL DEFAULT 0.0200,
    shadow_burnin_hours            INTEGER NOT NULL DEFAULT 168,
    rollout_step_pcts              JSONB NOT NULL DEFAULT '[5, 25, 50, 100]',
    rollout_step_hold_hours        INTEGER NOT NULL DEFAULT 24,
    rollback_margin                NUMERIC(5, 4) NOT NULL DEFAULT 0.0500,
    monitoring_interval_hours      INTEGER NOT NULL DEFAULT 1,
    alert_baseline_margin          NUMERIC(5, 4) NOT NULL DEFAULT 0.1000,
    spot_audit_sample_size         INTEGER NOT NULL DEFAULT 10,
    spot_audit_frequency_hours     INTEGER NOT NULL DEFAULT 24,
    spot_audit_early_window_hours  INTEGER NOT NULL DEFAULT 72,
    updated_at                     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed the single default row
INSERT INTO public.continuous_learning_config (id)
VALUES (gen_random_uuid());

-- Keep updated_at current on every write
CREATE OR REPLACE FUNCTION public.set_continuous_learning_config_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER continuous_learning_config_updated_at
    BEFORE UPDATE ON public.continuous_learning_config
    FOR EACH ROW EXECUTE FUNCTION public.set_continuous_learning_config_updated_at();

-- ── match_events extensions ────────────────────────────────────────────────
-- Shadow scoring and rollout-variant tracking (research.md R7). DEFAULT
-- 'champion' means every pre-existing/backfilled row is correctly attributed
-- with no backfill migration needed — there was no candidate to serve before
-- this feature shipped.

ALTER TABLE public.match_events
    ADD COLUMN shadow_score NUMERIC(5, 4),
    ADD COLUMN shadow_model_version TEXT,
    ADD COLUMN served_variant TEXT NOT NULL DEFAULT 'champion'
        CHECK (served_variant IN ('champion', 'candidate'));

-- ── RLS ────────────────────────────────────────────────────────────────────
-- Internal ML governance state, never surfaced in any passenger/driver/admin
-- UI. No public policies — only the backend service-role connection (asyncpg
-- pool) can read/write these tables.

ALTER TABLE public.dataset_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shadow_comparisons ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_monitoring_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_spot_audits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.continuous_learning_config ENABLE ROW LEVEL SECURITY;
