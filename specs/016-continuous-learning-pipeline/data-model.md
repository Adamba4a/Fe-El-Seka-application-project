# Data Model: Continuous Learning Pipeline

All new tables live in `services/api`'s Postgres schema (asyncpg, raw SQL), follow the existing RLS convention from `013-match-learning-foundation` (RLS enabled, no public policies — service-role/asyncpg-only access, never surfaced directly in any UI), and use UUID primary keys per the constitution's Data Standards. New enums use `CREATE TYPE ... AS ENUM`, matching the most recent convention (`report_resolution_action`, `match_outcome_transition`) rather than TEXT+CHECK.

Migration file: `supabase/migrations/20260802000002_phase13_continuous_learning.sql`

---

## Enums

### `model_promotion_status`
```
'candidate'        -- trained, evaluated, not yet promotion-eligible or rejected
'rejected'         -- failed promotion margin vs champion; retained for audit, never served
'shadow'           -- promotion-eligible, running shadow burn-in, 0% live traffic
'partial_rollout'  -- past burn-in, serving a configured % of live traffic
'champion'         -- serving 100% of live traffic
'retired'          -- was champion or partial_rollout, superseded or rolled back
```

### `monitoring_metric_type`
```
'prediction_distribution'
'acceptance_rate'
'completion_rate'
```

---

## Entities

### Dataset Snapshot → table `dataset_snapshots`

Maps to spec's **Dataset Snapshot** entity. One row per dataset-pipeline run (FR-001).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `model_type` | TEXT | `'match_score'` \| `'ride_ranker'` |
| `storage_path` | TEXT | e.g. `match_score/2026-08-09T02-00-00Z/dataset.parquet`, bucket `training-datasets` |
| `row_count` | INT | rows retained after exclusions |
| `excluded_count` | INT | rows dropped (fraud/bot/spam-flagged, outside retention window) — FR-003 |
| `date_range_start` | TIMESTAMPTZ | earliest `match_events.created_at` included |
| `date_range_end` | TIMESTAMPTZ | latest `match_events.created_at` included |
| `exclusion_summary` | JSONB | breakdown, e.g. `{"fraud_flagged": 4, "retention_expired": 12}` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` |

**Relationships**: referenced by `model_versions.dataset_snapshot_id`.

**Note on Training Example** (spec's other Key Entity): individual labeled rows are NOT a Postgres table — they are the rows inside the Parquet file at `dataset_snapshots.storage_path` (per research.md R8). Each row carries: source `match_event_id`, the 14-dimensional feature vector (from `match_events.feature_vector`), `signal_strength_tier` (FR-002 hierarchy), derived `label`, and the owning `dataset_snapshot_id`. This keeps bulk training data out of Postgres while `dataset_snapshots` remains the queryable, auditable index over it.

---

### Model Version → table `model_versions`

Maps to spec's **Model Version** + **Evaluation Result** entities (merged — a version is evaluated once, at creation, against the dataset snapshot it was trained/held-out against; embedding avoids a needless 1:1 join table).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `model_type` | TEXT | `'match_score'` \| `'ride_ranker'` |
| `storage_version` | TEXT | the version token used in the `model-registry` Storage path (`{model_type}/{storage_version}/...`) |
| `dataset_snapshot_id` | UUID FK → `dataset_snapshots.id` | dataset this version was trained + evaluated on |
| `promotion_status` | `model_promotion_status` | see state machine below |
| `evaluation_score` | NUMERIC(6,4) | ranking-quality metric (FR-007): rate at which top-ranked candidate matches passenger's actual choice, on held-out real data |
| `comparison_margin` | NUMERIC(6,4) NULL | `evaluation_score - champion.evaluation_score` at the time this version was evaluated |
| `rollout_pct` | NUMERIC(5,2) | `0` unless `partial_rollout` or `champion` (`champion` implies 100) |
| `shadow_started_at` | TIMESTAMPTZ NULL | burn-in start, for computing burn-in elapsed duration |
| `promoted_at` | TIMESTAMPTZ NULL | when it became `champion` |
| `retired_at` | TIMESTAMPTZ NULL | when it left `champion`/`partial_rollout` |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` |

