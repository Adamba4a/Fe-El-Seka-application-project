# Quickstart: Continuous Learning Pipeline

Validates the feature end-to-end using locally-seeded data shaped like the real schema — per spec Assumptions, User Story 1 (dataset pipeline) can be validated now; User Stories 2-4 (retraining, shadow, monitoring) need this same seeded data plus a mocked/short-cadence config to exercise without waiting for real production traffic.

## Prerequisites

- Local Supabase instance running with all migrations applied through `20260714000001_phase13_match_learning.sql` and `20260729000001_phase10_trust_community.sql`, plus this feature's new migration `20260802000002_phase13_continuous_learning.sql` applied.
- `services/api` and `services/ai` both running locally (`uvicorn`), pointed at the local Supabase instance.
- Seed data: at least 500 `search_sessions` + `match_events` + `match_outcomes` rows spanning `completed`, `cancelled`, and `shown_not_booked` cases (a seeding script can adapt the existing synthetic-ride generator's output shape, or a fixture can insert rows directly matching `013`'s schema).

## Scenario 1 — Dataset pipeline produces a labeled snapshot (User Story 1)

```
# From services/api
uv run python -c "
import asyncio
from app.services.dataset_pipeline_service import generate_dataset_snapshot
asyncio.run(generate_dataset_snapshot('match_score'))
"
```

**Expected**: a `dataset_snapshots` row is inserted with `row_count` close to the seeded volume minus any fraud/retention exclusions, and a Parquet file exists at `training-datasets/match_score/{snapshot_id}/dataset.parquet` in local Storage. Inspect the Parquet file and confirm every row has a `signal_strength_tier` from the documented hierarchy and no row corresponds to a suspended/rejected account.

## Scenario 2 — Retraining produces a candidate, gated by promotion margin (User Story 2)

```
# Trigger via services/api's retraining_scheduler_loop manually, or call directly:
curl -X POST http://localhost:8001/training/retrain \
  -H "Content-Type: application/json" \
  -d '{"model_type":"match_score","dataset_storage_path":"match_score/<snapshot_id>/dataset.parquet","dataset_snapshot_id":"<uuid>"}'
```

**Expected**: response is `{"status":"trained", "storage_version": ..., "evaluation_score": ...}` (or `gate_failed` if AUC/ECE gates aren't met — try again with a larger/cleaner seed set). Confirm a `model_versions` row is inserted: `'candidate'` immediately followed by `'shadow'` if it beats the existing champion by `promotion_margin`, or `'rejected'` if not — both outcomes are correct per FR-008, not a bug.

## Scenario 3 — Shadow scoring and staged rollout (User Story 3)

1. With a version in `'shadow'` status, issue a normal search request through `services/api`'s existing search endpoint and confirm `services/ai`'s `/predict/match-score` response (visible in `services/api` logs' `ai_prediction_call` event) includes non-null `shadow_score`/`shadow_model_version`, while the passenger-visible ranking is unaffected (still driven by the champion score only).
2. Confirm the corresponding `match_events` row has `shadow_score`/`shadow_model_version` populated and `served_variant = 'champion'`.
3. Manually invoke `model_lifecycle_service.generate_shadow_comparison_report(...)` after seeding enough shadow-window traffic; confirm a `shadow_comparisons` row appears and the version transitions to `'partial_rollout'` (favorable) or `'retired'` (unfavorable).
4. If `'partial_rollout'`: issue several more search requests and confirm roughly `rollout_pct`% of them get `served_variant = 'candidate'`.
5. Seed a batch of `match_outcomes` showing the candidate-variant's shown rides getting rejected/not-booked at a much higher rate than the champion's; run `check_rollout_progression()` and confirm the version flips to `'retired'`, `rollout_pct = 0`, and subsequent requests are 100% `served_variant = 'champion'` again — validating FR-012's automatic rollback without any `services/ai` call or deployment.

## Scenario 4 — Monitoring and spot audits (User Story 4)

1. Run `model_monitoring_service`'s hourly aggregation manually against the seeded `match_events`/`match_outcomes` for the current champion; confirm `model_monitoring_metrics` rows appear per zone/metric_type with computed `value`/`baseline`.
2. Seed a synthetic degradation (a batch of `match_outcomes` in one zone showing an artificially low acceptance rate) and re-run the aggregation; confirm the corresponding row has `alert_raised = true`.
3. Run `record_spot_audit_samples()`; confirm `model_spot_audits` rows are inserted, unreviewed, referencing real `match_events` rows for the current champion.

## Validating configuration is redeploy-free (NFR-005)

Edit any value in `continuous_learning_config` directly via SQL (e.g. `UPDATE continuous_learning_config SET promotion_margin = 0.05;`) and confirm, within 30 seconds (the refresh loop interval), that a fresh call to `model_lifecycle_service` reflects the new margin — no restart of `services/api` required, mirroring how `pricing_config`/`ranking_config` changes already take effect today.
