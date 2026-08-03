# Phase 0 Research: Continuous Learning Pipeline

All Technical Context fields were resolvable from the existing codebase — no unresolved `NEEDS CLARIFICATION` markers remain. Findings below are grounded in direct reads of the current repository, not assumptions.

## R1: Scheduling mechanism

**Decision**: Reuse the existing `asyncio.create_task(...)` background-loop pattern registered in `services/api/app/main.py`'s `lifespan()`. Add two new loops: `retraining_scheduler_loop()` (checks hourly whether the configured retraining cadence has elapsed and the 500-ride threshold is met) and `model_monitoring_loop()` (runs hourly per NFR-004).

**Rationale**: This is the *only* periodic-job mechanism anywhere in the stack. `services/api/app/main.py` already registers 7 such loops (`email_retry_loop` 60s, `booking_expiry_loop` 600s, `pricing_config_refresh_loop` 30s, `ranking_config_refresh_loop` 30s, `moderation_config_refresh_loop`, `notification_dispatcher_loop` 30s, `driver_reminder_loop` 300s), each following `while True: await asyncio.sleep(N); try: <work> except Exception: log`, started at `lifespan` entry and `.cancel()`-ed in reverse order at shutdown. Introducing Celery, APScheduler, or a cron container would be a genuine architectural deviation with no precedent in this codebase, adding an operational surface (a new process/container) the constitution's "favor simplicity" and existing monorepo/Docker Compose shape don't currently need at ~100 rides/day.

**Alternatives considered**:
- **Celery + Redis/RabbitMQ broker**: rejected — no message broker exists in `docker-compose.yml`; massive operational overhead for a twice-a-day-at-most job cadence.
- **APScheduler**: rejected — adds a new dependency and a persistence concern (job store) for no benefit over the existing in-process loop pattern at this scale.
- **External cron container hitting an internal endpoint**: rejected — adds a container and an unauthenticated-internal-endpoint attack surface for something `asyncio.sleep` already solves cleanly in-process.

## R2: Where the dataset ETL and governance state live

**Decision**: All new logic that reads `match_events`/`match_outcomes` or needs Postgres — the dataset ETL, the model-version ledger, monitoring metrics, spot audits, and all new config — lives in `services/api`. `services/ai` remains stateless/DB-free, receiving only a dataset file path (Storage) and returning scores/evaluation results over HTTP, exactly as it does today.

**Rationale**: Confirmed via direct inspection of `services/ai/app/config.py` — its `Settings` class has no Postgres/asyncpg/database URL field at all, only `supabase_url`, `supabase_service_role_key` (used solely for the Storage client), `model_registry_bucket`, `ai_version`. `services/ai/pyproject.toml` has no `asyncpg`/`sqlalchemy`/`psycopg` dependency. This is a real architectural boundary, not an oversight — `services/api` "owns business logic" and "databases are the source of truth" per the constitution's Architecture Standards, and `services/ai` is a "dedicated AI service" that computes, it doesn't persist. Building the ETL inside `services/ai` would require adding a database dependency to a service explicitly designed not to have one.

**Alternatives considered**:
- **Add asyncpg to `services/ai` so it can query `match_events` directly**: rejected — breaks the established service boundary for no real benefit; `services/api` already has full access to these tables and can hand `services/ai` a ready-made dataset file instead.
- **Have `services/api` query row-by-row and POST batches to `services/ai` per training run**: rejected — needlessly chatty and reinvents what a Storage file transfer already does simply; the existing model artifact flow already proves the "produce a file in Storage, tell the other service its path" pattern works well here.

## R3: Model registry extension for candidate/shadow/champion state

**Decision**: Keep `services/ai`'s Storage-based registry (`{model_type}/{version}/model.joblib` + `metadata.json` + `latest.json`) exactly as-is for artifact storage, and add a parallel `candidate.json` pointer file per model type (same bucket, same atomic-write convention) for "the currently shadow/rollout candidate, if any." All *governance* state (which version is candidate/shadow/partial_rollout/champion/retired, rollout percentage, evaluation scores, promotion decisions, audit trail) lives in a new Postgres table `model_versions` in `services/api`, which is the single source of truth `model_lifecycle_service.py` reads and writes. `latest.json`/`candidate.json` in Storage are just serving-time pointers `services/ai` uses to know which two artifacts to load into memory — never the authority on promotion status.

