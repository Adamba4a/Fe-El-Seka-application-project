---

description: "Task list for Continuous Learning Pipeline implementation"
---

# Tasks: Continuous Learning Pipeline

**Input**: Design documents from `/specs/016-continuous-learning-pipeline/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan.md's Project Structure explicitly names new unit/integration test files for both `services/api` and `services/ai` (no existing test files or fixture convention to extend; research.md R6 establishes this feature's tests as the first real ones for either service).

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P4) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 (P1), US2 (P2), US3 (P3), US4 (P4) — maps to spec.md's four user stories
- File paths are exact, relative to repo root

## Path Conventions

Monorepo, backend-only (plan.md Structure Decision): `services/api/app/...`, `services/api/tests/...`, `services/ai/app/...`, `services/ai/pipelines/...`, `supabase/migrations/...`. No `apps/main` or `apps/admin` changes.

---

## Phase 1: Setup

**Purpose**: Provision the one piece of new infrastructure this feature needs, and confirm no dependency changes are required.

- [X] T001 Create Supabase Storage bucket `training-datasets`, mirroring the existing `model-registry` bucket's `{model_type}/{version}/...` path convention (research.md R8)
- [X] T002 [P] Verify `services/api/pyproject.toml` and `services/ai/pyproject.toml` already declare every dependency this feature needs (asyncpg, pytest-asyncio, xgboost, scikit-learn, pyarrow, pandas, joblib, supabase-py) — no new dependency is introduced (research.md R1)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema and shared services every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Create migration `supabase/migrations/20260802000002_phase13_continuous_learning.sql`: enums `model_promotion_status`, `monitoring_metric_type`; tables `dataset_snapshots`, `model_versions`, `shadow_comparisons`, `model_monitoring_metrics`, `model_spot_audits`, `continuous_learning_config` (seeded with defaults per data-model.md); `ALTER TABLE match_events ADD COLUMN shadow_score, shadow_model_version, served_variant DEFAULT 'champion'`; `ENABLE ROW LEVEL SECURITY` with no policies on all 6 new tables; `updated_at` trigger for `continuous_learning_config` mirroring `set_pricing_config_updated_at()`
- [X] T004 Apply the migration to the local Supabase instance and verify the resulting schema matches data-model.md (table columns, FKs, indexes, enum values)
- [X] T005 [P] Implement `continuous_learning_config_service.py` in `services/api/app/services/`: singleton cache dict + `asyncio.Lock`, `init_continuous_learning_config()`, `continuous_learning_config_refresh_loop()` (30s), `_DEFAULTS` fallback — mirrors `ranking_config_service.py` (research.md R4)
- [X] T006 Register `init_continuous_learning_config()` call and `continuous_learning_config_refresh_loop()` task in `services/api/app/main.py`'s `lifespan()` (start at entry, `.cancel()` at shutdown, alongside the existing 7 loops)
- [X] T007 [P] Extend `services/ai/app/services/model_registry.py` with `candidate.json` read/write helpers, parallel to the existing `latest.json` helpers, same atomic-upload convention (research.md R3)

**Checkpoint**: Foundation ready — all six new tables exist, config is live-tunable, and the AI-side registry can track a candidate slot. User story implementation can now begin.

---

## Phase 3: User Story 1 - Real ride outcomes become a labeled training dataset (Priority: P1) 🎯 MVP

**Goal**: Periodically join logged match events and outcomes into a labeled, audit-tracked dataset snapshot reflecting real revealed preference.

**Independent Test**: quickstart.md Scenario 1 — run `generate_dataset_snapshot('match_score')` against seeded data and confirm a `dataset_snapshots` row and a Parquet file appear, every row has a `signal_strength_tier`, and no row corresponds to a suspended/rejected account.

### Tests for User Story 1 ⚠️

> Write this test FIRST, ensure it FAILS before implementation

- [X] T008 [P] [US1] Unit test for `generate_dataset_snapshot()` — labeling hierarchy, cancellation handling, fraud/suspension exclusion, retention-window exclusion — in `services/api/tests/unit/test_dataset_pipeline_service.py`

### Implementation for User Story 1

- [X] T009 [US1] Implement the base query in `generate_dataset_snapshot()` (`services/api/app/services/dataset_pipeline_service.py`): join `match_events` to `match_outcomes`, and apply the FR-003 exclusion (accounts with `profiles.verification_status IN ('suspended','rejected')` or a `reports` row resolved `resolution_action = 'suspend'`)
- [X] T010 [US1] Add the FR-004 retention-window exclusion to `generate_dataset_snapshot()`, following the same PDPL 151/2020-driven window already governing `match_events`/`match_outcomes`
- [X] T011 [US1] Add FR-002 `signal_strength_tier` labeling to `generate_dataset_snapshot()` — `completed_highly_rated` / `completed_unrated` / `booked_not_completed` / `shown_not_booked`, with `'cancelled'` folded into `booked_not_completed` (never an automatic negative)
- [X] T012 [US1] Add the FR-004 anonymization step to `generate_dataset_snapshot()` — strip/verify no PII fields beyond opaque UUIDs are present before the Parquet write
- [X] T013 [US1] Add the Parquet write (`training-datasets/{model_type}/{snapshot_id}/dataset.parquet`) and the `dataset_snapshots` row insert (row_count, excluded_count, date range, exclusion_summary) to `generate_dataset_snapshot()`, atomic — insert only after upload succeeds, so a mid-run failure leaves no partial row (contracts/dataset-pipeline.md)
- [X] T014 [US1] Implement `get_labeled_row_count(model_type, snapshot_id)` in `services/api/app/services/dataset_pipeline_service.py`
- [X] T015 [US1] Add structured logging for dataset pipeline runs (start/success/failure) to `dataset_pipeline_service.py`, consistent with the existing `ai_prediction_call`-style log event convention

**Checkpoint**: User Story 1 is fully functional and independently testable via quickstart.md Scenario 1.

---

## Phase 4: User Story 2 - New model versions are trained and only promoted if they beat the live model (Priority: P2)

**Goal**: Automated retraining against the latest labeled dataset, gated by champion-vs-challenger evaluation so a candidate only becomes eligible for rollout if it demonstrably beats the live model.

**Independent Test**: quickstart.md Scenario 2 — trigger `/training/retrain`, confirm a `model_versions` row lands as `candidate`→`shadow` (beats champion by `promotion_margin`) or `rejected` (does not), both being correct outcomes.

### Tests for User Story 2 ⚠️

> Write this test FIRST, ensure it FAILS before implementation

- [X] T016 [P] [US2] Unit test for `evaluate_and_register_candidate()` promotion-margin gating (candidate vs. no-champion-yet vs. rejected paths) in `services/api/tests/unit/test_model_lifecycle_service.py`

### Implementation for User Story 2

- [X] T017 [US2] Add `POST /training/retrain` endpoint in `services/ai` (new router or extension of the existing training router): accepts `model_type`, `dataset_storage_path`, `dataset_snapshot_id`
- [X] T018 [US2] Implement `services/ai/pipelines/training/train_from_real_data.py`: load the Parquet dataset snapshot, reuse `feature_engineering.py`'s `MATCH_QUALITY_MONOTONE_CONSTRAINTS`, train `XGBRegressor` with the same `monotone_constraints` argument as the synthetic pipeline (research.md R5)
- [X] T019 [US2] Extend `services/ai/pipelines/training/evaluate.py` with the ranking-quality metric (rate at which the model's top-ranked candidate matches the passenger's actual chosen/accepted ride — FR-007), applied alongside the existing AUC-ROC gate (`_AUC_GATE = 0.65`) and ECE calibration check as hard preconditions
- [X] T020 [US2] Wire `/training/retrain`'s response (`status: trained|gate_failed`, `storage_version`, `evaluation_score`, `auc_roc`, `expected_calibration_error`) and conditional model-registry upload — artifact uploaded only on `status: trained`, matching today's `TrainingGateError` abort-on-failure behavior (contracts/ai-service-endpoints.md)
- [X] T021 [P] [US2] Extend `services/api/app/services/ai_client.py` with a `retrain_model()` call to `POST /training/retrain`
- [X] T022 [US2] Implement `evaluate_and_register_candidate(model_type, dataset_snapshot_id, storage_version, evaluation_score)` in `services/api/app/services/model_lifecycle_service.py`: look up current champion, read `promotion_margin` from `continuous_learning_config`, insert `model_versions` as `candidate`→shadow (passes margin, or no champion yet) or `rejected` (contracts/model-lifecycle.md)
- [X] T023 [US2] Implement `advance_to_shadow(model_version_id)` in `model_lifecycle_service.py`: set `promotion_status='shadow'`, `shadow_started_at=now()`, call `POST /models/shadow` via `ai_client.py`
- [X] T024 [P] [US2] Add `POST /models/shadow` endpoint in `services/ai` (writes `candidate.json`, loads the version into `app.state.models[model_type]["candidate"]`)
- [X] T025 [US2] Implement and register `retraining_scheduler_loop()` in `services/api/app/main.py`'s `lifespan()`: hourly check of `retraining_cadence_hours` elapsed AND `min_dataset_size` (500) met via `get_labeled_row_count()`, then `generate_dataset_snapshot()` → `ai_client.retrain_model()` → `evaluate_and_register_candidate()`

**Checkpoint**: User Stories 1 AND 2 both independently functional via quickstart.md Scenarios 1–2.

---

## Phase 5: User Story 3 - New models prove themselves in shadow before serving real traffic (Priority: P3)

**Goal**: A promotion-eligible candidate runs in shadow (logged, never shown), then rolls out gradually with automatic rollback if it underperforms.

**Independent Test**: quickstart.md Scenario 3 — a `shadow`-status version produces logged, non-user-facing `shadow_score` values; a favorable burn-in report advances it to staged rollout; a seeded acceptance-rate regression triggers automatic rollback to 100% champion traffic without any `services/ai` call or deployment.

### Tests for User Story 3 ⚠️

> Extend the existing test file FIRST, ensure new cases FAIL before implementation

- [X] T026 [US3] Extend `services/api/tests/unit/test_model_lifecycle_service.py` with cases for shadow burn-in decisioning, rollout-step advancement, and rollback-margin triggering (same file as T016 — sequential, not parallel)

### Implementation for User Story 3

- [X] T027 [US3] Extend `services/api/app/services/ai_client.py`'s `score_candidates()`/`rank_candidates()` to read `shadow_score`/`shadow_model_version` from the `services/ai` response (same file as T021 — sequential)
- [X] T028 [P] [US3] Extend `services/ai`'s `/predict/match-score` and `/predict/ride-ranking` to compute and return `shadow_score`/`shadow_model_version` whenever a `candidate.json` pointer exists, strictly additive to the existing `match_score` field (contracts/ai-service-endpoints.md)
- [X] T029 [US3] Implement `get_routing_decision(model_type)` in `model_lifecycle_service.py`: weighted-random choice between `"champion"`/`"candidate"` based on the active `partial_rollout` version's `rollout_pct`
- [X] T030 [US3] Extend the existing search/ranking call site to call `get_routing_decision()`, select the champion or shadow score accordingly for what's actually shown, and record the choice as `match_events.served_variant`
- [X] T031 [US3] Implement `generate_shadow_comparison_report(model_version_id)` in `model_lifecycle_service.py`: compute `agreement_rate`/`outcome_alignment_rate` over the burn-in window, insert a `shadow_comparisons` row, and transition the version to `partial_rollout` (favorable, `rollout_pct = rollout_step_pcts[0]`) or `retired` + `POST /models/discard-candidate` (unfavorable)
- [X] T032 [US3] Implement `check_shadow_burnin_due()` in `model_lifecycle_service.py`: returns `shadow`-status versions past their configured `shadow_burnin_hours`
- [X] T033 [US3] Implement `check_rollout_progression()` and `advance_to_champion(model_version_id)` in `model_lifecycle_service.py`: rollback to `retired`/`rollout_pct=0` when the candidate's short-horizon acceptance rate underperforms the champion's by `rollback_margin` (FR-012); otherwise advance through `rollout_step_pcts` after `rollout_step_hold_hours`, calling `advance_to_champion()` (retires old champion, calls `POST /models/promote`) at the final step
- [X] T034 [P] [US3] Add `POST /models/promote` and `POST /models/discard-candidate` endpoints in `services/ai`
- [X] T035 [US3] Extend `retraining_scheduler_loop()` in `services/api/app/main.py` to also call `check_shadow_burnin_due()`, `generate_shadow_comparison_report()`, and `check_rollout_progression()` each tick (same file as T025 — sequential)

**Checkpoint**: User Stories 1, 2 AND 3 independently functional via quickstart.md Scenarios 1–3.

---

## Phase 6: User Story 4 - Model quality is continuously monitored so degradation is caught before users complain (Priority: P4)

**Goal**: Ongoing per-zone/time-window tracking of prediction distributions and acceptance/completion rates, with alerting and periodic human spot-audits.

**Independent Test**: quickstart.md Scenario 4 — run the hourly aggregation against seeded data, confirm `model_monitoring_metrics` rows appear per zone/metric_type, and a seeded degradation flips `alert_raised = true`; confirm `record_spot_audit_samples()` inserts unreviewed `model_spot_audits` rows.

### Tests for User Story 4 ⚠️

> Write this test FIRST, ensure it FAILS before implementation

- [X] T036 [P] [US4] Unit test for per-zone metric aggregation, baseline comparison, and alert-raising in `services/api/tests/unit/test_model_monitoring_service.py`

### Implementation for User Story 4

- [X] T037 [US4] Implement hourly per-zone/`metric_type` aggregation (`prediction_distribution`, `acceptance_rate`, `completion_rate`) with trailing-average baseline comparison and `alert_raised` flagging (`alert_baseline_margin`) in `services/api/app/services/model_monitoring_service.py` (FR-013, FR-014)
- [X] T038 [US4] Implement `record_spot_audit_samples()` in `model_monitoring_service.py`: sample `spot_audit_sample_size` recent `match_events` for the champion and any active `partial_rollout` candidate, insert unreviewed `model_spot_audits` rows, cadence halved within `spot_audit_early_window_hours` of `promoted_at`/`shadow_started_at` (FR-015)
- [X] T039 [US4] Implement `apply_spot_audit_finding(spot_audit_id, reviewer_admin_id, finding, trigger_rollback)` in `model_monitoring_service.py`, including the `trigger_rollback=True` path that performs the same rollback action as `check_rollout_progression()` out-of-cycle (edge case)
- [X] T040 [US4] Implement and register `model_monitoring_loop()` in `services/api/app/main.py`'s `lifespan()`: hourly cadence per NFR-004, calling the Phase 6 aggregation and spot-audit sampling

**Checkpoint**: All four user stories independently functional via quickstart.md Scenarios 1–4.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end verification and consistency across all four stories.

- [X] T041 [P] Integration test in `services/api/tests/integration/test_continuous_learning_flow.py`: seeded `match_events`/`match_outcomes` → dataset snapshot → mock retrain → promotion decision → rollout routing → rollback trigger
- [X] T042 [P] Unit tests for `services/ai/pipelines/training/train_from_real_data.py` and `evaluate.py`'s ranking-quality metric, in `services/ai/tests/`
- [X] T043 Run quickstart.md Scenarios 1–4 plus the config redeploy-free validation (edit `continuous_learning_config` via SQL, confirm the change is reflected within 30s with no restart)
- [ ] T044 Review structured logging across `dataset_pipeline_service.py`, `model_lifecycle_service.py`, and `model_monitoring_service.py` for consistency with the existing `ai_prediction_call`/`ai_training_call` log-event convention

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (schema and config service everything else reads/writes)
- **User Story 1 (Phase 3)**: Depends only on Foundational
- **User Story 2 (Phase 4)**: Depends on Foundational; consumes US1's `generate_dataset_snapshot()`/`get_labeled_row_count()` output but does not require US1's tasks to be "complete" beyond those two functions existing
- **User Story 3 (Phase 5)**: Depends on Foundational and on US2's `model_versions` state machine (`evaluate_and_register_candidate`, `advance_to_shadow`) existing — extends the same `model_lifecycle_service.py` and `ai_client.py` files US2 created
- **User Story 4 (Phase 6)**: Depends on Foundational and on `model_versions` existing (US2); independently valuable even before US3's shadow/rollout states are ever reached, since it can monitor the single current champion from day one
- **Polish (Phase 7)**: Depends on all four user stories being complete

### Within Each User Story

- Tests written and expected to fail before implementation
- `services/ai` endpoint/pipeline work and `services/api` service-layer work can proceed in parallel within a story (different codebases), but wiring tasks that call across them are sequential
- Story checkpoint reached only once all its tasks (including test) are done

### Parallel Opportunities

- T001/T002 (Setup) in parallel
- T005/T007 (Foundational) in parallel — different services, no shared file
- Within each story, tasks marked [P] touch different files and have no incomplete dependency
- T041/T042 (Polish) in parallel — different test suites

---

## Parallel Example: User Story 2

```bash
# T016 (test) and T021 (ai_client.py) touch different files from the services/ai work:
Task: "Unit test for evaluate_and_register_candidate() in services/api/tests/unit/test_model_lifecycle_service.py"
Task: "Extend services/api/app/services/ai_client.py with retrain_model() call"

