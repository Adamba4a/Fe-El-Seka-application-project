from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timezone
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


# ── T029: routing decision (champion vs. candidate) ──────────────────────────
# In-process cache of active partial_rollout versions, refreshed on a 30s loop
# — get_routing_decision() is called on the live search request path and must
# never touch the DB (mirrors continuous_learning_config_service.py's pattern).

_rollout_cache: dict[str, dict[str, Any]] = {}
_rollout_cache_lock = asyncio.Lock()


async def refresh_rollout_cache() -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT model_type, storage_version, rollout_pct
            FROM public.model_versions
            WHERE promotion_status = 'partial_rollout'
            """
        )
    new_cache = {
        row["model_type"]: {
            "storage_version": row["storage_version"],
            "rollout_pct": float(row["rollout_pct"]),
        }
        for row in rows
    }
    async with _rollout_cache_lock:
        _rollout_cache.clear()
        _rollout_cache.update(new_cache)


async def init_rollout_cache() -> None:
    """Best-effort initial load at startup, mirroring
    continuous_learning_config_service's init pattern — falls back to
    champion-only routing (empty cache) until the refresh loop syncs."""
    try:
        await refresh_rollout_cache()
    except Exception as exc:
        logger.warning("rollout cache unavailable at startup (%s) — defaulting to champion-only routing", exc)


async def rollout_cache_refresh_loop() -> None:
    while True:
        await asyncio.sleep(30)
        try:
            await refresh_rollout_cache()
        except Exception as exc:
            logger.error("rollout cache refresh error: %s", exc)


def get_routing_decision(model_type: str) -> dict[str, Any]:
    """contracts/model-lifecycle.md: weighted-random champion/candidate choice
    based on the cached partial_rollout version's rollout_pct. No active
    rollout for model_type -> always champion."""
    entry = _rollout_cache.get(model_type)
    if entry is None:
        return {"variant": "champion", "candidate_storage_version": None}
    if random.random() < entry["rollout_pct"] / 100:
        return {"variant": "candidate", "candidate_storage_version": entry["storage_version"]}
    return {"variant": "champion", "candidate_storage_version": None}


# ── T032: shadow burn-in due check ────────────────────────────────────────────

async def check_shadow_burnin_due() -> list[dict[str, Any]]:
    """contracts/model-lifecycle.md: returns shadow-status versions that have
    held shadow status for at least the configured shadow_burnin_hours."""
    config = get_continuous_learning_config()
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, model_type, storage_version, shadow_started_at
            FROM public.model_versions
            WHERE promotion_status = 'shadow'
              AND shadow_started_at <= now() - make_interval(hours => $1)
            """,
            config["shadow_burnin_hours"],
        )
    return [dict(r) for r in rows]


# ── T031: shadow comparison report ────────────────────────────────────────────

