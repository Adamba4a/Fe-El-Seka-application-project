from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from app.core.database import get_pool
from app.services import ai_client
from app.services.continuous_learning_config_service import get_continuous_learning_config

logger = logging.getLogger(__name__)


def _decide_promotion(
    evaluation_score: float,
    champion_evaluation_score: float | None,
    promotion_margin: float,
) -> tuple[str, float]:
    """contracts/model-lifecycle.md evaluate_and_register_candidate steps 3-4:
    no champion yet -> always candidate; otherwise candidate only if the
    challenger beats the champion by at least promotion_margin, else rejected."""
    if champion_evaluation_score is None:
        return "candidate", round(evaluation_score, 4)
    # Round to 4dp (comparison_margin is NUMERIC(6,4)) before comparing, so
    # scores that are conceptually equal to the margin boundary aren't flipped
    # by binary float subtraction artifacts (e.g. 0.82 - 0.80 != 0.02 in IEEE754).
    margin = round(evaluation_score - champion_evaluation_score, 4)
    if margin >= promotion_margin:
        return "candidate", margin
    return "rejected", margin


async def evaluate_and_register_candidate(
    model_type: str,
    dataset_snapshot_id: uuid.UUID,
    storage_version: str,
    evaluation_score: float,
) -> dict[str, Any]:
    """contracts/model-lifecycle.md: registers a freshly trained model version,
    gated against the current champion by `promotion_margin`. A candidate that
    beats the gate is immediately advanced to shadow; one that doesn't is
    recorded as rejected and never served."""
    pool = get_pool()
    async with pool.acquire() as conn:
        champion = await conn.fetchrow(
            """
            SELECT id, evaluation_score FROM public.model_versions
            WHERE model_type = $1 AND promotion_status = 'champion'
            ORDER BY promoted_at DESC LIMIT 1
            """,
            model_type,
        )
        champion_score = float(champion["evaluation_score"]) if champion else None
        promotion_margin = get_continuous_learning_config()["promotion_margin"]
        status, margin = _decide_promotion(evaluation_score, champion_score, promotion_margin)

        model_version_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO public.model_versions
                (id, model_type, storage_version, dataset_snapshot_id,
                 promotion_status, evaluation_score, comparison_margin)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            model_version_id,
            model_type,
            storage_version,
            dataset_snapshot_id,
            status,
            evaluation_score,
            margin,
        )

    logger.info(json.dumps({
        "event": "model_promotion_decision",
        "model_type": model_type,
        "model_version_id": str(model_version_id),
        "promotion_status": status,
        "comparison_margin": margin,
    }))

    if status == "candidate":
        await advance_to_shadow(model_version_id)

    return {
        "model_version_id": model_version_id,
        "promotion_status": status,
        "comparison_margin": margin,
    }


async def advance_to_shadow(model_version_id: uuid.UUID) -> None:
    """contracts/model-lifecycle.md: marks a candidate as shadow-active and
    activates the corresponding slot in services/ai."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT model_type, storage_version FROM public.model_versions WHERE id = $1",
            model_version_id,
        )
        await conn.execute(
            """
            UPDATE public.model_versions
            SET promotion_status = 'shadow', shadow_started_at = now()
            WHERE id = $1
            """,
            model_version_id,
        )

    await ai_client.activate_shadow_candidate(row["model_type"], row["storage_version"])