**Rationale**: The existing registry (confirmed via `services/ai/app/services/model_registry.py` and `specs/002-ai-foundation/contracts/model-registry.md`) has exactly one pointer per model type (`latest.json`) and zero queryable/auditable state beyond that — no champion/candidate/shadow concept exists today. FR-016 requires "a complete history of model versions, their training dataset snapshot, evaluation scores, promotion decisions, and rollout outcomes, for auditability" — that's inherently relational, queryable state, which belongs in Postgres (where `services/api` already tracks similar audit trails, e.g. `match_events`/`match_outcomes`), not scattered across Storage JSON blobs. Splitting cleanly (Storage = artifact bytes + "what to load," Postgres = governance history + "why") keeps each system doing what it already does well and avoids the registry needing to reimplement transactional state.

**Alternatives considered**:
- **Store all governance state in `metadata.json` per version in Storage**: rejected — not queryable (SC-005's "retrievable audit trail" and FR-016's history requirement need SQL-level querying, e.g. "all rejected versions with their evaluation scores"), and Storage has no transactional guarantees for updating a "current candidate" pointer under concurrent writes the way a Postgres row with `UPDATE ... WHERE` does.
- **Replace the Storage registry entirely with a DB-BLOB-backed one**: rejected — needlessly rewrites a working, tested artifact-storage mechanism; the gap is only the missing governance-state layer, not the artifact storage itself.

## R4: Config/tunables mechanism

**Decision**: One new singleton table, `continuous_learning_config`, holding every tunable from NFR-005 and the spec's Assumptions (min dataset size, retraining cadence, promotion margin, shadow burn-in duration, rollout step percentages, rollback margin, monitoring interval, alert baseline margin, spot-audit sample size/frequency) — refreshed in-process on a timer via a new `continuous_learning_config_service.py`, structurally identical to `ranking_config_service.py`.

**Rationale**: `pricing_config`, `ranking_config`, and `moderation_config` already establish this exact pattern in this codebase: a singleton row, edited directly in the Supabase dashboard (no admin UI needed), an in-process cache dict guarded by `asyncio.Lock`, a `while True: sleep(30); refresh` loop, and a fallback-to-hardcoded-defaults path if the table is briefly unavailable (`pricing_service.py`'s `_DEFAULTS`). Reusing this satisfies NFR-005 ("adjustable without a code deployment") with zero new infrastructure, and `ranking_config_service.py`'s own comment ("mirrors pricing_config's shape and refresh convention") shows this is the codebase's intended way to add a new tunable domain.

**Alternatives considered**:
- **One config table per concern (retraining_config, rollout_config, monitoring_config)**: rejected — over-splits a set of values that are all read together by the same small number of loops/services; three near-identical singleton tables with three near-identical refresh loops is needless duplication for values that change together operationally.
- **Environment variables**: rejected — fails NFR-005 outright (changing an env var requires a redeploy/restart).

## R5: Retraining must not regress the 2026-07-04/07-14 calibration fixes

**Decision**: The new real-data training path (`pipelines/training/train_from_real_data.py`) reuses `feature_engineering.py`'s `MATCH_QUALITY_MONOTONE_CONSTRAINTS`, trains `XGBRegressor` with the same `monotone_constraints` argument, and reuses `evaluate.py`'s existing AUC-ROC gate (`_AUC_GATE = 0.65`) and Expected Calibration Error check as hard preconditions before a candidate is even eligible for champion-vs-challenger comparison — a candidate that fails either gate is rejected before evaluation, exactly like today's synthetic pipeline (`pipelines/training/run.py` aborts with `TrainingGateError` and uploads nothing).

**Rationale**: Confirmed via direct read of `feature_engineering.py`, `train_match_score.py`, and `evaluate.py`: the current pipeline already encodes hard-won lessons (monotonicity prevents a previously-shipped "detour distance improves score" inversion; the ECE check exists specifically because a prior bug showed 0.98 AUC while real-world scores were miscalibrated ~10x). A fresh training routine for real data that skipped these checks could silently reintroduce either bug the moment it retrains on a real-world sample where these pathologies re-emerge (e.g., a sparse zone with few examples). Reusing the exact same gates, applied to real-outcome training examples instead of synthetic ones, is both simpler (no new eval logic to design) and directly satisfies the plan's "must reuse the calibration and monotonicity fixes" Technical Consideration.

**Alternatives considered**:
- **New evaluation logic tailored to real data**: rejected — real data doesn't change what these gates are protecting against (miscalibration, non-monotonic feature response); re-deriving equivalent checks from scratch risks reintroducing the exact bugs the existing gates were built to catch.

## R6: Testing approach

**Decision**: Establish new pytest test files for this feature's new services (`services/api/tests/unit/test_dataset_pipeline_service.py`, `test_model_lifecycle_service.py`, `test_model_monitoring_service.py`, plus an integration test) and for the new `services/ai` real-data training path — following the dependency/config each service's `pyproject.toml` already declares (`pytest-asyncio`, `asyncio_mode = "auto"` for `services/ai`).

**Rationale**: Confirmed both `services/api/tests/` and `services/ai/tests/` exist as directories but are currently empty (no `test_*.py` files, no `conftest.py`) despite test dependencies being present in both `pyproject.toml` files. There is no existing fixture/factory convention to extend — this feature's tests will be the first real ones for either service, so they should be written straightforwardly (direct asyncpg test-DB setup for `services/api`, direct pandas/numpy fixtures for `services/ai`'s training tests) rather than inventing a fixture framework speculatively.