**Constraints**: `UNIQUE (model_type, storage_version)`. At most one row per `model_type` may have `promotion_status = 'champion'` at a time — enforced in `model_lifecycle_service.py` (transactional check-then-set), not a DB constraint, since the transition itself (old champion → retired, new version → champion) must be atomic across two rows.

**State transitions** (FR-006 through FR-012, User Stories 2-3):

```
candidate --(fails promotion margin)--> rejected                    [terminal]
candidate --(exceeds champion by margin)--> shadow
shadow --(burn-in period elapses, comparison report favorable)--> partial_rollout
shadow --(burn-in comparison unfavorable)--> retired                 [terminal, never served]
partial_rollout --(rollout_pct steps reach 100, holds)--> champion   [previous champion --> retired]
partial_rollout --(short-horizon acceptance rate underperforms)--> retired  [automatic rollback, FR-012]
champion --(a later version reaches champion)--> retired
```

`rejected` and the two `retired`-from-shadow/`partial_rollout` paths are all terminal per-version outcomes; a rolled-back or rejected version is never resurrected — a fresh retraining run produces a new candidate row instead (consistent with the append-only audit trail FR-016 requires).

---

### Shadow Comparison Report → table `shadow_comparisons`

Maps to spec's **Shadow Comparison Report** entity (FR-010, User Story 3 Acceptance Scenario 2).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `candidate_version_id` | UUID FK → `model_versions.id` | |
| `champion_version_id` | UUID FK → `model_versions.id` | the champion being compared against at burn-in time |
| `burn_in_start` | TIMESTAMPTZ | copies `model_versions.shadow_started_at` |
| `burn_in_end` | TIMESTAMPTZ | when this report was generated |
| `agreement_rate` | NUMERIC(5,4) | fraction of shadowed requests where candidate and champion top-ranked the same ride |
| `outcome_alignment_rate` | NUMERIC(5,4) NULL | of requests with a known real outcome by report time, fraction where candidate's top choice matched the actual outcome (may be null if too few outcomes resolved yet) |
| `sample_size` | INT | number of `match_events` rows with `shadow_model_version = candidate`'s storage_version, within the burn-in window |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` |

**Derivation**: computed on-demand by `model_lifecycle_service.generate_shadow_comparison_report()` from `match_events` (filtered `shadow_model_version = <candidate storage_version>` and `created_at` within `[burn_in_start, burn_in_end]`) joined to `match_outcomes`; the result row is persisted here once, at burn-in end, for the audit trail (not recomputed live).

---

### Monitoring Metric → table `model_monitoring_metrics`

Maps to spec's **Monitoring Metric** entity (FR-013, FR-014, User Story 4).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `model_version_id` | UUID FK → `model_versions.id` | the champion (or partial-rollout candidate) this metric was measured for |
| `zone` | TEXT | matches the existing zone identifier convention used by `zone_lookup.py`/`ranking_config` |
| `metric_type` | `monitoring_metric_type` | |
| `time_window_start` | TIMESTAMPTZ | |
| `time_window_end` | TIMESTAMPTZ | one hour apart, per NFR-004 |
| `value` | NUMERIC(8,4) | measured metric value for the window |
| `baseline` | NUMERIC(8,4) | established baseline for this zone/metric_type at measurement time |
| `alert_raised` | BOOLEAN | `DEFAULT false` — true when `value` deviates from `baseline` beyond the configured margin (FR-014) |
| `created_at` | TIMESTAMPTZ | `DEFAULT now()` |

**Index**: `(model_version_id, zone, metric_type, time_window_start)` for the hourly aggregation query and for baseline lookups (baseline = trailing average of prior windows for the same zone/metric_type).

---

### Spot Audit Record → table `model_spot_audits`

Maps to spec's **Spot Audit Record** entity (FR-015, User Story 4 Acceptance Scenario 3).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `model_version_id` | UUID FK → `model_versions.id` | |
| `match_event_id` | UUID FK → `match_events.id` | the sampled decision under review |
| `reviewer_admin_id` | UUID FK → `profiles.id` NULL | null until reviewed |
| `finding` | TEXT NULL | free-text reviewer note; null until reviewed |
| `triggered_rollback` | BOOLEAN | `DEFAULT false` — set true if this finding led to an out-of-cycle rollback (edge case in spec) |
| `sampled_at` | TIMESTAMPTZ | `DEFAULT now()` |
| `reviewed_at` | TIMESTAMPTZ NULL | |

