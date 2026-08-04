-- Phase 13 (016-continuous-learning-pipeline) follow-up: fills three gaps
-- discovered while implementing model_lifecycle_service's shadow-burn-in and
-- rollout-progression logic (T031/T033), none of which were named by
-- spec.md/contracts with a concrete value or column:
--
-- 1. "meets rollout criteria" (FR-010/FR-011) never named a numeric
--    threshold anywhere in spec/research/contracts — added as two more
--    tunable continuous_learning_config fields, consistent with NFR-005
--    (all thresholds config-driven, no redeploy) rather than hardcoding.
-- 2. check_rollout_progression() (contract model-lifecycle.md step 3) needs
--    to know how long a version has held its *current* rollout_pct step to
--    decide when to advance — no such timestamp existed.
-- 3. The very first real-data retrain for a model_type has no prior
--    model_versions champion row (models before this feature existed only
--    as Storage latest.json, untracked here) — shadow_comparisons.
--    champion_version_id was NOT NULL, which made that case unrepresentable.

ALTER TABLE public.continuous_learning_config
    ADD COLUMN shadow_min_agreement_rate NUMERIC(5, 4) NOT NULL DEFAULT 0.5000,
    ADD COLUMN shadow_min_outcome_alignment_rate NUMERIC(5, 4) NOT NULL DEFAULT 0.5000;

ALTER TABLE public.model_versions
    ADD COLUMN rollout_step_started_at TIMESTAMPTZ;

ALTER TABLE public.shadow_comparisons
    ALTER COLUMN champion_version_id DROP NOT NULL;