# T017-T020 (services/ai training endpoint) can proceed alongside T022-T023 (services/api lifecycle service)
# since they're different codebases wired together only at T025.
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run quickstart.md Scenario 1 against locally-seeded data (per spec.md Assumptions, US1 can be validated now without waiting for real production traffic)

### Incremental Delivery

1. Setup + Foundational → schema and config live
2. User Story 1 → labeled dataset snapshots producible on demand (MVP — independently valuable even before any retraining exists, per spec.md's "Why this priority")
3. User Story 2 → automated retraining with champion-vs-challenger gating
4. User Story 3 → shadow burn-in and staged, auto-rollback rollout
5. User Story 4 → continuous monitoring and spot audits
6. Each story is independently testable via its quickstart.md scenario before moving to the next

### Note on end-to-end validation timing

Per spec.md's Assumptions: User Stories 2–4 (retraining, shadow rollout, monitoring) can be built and unit-tested now, but cannot be meaningfully exercised against *real* production data until the platform is redeployed and real traffic accumulates (≥500 completed rides). This does not block implementation — quickstart.md's locally-seeded scenarios validate all four stories' logic pre-launch.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to its spec.md user story for traceability
- `model_lifecycle_service.py` and `ai_client.py` are each built incrementally across US2 and US3 — tasks touching them within a later story are marked sequential (no [P]) relative to the earlier story's tasks on the same file, even though the stories themselves are independently testable once their tasks land
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently via its quickstart.md scenario