async def generate_shadow_comparison_report(model_version_id: uuid.UUID) -> dict[str, Any]:
    """contracts/model-lifecycle.md: compares the candidate's implicit top
    choice (MAX(shadow_score) per search — valid throughout burn-in since
    get_routing_decision() never selects "candidate" before a partial_rollout
    row exists, so match_events.rank_position=1 reliably reflects the
    champion-only order the whole time) against the champion's actual top
    choice (rank_position=1), and against the passenger's actual accepted
    ride where resolved. "Favorable" is gated on
    shadow_min_agreement_rate/shadow_min_outcome_alignment_rate — spec.md
    never named a concrete threshold for this, so these two
    continuous_learning_config fields were added specifically to fill that
    gap (20260803000002 migration), keeping it tunable per NFR-005 rather
    than a hardcoded constant."""
    config = get_continuous_learning_config()
    pool = get_pool()

    async with pool.acquire() as conn:
        candidate = await conn.fetchrow(
            "SELECT model_type, storage_version, shadow_started_at FROM public.model_versions WHERE id = $1",
            model_version_id,
        )
        champion = await conn.fetchrow(
            """
            SELECT id FROM public.model_versions
            WHERE model_type = $1 AND promotion_status = 'champion'
            ORDER BY promoted_at DESC LIMIT 1
            """,
            candidate["model_type"],
        )

        burn_in_start = candidate["shadow_started_at"]
        burn_in_end = datetime.now(timezone.utc)

        stats = await conn.fetchrow(
            """
            WITH windowed AS (
                SELECT me.id, me.search_id, me.candidate_ride_id, me.rank_position, me.shadow_score
                FROM public.match_events me
                WHERE me.shadow_model_version = $1
                  AND me.created_at BETWEEN $2 AND $3
            ),
            per_search AS (
                SELECT
                    search_id,
                    (ARRAY_AGG(candidate_ride_id ORDER BY rank_position ASC))[1] AS champion_top,
                    (ARRAY_AGG(candidate_ride_id ORDER BY shadow_score DESC NULLS LAST))[1] AS candidate_top
                FROM windowed
                GROUP BY search_id
            ),
            outcomes AS (
                SELECT DISTINCT w.search_id, w.candidate_ride_id AS accepted_ride_id
                FROM windowed w
                JOIN public.match_outcomes mo ON mo.match_event_id = w.id
                WHERE mo.transition_type = 'accepted'
            )
            SELECT
                COUNT(*) AS sample_size,
                AVG(CASE WHEN ps.champion_top = ps.candidate_top THEN 1.0 ELSE 0.0 END) AS agreement_rate,
                (
                    SELECT AVG(CASE WHEN ps2.candidate_top = o.accepted_ride_id THEN 1.0 ELSE 0.0 END)
                    FROM per_search ps2 JOIN outcomes o ON o.search_id = ps2.search_id
                ) AS outcome_alignment_rate
            FROM per_search ps
            """,
            candidate["storage_version"], burn_in_start, burn_in_end,
        )

        agreement_rate = float(stats["agreement_rate"]) if stats["agreement_rate"] is not None else 0.0
        outcome_alignment_rate = (
            float(stats["outcome_alignment_rate"]) if stats["outcome_alignment_rate"] is not None else None
        )
        sample_size = stats["sample_size"] or 0

        favorable = agreement_rate >= config["shadow_min_agreement_rate"] and (
            outcome_alignment_rate is None
            or outcome_alignment_rate >= config["shadow_min_outcome_alignment_rate"]
        )

        report_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO public.shadow_comparisons
                (id, candidate_version_id, champion_version_id, burn_in_start, burn_in_end,
                 agreement_rate, outcome_alignment_rate, sample_size)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            report_id,
            model_version_id,
            champion["id"] if champion else None,
            burn_in_start,
            burn_in_end,
            round(agreement_rate, 4),
            round(outcome_alignment_rate, 4) if outcome_alignment_rate is not None else None,
            sample_size,
        )

        if favorable:
            first_step = config["rollout_step_pcts"][0]
            await conn.execute(
                """
                UPDATE public.model_versions
                SET promotion_status = 'partial_rollout', rollout_pct = $2, rollout_step_started_at = now()
                WHERE id = $1
                """,
                model_version_id, first_step,
            )
        else:
            await conn.execute(
                """
                UPDATE public.model_versions
                SET promotion_status = 'retired', retired_at = now()
                WHERE id = $1
                """,
                model_version_id,
            )

    if not favorable:
        await ai_client.discard_candidate(candidate["model_type"])

    logger.info(json.dumps({
        "event": "shadow_comparison_report",
        "model_version_id": str(model_version_id),
        "agreement_rate": agreement_rate,
        "outcome_alignment_rate": outcome_alignment_rate,
        "sample_size": sample_size,
        "favorable": favorable,
    }))

    return {
        "model_version_id": model_version_id,
        "agreement_rate": agreement_rate,
        "outcome_alignment_rate": outcome_alignment_rate,
        "sample_size": sample_size,
        "favorable": favorable,
    }


# ── T033: rollout progression / rollback / champion promotion ────────────────

