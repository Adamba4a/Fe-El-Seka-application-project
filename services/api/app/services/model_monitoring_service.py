from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.database import get_pool
from app.services import model_lifecycle_service
from app.services.continuous_learning_config_service import get_continuous_learning_config
from app.utils.zone_lookup import nearest_zone

logger = logging.getLogger(__name__)

_MODEL_TYPES = ("match_score", "ride_ranker")
_METRIC_TYPES = ("prediction_distribution", "acceptance_rate", "completion_rate")

# match_events.model_version always holds the champion's storage_version
# (match_logging_service.py); shadow_model_version + served_variant='candidate'
# identifies decisions actually served by an active partial_rollout candidate.
# Mirrors the WHERE-clause convention already used by
# model_lifecycle_service.check_rollout_progression().
_METRIC_QUERY = """
    SELECT
        me.predicted_score,
        ST_Y(ss.origin_point) AS origin_lat,
        ST_X(ss.origin_point) AS origin_lng,
        BOOL_OR(mo.transition_type = 'accepted') AS accepted,
        BOOL_OR(mo.transition_type = 'completed') AS completed
    FROM public.match_events me
    JOIN public.search_sessions ss ON ss.id = me.search_id
    LEFT JOIN public.match_outcomes mo ON mo.match_event_id = me.id
    WHERE (
        ($4 = 'champion' AND me.model_version = $1)
        OR ($4 = 'candidate' AND me.shadow_model_version = $1 AND me.served_variant = 'candidate')
    )
    AND me.created_at >= $2 AND me.created_at < $3
    GROUP BY me.search_id, me.predicted_score, ss.origin_point
"""


# ── T037: per-zone aggregation, baseline comparison, alert-raising ──────────


def _aggregate_by_zone(rows: list[dict]) -> dict[str, dict[str, Any]]:
    """Pure grouping over raw per-search rows (already de-duplicated to one
    row per search_id by _METRIC_QUERY's GROUP BY) into per-zone metric
    values, per data-model.md's Monitoring Metric entity (FR-013)."""
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["origin_lat"] is None or row["origin_lng"] is None:
            continue
        zone, _ = nearest_zone(row["origin_lat"], row["origin_lng"])
        bucket = buckets.setdefault(zone, {
            "sample_size": 0, "score_sum": 0.0, "score_count": 0,
            "accepted": 0, "completed": 0,
        })
        bucket["sample_size"] += 1
        if row["predicted_score"] is not None:
            bucket["score_sum"] += float(row["predicted_score"])
            bucket["score_count"] += 1
        if row["accepted"]:
            bucket["accepted"] += 1
        if row["completed"]:
            bucket["completed"] += 1

    result: dict[str, dict[str, Any]] = {}
    for zone, bucket in buckets.items():
        total = bucket["sample_size"]
        result[zone] = {
            "sample_size": total,
            "prediction_distribution": (
                bucket["score_sum"] / bucket["score_count"] if bucket["score_count"] else None
            ),
            "acceptance_rate": bucket["accepted"] / total,
            "completion_rate": bucket["completed"] / total,
        }
    return result


def _alert_raised(value: float | None, baseline: float | None, margin: float) -> bool:
    """FR-014: an alert fires only once a real baseline exists to compare
    against — the first-ever measured window for a zone/metric_type has
    nothing to degrade relative to."""
    if value is None or baseline is None:
        return False
    # Round before comparing (mirrors model_lifecycle_service._decide_promotion)
    # so margin-boundary values aren't flipped by IEEE754 subtraction artifacts
    # (e.g. 0.6 - 0.5 != 0.1 exactly in binary floating point).
    return round(abs(value - baseline), 4) >= margin


async def _baseline_for(conn, model_version_id: uuid.UUID, zone: str, metric_type: str) -> float | None:
    """data-model.md: baseline = trailing average of prior windows for the
    same model_version_id/zone/metric_type."""
    row = await conn.fetchrow(
        """
        SELECT AVG(value) AS baseline
        FROM public.model_monitoring_metrics
        WHERE model_version_id = $1 AND zone = $2 AND metric_type = $3
        """,
        model_version_id, zone, metric_type,
    )
    if row is None or row["baseline"] is None:
        return None
    return float(row["baseline"])