**Alternatives considered**:
- **Defer test-infrastructure decisions to `/speckit-tasks`**: partially adopted — this research only establishes *where* tests live and *what* they cover; exact fixture helper design is left to the tasks/implementation phase since no existing convention constrains it either way.

## R7: Shadow scoring and rollout routing split

**Decision**: `services/ai`'s predict endpoints (`/predict/match-score`, `/predict/ride-ranking`) become pure dual-scorers: whenever a `candidate.json` pointer exists, compute and return both the champion score and a `shadow_score`/`shadow_model_version`, always, for every request — with no knowledge of rollout percentage or which one "counts." `services/api`'s existing call site (`ai_client.py` → search/ranking flow) owns the actual routing decision: it reads `model_versions.rollout_pct` for the current candidate (via `model_lifecycle_service.py`, cached like the other config services) and performs a weighted random choice between champion and candidate score to decide what's actually shown to the passenger/driver, recording the choice as `match_events.served_variant`.

**Rationale**: Matches the constitution's "backend services own business logic, AI service computes" split already established by `012-ai-application` (fare's AI-removal precedent: `services/ai` computes/predicts, `services/api` decides what to do with it). It also means a rollback (FR-012) is a pure `services/api`-side state change (`rollout_pct → 0`) with no `services/ai` deployment or reload involved — satisfying "without requiring a code deployment to revert" with the minimum possible blast radius. `services/ai` computing both scores on every request (not conditionally) keeps its logic simple and stateless, and is cheap since both models are already loaded in memory (`app.state.models`) once resident.

**Alternatives considered**:
- **`services/ai` decides which score to return based on a passed-in rollout percentage**: rejected — pushes business/governance logic (rollout state) into the AI service, which the constitution and existing precedent keep computation-only; also would require `services/api` to pass rollout state on every request instead of `services/ai` just always returning both scores.

## R8: Dataset snapshot storage shape

**Decision**: Bulk labeled training rows are written as a Parquet file to a new Supabase Storage bucket `training-datasets`, path `{model_type}/{snapshot_id}/dataset.parquet` (mirrors the existing `model-registry` bucket's `{model_type}/{version}/...` layout). A lightweight metadata row is inserted into a new Postgres table `dataset_snapshots` (snapshot id, model_type, storage_path, row_count, date range, exclusion summary, created_at) for querying/auditability (SC-005) without loading the full dataset.

**Rationale**: Mirrors the proven artifact/metadata split already used for models (`model.joblib` + `metadata.json` in Storage). `services/ai`'s existing pipeline already reads/writes Parquet (`pyarrow` is a declared dependency, and `pipelines/features/engineer.py`/`pipelines/dataset/` already produce/consume Parquet-shaped data under `services/ai/data/features/`), so this is a natural fit rather than introducing a new file format or a giant Postgres table of training rows.

**Alternatives considered**:
- **Store every training example as a Postgres row**: rejected — at even modest scale this duplicates `match_events`/`match_outcomes` data into a much wider table for no querying benefit beyond what the lightweight metadata row already provides; Parquet is the format the training pipeline already consumes.