async def check_rollout_progression() -> None:
    """contracts/model-lifecycle.md step 3: for every partial_rollout version,
    compare the trailing search-level acceptance rate of searches served by
    the candidate vs. the champion since this version's current rollout step
    began. Rolls back on underperformance by rollback_margin (FR-012);
    otherwise advances rollout_step_pcts after rollout_step_hold_hours,
    promoting to champion at the final step. No dedicated config field names
    the acceptance-rate trailing window, so this reuses rollout_step_hold_hours
    (the same cadence already governing step-advancement) rather than adding
    another config knob for an overlapping concern."""
    config = get_continuous_learning_config()
    pool = get_pool()

    to_promote: list[uuid.UUID] = []

    async with pool.acquire() as conn:
        rollout_versions = await conn.fetch(
            """
            SELECT id, model_type, storage_version, rollout_pct, rollout_step_started_at
            FROM public.model_versions
            WHERE promotion_status = 'partial_rollout'
            """
        )

        for row in rollout_versions:
            model_version_id = row["id"]
            window_start = row["rollout_step_started_at"] or datetime.now(timezone.utc)

            perf_rows = await conn.fetch(
                """
                WITH scoped AS (
                    SELECT DISTINCT me.search_id, me.served_variant
                    FROM public.match_events me
                    WHERE me.shadow_model_version = $1 AND me.created_at >= $2
                ),
                outcomes AS (
                    SELECT DISTINCT me.search_id
                    FROM public.match_events me
                    JOIN public.match_outcomes mo ON mo.match_event_id = me.id
                    WHERE mo.transition_type = 'accepted'
                      AND me.shadow_model_version = $1 AND me.created_at >= $2
                )
                SELECT
                    served_variant,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE search_id IN (SELECT search_id FROM outcomes)) AS accepted
                FROM scoped
                GROUP BY served_variant
                """,
                row["storage_version"], window_start,
            )
            perf = {r["served_variant"]: (r["accepted"], r["total"]) for r in perf_rows}
            cand_accepted, cand_total = perf.get("candidate", (0, 0))
            champ_accepted, champ_total = perf.get("champion", (0, 0))

            if cand_total > 0 and champ_total > 0:
                candidate_rate = cand_accepted / cand_total
                champion_rate = champ_accepted / champ_total
                if champion_rate - candidate_rate >= config["rollback_margin"]:
                    await conn.execute(
                        """
                        UPDATE public.model_versions
                        SET promotion_status = 'retired', rollout_pct = 0, retired_at = now()
                        WHERE id = $1
                        """,
                        model_version_id,
                    )
                    logger.info(json.dumps({
                        "event": "rollout_auto_rollback",
                        "model_version_id": str(model_version_id),
                        "candidate_rate": candidate_rate,
                        "champion_rate": champion_rate,
                    }))
                    continue

            hold_elapsed_hours = (datetime.now(timezone.utc) - window_start).total_seconds() / 3600
            if hold_elapsed_hours < config["rollout_step_hold_hours"]:
                continue

            current_pct = float(row["rollout_pct"])
            remaining_steps = [p for p in config["rollout_step_pcts"] if p > current_pct]
            if not remaining_steps:
                to_promote.append(model_version_id)
            else:
                await conn.execute(
                    """
                    UPDATE public.model_versions
                    SET rollout_pct = $2, rollout_step_started_at = now()
                    WHERE id = $1
                    """,
                    model_version_id, remaining_steps[0],
                )

    for model_version_id in to_promote:
        await advance_to_champion(model_version_id)


async def advance_to_champion(model_version_id: uuid.UUID) -> None:
    """contracts/model-lifecycle.md: retires the current champion (if any)
    for this model_type and promotes model_version_id in its place, then
    calls POST /models/promote so services/ai starts serving it as latest."""
    pool = get_pool()
    async with pool.acquire() as conn:
        version = await conn.fetchrow(
            "SELECT model_type, storage_version FROM public.model_versions WHERE id = $1",
            model_version_id,
        )
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE public.model_versions
                SET promotion_status = 'retired', retired_at = now()
                WHERE model_type = $1 AND promotion_status = 'champion'
                """,
                version["model_type"],
            )
            await conn.execute(
                """
                UPDATE public.model_versions
                SET promotion_status = 'champion', rollout_pct = 100, promoted_at = now()
                WHERE id = $1
                """,
                model_version_id,
            )

    await ai_client.promote_model(version["model_type"], version["storage_version"])
    logger.info(json.dumps({
        "event": "model_promoted_to_champion",
        "model_version_id": str(model_version_id),
        "model_type": version["model_type"],
        "storage_version": version["storage_version"],
    }))