async def _run_aggregation_for_version(
    conn, model_version_id: uuid.UUID, storage_version: str, variant: str,
    window_start: datetime, window_end: datetime, alert_baseline_margin: float,
) -> None:
    raw_rows = await conn.fetch(_METRIC_QUERY, storage_version, window_start, window_end, variant)
    zone_metrics = _aggregate_by_zone(raw_rows)

    for zone, metrics in zone_metrics.items():
        for metric_type in _METRIC_TYPES:
            value = metrics[metric_type]
            if value is None:
                continue
            baseline = await _baseline_for(conn, model_version_id, zone, metric_type)
            alert = _alert_raised(value, baseline, alert_baseline_margin)
            await conn.execute(
                """
                INSERT INTO public.model_monitoring_metrics
                    (id, model_version_id, zone, metric_type, time_window_start,
                     time_window_end, value, baseline, alert_raised)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                uuid.uuid4(), model_version_id, zone, metric_type,
                window_start, window_end, round(value, 4),
                round(baseline, 4) if baseline is not None else None, alert,
            )
            if alert:
                logger.info(json.dumps({
                    "event": "model_monitoring_alert",
                    "phase": "success",
                    "model_version_id": str(model_version_id),
                    "zone": zone,
                    "metric_type": metric_type,
                    "value": value,
                    "baseline": baseline,
                }))


async def run_hourly_aggregation(model_type: str) -> None:
    """T037 (FR-013, FR-014): aggregates the trailing monitoring_interval_hours
    window for the current champion, and for any active partial_rollout
    candidate (data-model.md: metrics are measured for "the champion (or
    partial-rollout candidate)"), per zone and metric_type."""
    config = get_continuous_learning_config()
    pool = get_pool()
    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(hours=config["monitoring_interval_hours"])

    async with pool.acquire() as conn:
        champion = await conn.fetchrow(
            """
            SELECT id, storage_version FROM public.model_versions
            WHERE model_type = $1 AND promotion_status = 'champion'
            """,
            model_type,
        )
        rollout = await conn.fetchrow(
            """
            SELECT id, storage_version FROM public.model_versions
            WHERE model_type = $1 AND promotion_status = 'partial_rollout'
            """,
            model_type,
        )

        for row, variant in ((champion, "champion"), (rollout, "candidate")):
            if row is None:
                continue
            await _run_aggregation_for_version(
                conn, row["id"], row["storage_version"], variant,
                window_start, window_end, config["alert_baseline_margin"],
            )

    logger.info(json.dumps({
        "event": "model_monitoring_aggregation_tick",
        "phase": "success",
        "model_type": model_type,
    }))


# ── T038: spot-audit sampling ─────────────────────────────────────────────────


def _spot_audit_due(
    anchor_at: datetime, last_sampled_at: datetime | None,
    frequency_hours: float, early_window_hours: float, now: datetime,
) -> bool:
    """FR-015: cadence halves for early_window_hours after promotion/rollout
    start (anchor_at), so early drift is caught faster."""
    if last_sampled_at is None:
        return True
    since_anchor_hours = (now - anchor_at).total_seconds() / 3600
    effective_frequency = frequency_hours / 2 if since_anchor_hours < early_window_hours else frequency_hours
    elapsed_hours = (now - last_sampled_at).total_seconds() / 3600
    return elapsed_hours >= effective_frequency


async def _last_spot_audit_at(conn, model_version_id: uuid.UUID) -> datetime | None:
    row = await conn.fetchrow(
        "SELECT MAX(sampled_at) AS last_sampled_at FROM public.model_spot_audits WHERE model_version_id = $1",
        model_version_id,
    )
    return row["last_sampled_at"] if row else None


async def _sample_spot_audits_for_version(
    conn, model_version_id: uuid.UUID, storage_version: str, variant: str, sample_size: int,
) -> int:
    rows = await conn.fetch(
        """
        SELECT id FROM public.match_events
        WHERE (
            ($3 = 'champion' AND model_version = $1)
            OR ($3 = 'candidate' AND shadow_model_version = $1 AND served_variant = 'candidate')
        )
        ORDER BY created_at DESC
        LIMIT $2
        """,
        storage_version, sample_size, variant,
    )
    for row in rows:
        await conn.execute(
            """
            INSERT INTO public.model_spot_audits (id, model_version_id, match_event_id)
            VALUES ($1, $2, $3)
            """,
            uuid.uuid4(), model_version_id, row["id"],
        )
    return len(rows)


async def record_spot_audit_samples() -> None:
    """T038 (FR-015): champion and any active partial_rollout candidate, per
    model_type, each on their own due-ness cadence anchored to promoted_at /
    shadow_started_at respectively."""
    config = get_continuous_learning_config()
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        for model_type in _MODEL_TYPES:
            champion = await conn.fetchrow(
                """
                SELECT id, storage_version, promoted_at FROM public.model_versions
                WHERE model_type = $1 AND promotion_status = 'champion'
                """,
                model_type,
            )
            rollout = await conn.fetchrow(
                """
                SELECT id, storage_version, shadow_started_at FROM public.model_versions
                WHERE model_type = $1 AND promotion_status = 'partial_rollout'
                """,
                model_type,
            )

            for row, variant, anchor_field in (
                (champion, "champion", "promoted_at"),
                (rollout, "candidate", "shadow_started_at"),
            ):
                if row is None:
                    continue
                anchor_at = row[anchor_field] or now
                last_sampled_at = await _last_spot_audit_at(conn, row["id"])
                if not _spot_audit_due(
                    anchor_at, last_sampled_at,
                    config["spot_audit_frequency_hours"], config["spot_audit_early_window_hours"], now,
                ):
                    continue
                sampled = await _sample_spot_audits_for_version(
                    conn, row["id"], row["storage_version"], variant, config["spot_audit_sample_size"],
                )
                logger.info(json.dumps({
                    "event": "spot_audit_sampled",
                    "phase": "success",
                    "model_type": model_type,
                    "model_version_id": str(row["id"]),
                    "variant": variant,
                    "sample_count": sampled,
                }))


# ── T039: human review of sampled decisions ──────────────────────────────────


async def apply_spot_audit_finding(
    spot_audit_id: uuid.UUID, reviewer_admin_id: uuid.UUID, finding: str, trigger_rollback: bool,
) -> None:
    """T039: human review of a sampled decision (data-model.md Spot Audit
    Record) — trigger_rollback=True performs the exact same rollback action
    as check_rollout_progression()'s automatic path (spec Edge Case), reusing
    model_lifecycle_service.rollback_version() on the same connection/
    transaction so the audit update and the rollback commit atomically together."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            audit_row = await conn.fetchrow(
                "SELECT model_version_id FROM public.model_spot_audits WHERE id = $1",
                spot_audit_id,
            )
            await conn.execute(
                """
                UPDATE public.model_spot_audits
                SET reviewer_admin_id = $1, finding = $2, reviewed_at = now(), triggered_rollback = $3
                WHERE id = $4
                """,
                reviewer_admin_id, finding, trigger_rollback, spot_audit_id,
            )
            if trigger_rollback and audit_row is not None:
                await model_lifecycle_service.rollback_version(audit_row["model_version_id"], conn=conn)

    logger.info(json.dumps({
        "event": "spot_audit_finding_applied",
        "phase": "success",
        "spot_audit_id": str(spot_audit_id),
        "trigger_rollback": trigger_rollback,
    }))


# ── T040: background loop ────────────────────────────────────────────────────


async def model_monitoring_loop() -> None:
    """T040: hourly cadence per NFR-004 — aggregation + spot-audit sampling
    for every model_type, same in-process background-task pattern as the
    other loops in main.py."""
    while True:
        for model_type in _MODEL_TYPES:
            try:
                await run_hourly_aggregation(model_type)
            except Exception as exc:
                logger.error("model_monitoring_loop aggregation error for %s: %s", model_type, exc)
        try:
            await record_spot_audit_samples()
        except Exception as exc:
            logger.error("model_monitoring_loop spot-audit error: %s", exc)
        await asyncio.sleep(3600)
