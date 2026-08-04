# Contract: Model Lifecycle Service (`services/api/app/services/model_lifecycle_service.py`)

Internal service module — no HTTP surface (no admin UI in this feature; see spec Out-of-Scope). Owns the `model_versions` state machine (data-model.md) and is the only writer of `promotion_status`/`rollout_pct`.

## Function: `evaluate_and_register_candidate(model_type, dataset_snapshot_id, storage_version, evaluation_score) -> ModelVersion`

Called after `ai_client.retrain_model()` returns a successful training result (FR-006, FR-007, FR-008).

1. Look up the current `champion` row for `model_type` (may be none, e.g. first-ever real-data retrain).
2. Read `promotion_margin` from `continuous_learning_config`.
3. If no champion exists yet, OR `evaluation_score - champion.evaluation_score >= promotion_margin`: insert `model_versions` row with `promotion_status = 'candidate'`, `comparison_margin` set, and immediately call `advance_to_shadow()` (below) — a passing candidate proceeds straight to shadow, per Acceptance Scenario 4 ("becomes eligible for rollout via shadow deployment ... rather than replacing the live model directly").
4. Else: insert `model_versions` row with `promotion_status = 'rejected'`, `comparison_margin` set (negative or below threshold). Retained for audit (FR-006, SC-005); never served.

## Function: `advance_to_shadow(model_version_id)`

1. Set `promotion_status = 'shadow'`, `shadow_started_at = now()`.
2. Call `services/ai`'s `POST /models/shadow` (contracts/ai-service-endpoints.md) to activate the candidate slot.

## Function: `check_shadow_burnin_due() -> list[ModelVersion]`

Called each tick of `retraining_scheduler_loop`. Returns `shadow`-status versions where `now() - shadow_started_at >= shadow_burnin_hours` (from config).

## Function: `generate_shadow_comparison_report(model_version_id) -> ShadowComparisonReport`

Implements FR-010 / User Story 3 Acceptance Scenario 2. Queries `match_events` where `shadow_model_version = <this version's storage_version>` and `created_at BETWEEN shadow_started_at AND now()`, joined to `match_outcomes` where available, computing `agreement_rate` (candidate's top choice == champion's top choice) and `outcome_alignment_rate` (candidate's top choice == the ride actually accepted, for events with a resolved outcome). Inserts a `shadow_comparisons` row.

**Decision after report**:
- Favorable (agreement/outcome-alignment meet configured rollout criteria) → `promotion_status = 'partial_rollout'`, `rollout_pct = rollout_step_pcts[0]` (e.g. 5).
- Unfavorable → `promotion_status = 'retired'`, call `services/ai`'s `POST /models/discard-candidate`. Terminal — per spec Edge Case, "the champion continues serving indefinitely; this is the expected safe outcome."

## Function: `check_rollout_progression()`

Called each tick of `retraining_scheduler_loop` (or a dedicated faster loop if the hourly cadence proves too coarse for `rollout_step_hold_hours` granularity — default config values keep these aligned). For each `partial_rollout` version:

1. Compute short-horizon acceptance rate for `served_variant = 'candidate'` events vs. the champion's `served_variant = 'champion'` events, over a trailing window (FR-012).
2. **Rollback** if candidate's acceptance rate is below the champion's by `rollback_margin`: set `promotion_status = 'retired'`, `rollout_pct = 0`. This is the entire rollback action — no `services/ai` call is required on this path (research.md R7); the next read of `model_versions` by the routing decision (below) simply stops selecting the candidate.
3. **Advance** if the version has held its current `rollout_pct` for `>= rollout_step_hold_hours` without rollback: move to the next value in `rollout_step_pcts`. If already at the last step (100), call `advance_to_champion()`.

## Function: `advance_to_champion(model_version_id)`

1. Look up the current `champion` for this `model_type` (if any) and set it `promotion_status = 'retired'`, `retired_at = now()`.
2. Set the new version `promotion_status = 'champion'`, `rollout_pct = 100`, `promoted_at = now()`.
3. Call `services/ai`'s `POST /models/promote`.

## Function: `get_routing_decision(model_type) -> RoutingDecision`

Called by the search/ranking call site (`services/api`) on every live match/ranking request, reading from the same in-process cache pattern as `continuous_learning_config_service` (refreshed periodically, not queried per-request).

**Returns**: `{"variant": "champion" | "candidate", "candidate_storage_version": str | None}` — a weighted-random choice: `random() < rollout_pct/100` picks `"candidate"` when a `partial_rollout` version exists for this `model_type`; otherwise always `"champion"`.

**Used by**: the existing search/ranking flow to decide whether `ai_client`'s returned `match_score` or `shadow_score` is the one actually used to rank/select candidates shown to the user, and what `match_events.served_variant` gets recorded as.

## Function: `record_spot_audit_samples()`

Called on the `spot_audit_frequency_hours` cadence (halved within `spot_audit_early_window_hours` of any `promoted_at`/`shadow_started_at`, per FR-015). Samples `spot_audit_sample_size` recent `match_events` rows for the current champion (and any active `partial_rollout` candidate) and inserts unreviewed `model_spot_audits` rows.

## Function: `apply_spot_audit_finding(spot_audit_id, reviewer_admin_id, finding, trigger_rollback: bool)`

Populates a `model_spot_audits` row. If `trigger_rollback=True` (edge case: "spot-audit findings ... can trigger an out-of-cycle rollback"), performs the same rollback action as step 2 of `check_rollout_progression()` regardless of the scheduled acceptance-rate check, and sets `model_spot_audits.triggered_rollback = true`.