**Sampling logic**: `model_monitoring_service.py` inserts new rows (with `reviewer_admin_id`/`finding`/`reviewed_at` left null) on the configured spot-audit cadence, weighted toward higher frequency in the period immediately following a promotion/rollout start (per FR-015's "increased frequency during the early period" and Acceptance Scenario 3). Rows are populated (`reviewer_admin_id`, `finding`, `reviewed_at`) by a human reviewer out-of-band; no UI is built for this in this feature (spec Out-of-Scope) — review happens via direct DB/SQL access until `015-admin-operations` is extended, same as `ranking_config`'s dashboard-only editing today.

---

### Continuous Learning Config → table `continuous_learning_config`

Singleton config table (NFR-005), mirrors `pricing_config`/`ranking_config`'s exact shape and trigger pattern.

| Column | Type | Default | Notes |
|---|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` | single seed row |
| `min_dataset_size` | INT | `500` | completed-rides-with-outcomes threshold (Assumptions) |
| `retraining_cadence_hours` | INT | `168` | weekly default |
| `promotion_margin` | NUMERIC(5,4) | `0.0200` | required evaluation-score improvement over champion |
| `shadow_burnin_hours` | INT | `168` | weekly burn-in default |
| `rollout_step_pcts` | JSONB | `[5, 25, 50, 100]` | staged rollout percentages, applied in order |
| `rollout_step_hold_hours` | INT | `24` | minimum time at each step before advancing |
| `rollback_margin` | NUMERIC(5,4) | `0.0500` | short-horizon acceptance-rate underperformance that triggers auto-rollback |
| `monitoring_interval_hours` | INT | `1` | NFR-004 |
| `alert_baseline_margin` | NUMERIC(5,4) | `0.1000` | zone metric deviation that raises an alert |
| `spot_audit_sample_size` | INT | `10` | decisions sampled per audit cycle |
| `spot_audit_frequency_hours` | INT | `24` | baseline cadence; halved during the early post-promotion window per FR-015 |
| `spot_audit_early_window_hours` | INT | `72` | duration after promotion/rollout-start considered "early period" |
| `updated_at` | TIMESTAMPTZ | `now()` | bumped by trigger, mirrors `set_pricing_config_updated_at()` |

**Access pattern**: `continuous_learning_config_service.py` — module-level cache dict + `asyncio.Lock`, `init_continuous_learning_config()` at startup (falls back to the defaults above if the table is briefly unavailable, mirroring `pricing_service.py`'s `_DEFAULTS` pattern), `continuous_learning_config_refresh_loop()` on a 30s `asyncio.sleep`, identical to `pricing_config_refresh_loop`/`ranking_config_refresh_loop`.

---

## Extensions to existing tables

### `match_events` (from `013-match-learning-foundation`)

Add three nullable columns to support shadow scoring and rollout-variant tracking (research.md R7):

| Column | Type | Notes |
|---|---|---|
| `shadow_score` | NUMERIC(5,4) NULL | candidate model's score for this event, when a candidate/shadow model exists at logging time |
| `shadow_model_version` | TEXT NULL | the candidate's `storage_version`, for later joining to `model_versions`/computing `shadow_comparisons` |
| `served_variant` | TEXT | `'champion'` \| `'candidate'` — which score was actually shown to the user; `DEFAULT 'champion'` so existing/backfilled rows and non-rollout periods are correctly attributed |

`ALTER TABLE match_events ADD COLUMN ... ` with the `DEFAULT 'champion'` ensures no backfill migration is needed — every row logged before this feature ships is correctly `'champion'` by construction (there was no candidate to serve).

No changes to `match_outcomes`, `search_sessions`, or `ranking_config` — this feature is purely additive to the existing `013` schema.

---

## RLS Policy

All six new tables: `ALTER TABLE ... ENABLE ROW LEVEL SECURITY;` with **no policies added** — service-role (asyncpg connection) bypasses RLS by default in Supabase, matching the exact pattern and rationale already documented in `20260714000001_phase13_match_learning.sql` ("never surfaced in any UI, service-role/asyncpg-only access").
