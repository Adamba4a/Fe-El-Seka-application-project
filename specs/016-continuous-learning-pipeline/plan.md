# Implementation Plan: Continuous Learning Pipeline

**Branch**: `016-continuous-learning-pipeline` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/016-continuous-learning-pipeline/spec.md`

## Summary

Close the loop opened by `013-match-learning-foundation`: periodically turn logged `match_events`/`match_outcomes` into a labeled real-outcome dataset, retrain `match_score` and `ride_ranker` candidates against it, gate promotion on a champion-vs-challenger evaluation margin, prove a promoted candidate in shadow mode and a staged percentage rollout with automatic rollback, and continuously monitor the live model's prediction distribution and acceptance/completion rates per zone with periodic human spot-audits.

The design deliberately extends existing mechanisms rather than introducing new infrastructure: the dataset ETL and all new governance state live in `services/api` (Postgres, asyncpg) because `services/ai` has no database access; retraining/evaluation/dual-scoring extend the existing `services/ai` training pipeline and Storage-based model registry; scheduling reuses the codebase's only periodic-job mechanism (`asyncio.create_task` loops in `services/api`'s `lifespan`); and all new tunables (thresholds, margins, cadences) live in one new singleton config table refreshed in-process, mirroring `pricing_config`/`ranking_config`.

Per the scope correction recorded in spec.md, pricing is excluded — fare calculation has been deterministic-only since 2026-07-14, so there is no pricing model to retrain. This plan covers `match_score` and `ride_ranker` only.

## Technical Context

**Language/Version**: Python 3.11 (both `services/api` and `services/ai`, matching existing services)

**Primary Dependencies**: FastAPI, asyncpg (`services/api`); FastAPI, xgboost, scikit-learn, joblib, pandas, pyarrow, supabase-py (`services/ai`) — all already in use, no new dependencies added. No scheduler library is introduced (see research.md R1).

**Storage**: Supabase Postgres (new tables in `services/api`'s existing schema, asyncpg raw SQL) for all governance/audit state; existing Supabase Storage `model-registry` bucket (extended, not replaced) for model artifacts; a new `training-datasets` Storage bucket for dataset snapshot parquet files (metadata rows live in Postgres, bulk rows live in Storage — mirrors the existing artifact/metadata split already used for models).

**Testing**: pytest + pytest-asyncio for `services/api` (new asyncpg-backed tests — no existing fixture convention to extend, per research.md R6, so this feature establishes the first ones) and `services/ai` (`asyncio_mode = "auto"` already configured; no existing test files to extend).

**Target Platform**: Linux server via uvicorn (same deployment shape as all existing services; no new runtime).

**Project Type**: Monorepo, backend-only — extends `services/api` and `services/ai`; no changes to `apps/main` or `apps/admin` (per spec Out-of-Scope).

**Performance Goals**: Zero added latency on passenger/driver-facing request paths (search, booking, ranking) per NFR-001/NFR-003 — dataset ETL, retraining, monitoring, and shadow scoring all run off the response-blocking path. Monitoring detection lag ≤ 1 hour (NFR-004/SC-004).

**Constraints**: `services/ai` has no Postgres access (confirmed: no asyncpg/DB config anywhere in `services/ai/app/config.py`) — the dataset ETL and all governance/audit tables MUST live in `services/api`, not `services/ai`. Retraining MUST reuse the existing monotonicity-constrained, calibration-gated training path (`MATCH_QUALITY_MONOTONE_CONSTRAINTS`, AUC-ROC gate, ECE calibration check) rather than a fresh training routine, so the 2026-07-04/07-14 recalibration fixes cannot be silently reintroduced as regressions. Shadow/rollout dual-scoring must not double user-facing latency.

**Scale/Scope**: ~100 rides/day expected launch volume; 500-completed-ride minimum dataset threshold before automated retraining/promotion activates; weekly default retraining cadence; hourly monitoring cadence; 2 live model types (`match_score`, `ride_ranker`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Driver-First Route Sharing | Not affected — this feature changes how match/ranking models are trained and governed, not the route-sharing model itself. | PASS (N/A) |
| II. Route Intelligence Over Geographic Proximity | Directly serves this principle: real-outcome retraining is a strict improvement over synthetic-bootstrapped route intelligence, and champion-vs-challenger gating prevents it from regressing. | PASS |
| III. Trust Before Transportation | FR-003 explicitly excludes bot/fraud/spam-flagged accounts (via existing `reports`/`report_resolution_action`/`profiles.verification_status='suspended'` mechanism from `014-trust-community`) from training data, so untrusted behavior cannot poison the learned model. | PASS |
| IV. AI-Augmented Transportation | Core purpose of this feature — keeps AI models improving from real behavior instead of staying frozen at launch-time synthetic calibration, while explicit champion/shadow/rollout gating keeps AI advisory-safe (never an unreviewed model can reach 100% traffic instantly, per SC-003). | PASS |
| V. Mobile-First UX | Not affected — no UI changes (spec Out-of-Scope). | PASS (N/A) |
| VI. Modular Domain-Driven Architecture | New logic is added as new service modules (`services/api/app/services/dataset_pipeline_service.py`, `model_lifecycle_service.py`, `model_monitoring_service.py`) following the existing one-module-per-domain-concern convention; no cross-cutting God-service introduced. | PASS |
| VII. Shared Foundations, Independent Applications | All new work is backend/AI-service only; `apps/main` and `apps/admin` are untouched, preserving independence. Any future admin visibility is called out as a separate follow-up extension, not bundled in here. | PASS |

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/016-continuous-learning-pipeline/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── dataset-pipeline.md
│   ├── model-lifecycle.md
│   └── ai-service-endpoints.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
supabase/migrations/
└── 20260802000002_phase13_continuous_learning.sql   # NEW — all new tables/enums for this feature

services/api/
├── app/
│   ├── services/
│   │   ├── dataset_pipeline_service.py       # NEW — ETL: match_events+match_outcomes → labeled dataset snapshot (parquet in Storage + metadata row)
│   │   ├── model_lifecycle_service.py        # NEW — model_versions state machine (candidate→shadow→partial_rollout→champion/retired), rollout routing decision, promotion/rollback logic
│   │   ├── model_monitoring_service.py       # NEW — hourly per-zone metric aggregation, baseline comparison, alert raising, spot-audit sampling
│   │   ├── continuous_learning_config_service.py  # NEW — singleton config cache + refresh loop, mirrors ranking_config_service.py
│   │   └── ai_client.py                      # EXTENDED — add retrain_model(), promote_model() calls; score_candidates()/rank_candidates() extended to read shadow_score/shadow_model_version from response
│   ├── search/ (or existing search router/service)
│   │   └── (existing match/ranking call site)  # EXTENDED — routes a fraction of requests to the candidate score per model_versions.rollout_pct; match_logging_service records served_variant
│   └── main.py                                # EXTENDED — register 2 new asyncio.create_task loops (retraining_scheduler_loop, model_monitoring_loop) in lifespan, cancelled on shutdown like existing loops
└── tests/
    ├── unit/
    │   ├── test_dataset_pipeline_service.py    # NEW
    │   ├── test_model_lifecycle_service.py     # NEW
    │   └── test_model_monitoring_service.py    # NEW
    └── integration/
        └── test_continuous_learning_flow.py    # NEW — end-to-end: seeded match_events/outcomes → dataset snapshot → mock retrain → promotion decision → rollout routing → rollback trigger

services/ai/
├── app/
│   ├── routers/
│   │   ├── models.py                          # EXTENDED — new /models/promote endpoint (copies a specific version to latest.json); existing /models/reload extended to also load a "candidate" slot from candidate.json if present
│   │   └── predict.py                         # EXTENDED — /predict/match-score and /predict/ride-ranking compute + return shadow_score/shadow_model_version whenever a candidate slot is loaded, alongside the existing champion score
│   └── services/
│       └── model_registry.py                  # EXTENDED — add candidate.json read/write helpers (parallel to existing latest.json helpers), reusing the same atomic-upload convention
└── pipelines/
    └── training/
        ├── train_from_real_data.py            # NEW — loads a dataset snapshot parquet (instead of pipelines/dataset's synthetic generator), reuses existing feature_engineering.py + MATCH_QUALITY_MONOTONE_CONSTRAINTS, same AUC-gate/ECE evaluate.py checks
        └── evaluate.py                        # EXTENDED — add the ranking-quality metric (top-ranked-candidate-matches-actual-choice rate) alongside existing AUC/ECE checks, for champion-vs-challenger comparison
```

**Structure Decision**: Monorepo, backend-only extension (matches Fe El Seka's existing `services/api` + `services/ai` split). No new top-level project or service is introduced — this feature is entirely new modules/tables layered onto the two existing backend services, per the Constraints above (no DB access in `services/ai`, no scheduler beyond `asyncio.create_task`).

## Complexity Tracking

*No Constitution Check violations — table not needed.*
