from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from app.core.database import get_pool
from app.services import ai_client, dataset_pipeline_service, model_lifecycle_service
from app.services.ai_client import AIServiceUnavailableError
from app.services.continuous_learning_config_service import get_continuous_learning_config

logger = logging.getLogger(__name__)

_MODEL_TYPES = ("match_score", "ride_ranker")


async def _cadence_elapsed(model_type: str, cadence_hours: int) -> bool:
    """No champion/candidate version ever trained yet -> cadence is considered
    elapsed immediately, so the first retrain isn't gated on a prior run that
    never happened."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT created_at FROM public.model_versions
            WHERE model_type = $1
            ORDER BY created_at DESC LIMIT 1
            """,
            model_type,
        )
    if row is None:
        return True
    elapsed_hours = (datetime.now(timezone.utc) - row["created_at"]).total_seconds() / 3600
    return elapsed_hours >= cadence_hours


async def _attempt_retrain(model_type: str) -> None:
    """T025: generate_dataset_snapshot() -> ai_client.retrain_model() ->
    evaluate_and_register_candidate(), gated on retraining_cadence_hours and
    min_dataset_size (contracts/dataset-pipeline.md: a mid-run failure is
    logged and retried on the next tick — no partial state to clean up since
    every step here is already individually atomic)."""
    config = get_continuous_learning_config()
    if not await _cadence_elapsed(model_type, config["retraining_cadence_hours"]):
        return

    # Cheap count-only pass before paying for a full Parquet write + Storage
    # upload + dataset_snapshots insert — while below min_dataset_size (e.g.
    # the platform's first weeks) no model_versions row is ever written, so
    # _cadence_elapsed keeps returning True every single tick; without this
    # check that would mean a full snapshot generated and uploaded hourly
    # forever.
    eligible_count = await dataset_pipeline_service.count_eligible_rows()
    if eligible_count < config["min_dataset_size"]:
        logger.info(json.dumps({
            "event": "retraining_scheduler_tick",
            "model_type": model_type,
            "outcome": "skipped_insufficient_data",
            "row_count": eligible_count,
            "min_dataset_size": config["min_dataset_size"],
        }))
        return

    snapshot = await dataset_pipeline_service.generate_dataset_snapshot(model_type)

    try:
        result = await ai_client.retrain_model(
            model_type, snapshot["storage_path"], str(snapshot["snapshot_id"])
        )
    except AIServiceUnavailableError as exc:
        logger.warning("retraining_scheduler: AI service unavailable for %s: %s", model_type, exc)
        return

    if result.get("status") != "trained":
        logger.info(json.dumps({
            "event": "retraining_scheduler_tick",
            "model_type": model_type,
            "outcome": "gate_failed",
            "reason": result.get("reason"),
        }))
        return

    await model_lifecycle_service.evaluate_and_register_candidate(
        model_type,
        snapshot["snapshot_id"],
        result["storage_version"],
        result["evaluation_score"],
    )
    logger.info(json.dumps({
        "event": "retraining_scheduler_tick",
        "model_type": model_type,
        "outcome": "retrained",
        "storage_version": result["storage_version"],
    }))


async def _advance_shadow_and_rollout() -> None:
    """T035: each tick, also drive the shadow burn-in -> rollout -> champion
    state machine (contracts/model-lifecycle.md) — due shadow versions get a
    comparison report generated, and any active partial_rollout gets checked
    for rollback/advancement."""
    due = await model_lifecycle_service.check_shadow_burnin_due()
    for row in due:
        try:
            await model_lifecycle_service.generate_shadow_comparison_report(row["id"])
        except Exception as exc:
            logger.error("shadow_comparison_report error for %s: %s", row["id"], exc)

    try:
        await model_lifecycle_service.check_rollout_progression()
    except Exception as exc:
        logger.error("check_rollout_progression error: %s", exc)


async def retraining_scheduler_loop() -> None:
    """Background task: hourly check of whether real-data retraining is due
    for each model type (research.md R1 — reuses the existing in-process loop
    pattern already used by the other 7 loops in main.py, no new scheduler
    dependency). Also drives shadow burn-in and rollout progression each tick
    (T035) — both are cheap no-ops when nothing is in shadow/partial_rollout."""
    while True:
        for model_type in _MODEL_TYPES:
            try:
                await _attempt_retrain(model_type)
            except Exception as exc:
                logger.error("retraining_scheduler_loop error for %s: %s", model_type, exc)
        try:
            await _advance_shadow_and_rollout()
        except Exception as exc:
            logger.error("retraining_scheduler_loop shadow/rollout tick error: %s", exc)
        await asyncio.sleep(3600)
