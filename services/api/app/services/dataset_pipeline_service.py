from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from app.core.database import get_pool
from app.services import storage_service

logger = logging.getLogger(__name__)

_BUCKET = "training-datasets"

# PDPL 151/2020 retention window — 013's spec explicitly deferred defining this
# to this feature (FR-004). match_events older than this are excluded.
_DATA_RETENTION_DAYS = 365

# "Highly rated" threshold for the completed_highly_rated tier — the spec
# describes the labeling hierarchy qualitatively only.
_HIGH_RATING_THRESHOLD = 4

# signal_strength_tier -> (soft label match_prob, hard label match_label).
# Mirrors the synthetic pipeline's match_prob/match_label column convention
# (train_match_score.py fits on the soft label; the hard label is used only
# for the AUC/stratify gate) so train_from_real_data.py can reuse it as-is.
_TIER_LABELS: dict[str, tuple[float, int]] = {
    "completed_highly_rated": (0.95, 1),
    "completed_unrated": (0.75, 1),
    "booked_not_completed": (0.50, 1),
    "shown_not_booked": (0.10, 0),
}

_EXCLUDED_VERIFICATION_STATUSES = ("suspended", "rejected")

# Joins match_events -> search_sessions/rides (for raw coordinate reconstruction,
# since match_events.feature_vector does not itself carry the passenger/driver
# origin-destination points) and aggregates match_outcomes/ratings per event.
# Filtering (retention window, fraud/suspension exclusion) and labeling are done
# in Python below rather than in this query, so that logic is unit-testable
# without a live Postgres instance — at the dataset volumes this pipeline deals
# with (hundreds to low thousands of rows per run) this is not a performance
# concern.
_JOIN_QUERY = """
    SELECT
        me.id                       AS match_event_id,
        me.search_id,
        me.passenger_id,
        r.driver_id,
        me.created_at               AS match_event_created_at,
        me.feature_vector,
        ST_Y(ss.origin_point)                       AS passenger_origin_lat,
        ST_X(ss.origin_point)                       AS passenger_origin_lng,
        ST_Y(ss.destination_point)                  AS passenger_dest_lat,
        ST_X(ss.destination_point)                  AS passenger_dest_lng,
        ss.desired_departure_at,
        ST_Y(r.origin_coordinates::geometry)        AS driver_origin_lat,
        ST_X(r.origin_coordinates::geometry)        AS driver_origin_lng,
        ST_Y(r.destination_coordinates::geometry)   AS driver_dest_lat,
        ST_X(r.destination_coordinates::geometry)   AS driver_dest_lng,
        p_pass.verification_status  AS passenger_verification_status,
        p_drv.verification_status   AS driver_verification_status,
        EXISTS (
            SELECT 1 FROM public.reports rp
            WHERE rp.reported_user_id = me.passenger_id AND rp.resolution_action = 'suspend'
        ) AS passenger_suspended_by_report,
        EXISTS (
            SELECT 1 FROM public.reports rp
            WHERE rp.reported_user_id = r.driver_id AND rp.resolution_action = 'suspend'
        ) AS driver_suspended_by_report,
        COALESCE(
            array_agg(DISTINCT mo.transition_type::text) FILTER (WHERE mo.transition_type IS NOT NULL),
            ARRAY[]::text[]
        ) AS transitions,
        MAX(rt.stars) AS rating_stars
    FROM public.match_events me
    JOIN public.search_sessions ss ON ss.id = me.search_id
    JOIN public.rides r ON r.id = me.candidate_ride_id
    JOIN public.profiles p_pass ON p_pass.id = me.passenger_id
    JOIN public.profiles p_drv ON p_drv.id = r.driver_id
    LEFT JOIN public.match_outcomes mo ON mo.match_event_id = me.id
    LEFT JOIN public.bookings bk ON bk.ride_id = me.candidate_ride_id AND bk.passenger_id = me.passenger_id
    LEFT JOIN public.ratings rt ON rt.booking_id = bk.id AND rt.rater_role = 'passenger'
    GROUP BY
        me.id, ss.id, r.id, p_pass.verification_status, p_drv.verification_status
"""

# Allowlist of columns persisted to the Parquet dataset (FR-004 anonymization) —
# built explicitly rather than passing the raw joined row through, so a future
# column added to _JOIN_QUERY doesn't silently leak into the training dataset.
# passenger_id/driver_id are retained only as opaque UUIDs (contracts/dataset-
# pipeline.md step 5) — no names, phone numbers, or free-text fields.
_PARQUET_COLUMNS = (
    "match_event_id",
    # Opaque grouping key (not PII) — lets train_from_real_data.py's ranking-
    # quality metric (FR-007) know which candidate rows competed in the same
    # search, so it can tell whether the top-ranked one was the actual choice.
    "search_id",
    "passenger_id",
    "driver_id",
    "passenger_origin_lat",
    "passenger_origin_lng",
    "passenger_dest_lat",
    "passenger_dest_lng",
    "driver_origin_lat",
    "driver_origin_lng",
    "driver_dest_lat",
    "driver_dest_lng",
    "departure_at_utc",
    "overlap_ratio",
    "pickup_detour_km",
    "dropoff_distance_km",
    "signal_strength_tier",
    "match_prob",
    "match_label",
)

# Explicit schema (rather than relying on pyarrow's type inference) so an
# empty dataset — a valid, if degenerate, snapshot — still writes a readable
# Parquet file instead of erroring on schema inference from zero rows.
_PARQUET_SCHEMA = pa.schema([
    ("match_event_id", pa.string()),
    ("search_id", pa.string()),
    ("passenger_id", pa.string()),
    ("driver_id", pa.string()),
    ("passenger_origin_lat", pa.float64()),
    ("passenger_origin_lng", pa.float64()),
    ("passenger_dest_lat", pa.float64()),
    ("passenger_dest_lng", pa.float64()),
    ("driver_origin_lat", pa.float64()),
    ("driver_origin_lng", pa.float64()),
    ("driver_dest_lat", pa.float64()),
    ("driver_dest_lng", pa.float64()),
    ("departure_at_utc", pa.string()),
    ("overlap_ratio", pa.float64()),
    ("pickup_detour_km", pa.float64()),
    ("dropoff_distance_km", pa.float64()),
    ("signal_strength_tier", pa.string()),
    ("match_prob", pa.float64()),
    ("match_label", pa.int64()),
])


def _is_excluded(row: dict[str, Any]) -> bool:
    """FR-003: exclude accounts that are suspended/rejected, or have a report
    resolved with resolution_action='suspend', on either side of the match."""
    if row["passenger_verification_status"] in _EXCLUDED_VERIFICATION_STATUSES:
        return True
    if row["driver_verification_status"] in _EXCLUDED_VERIFICATION_STATUSES:
        return True
    if row["passenger_suspended_by_report"] or row["driver_suspended_by_report"]:
        return True
    return False


def _within_retention_window(row: dict[str, Any], now: datetime) -> bool:
    """FR-004: excludes rows older than the PDPL retention window."""
    created_at = row["match_event_created_at"]
    return created_at >= now - timedelta(days=_DATA_RETENTION_DAYS)


def _signal_strength_tier(transitions: list[str], rating_stars: int | None) -> str:
    """FR-002 labeling hierarchy. 'cancelled' is folded into booked_not_completed
    — a cancellation is never treated as an automatic negative signal, since the
    passenger still expressed booking intent."""
    if "completed" in transitions:
        if rating_stars is not None and rating_stars >= _HIGH_RATING_THRESHOLD:
            return "completed_highly_rated"
        return "completed_unrated"
    if "accepted" in transitions or "cancelled" in transitions:
        return "booked_not_completed"
    return "shown_not_booked"


def _process_rows(
    raw_rows: list[dict[str, Any]], now: datetime
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    """Applies FR-003/FR-004 exclusions and FR-002 labeling to raw joined rows.
    Returns (labeled rows ready for anonymization, excluded_count, exclusion_summary)."""
    included: list[dict[str, Any]] = []
    exclusion_summary = {"fraud_or_suspension": 0, "retention_window": 0}

    for row in raw_rows:
        if _is_excluded(row):
            exclusion_summary["fraud_or_suspension"] += 1
            continue
        if not _within_retention_window(row, now):
            exclusion_summary["retention_window"] += 1
            continue

        feature_vector = row["feature_vector"] or {}
        tier = _signal_strength_tier(list(row["transitions"] or []), row["rating_stars"])
        match_prob, match_label = _TIER_LABELS[tier]

        included.append(
            {
                "match_event_id": str(row["match_event_id"]),
                "search_id": str(row["search_id"]),
                "passenger_id": str(row["passenger_id"]),
                "driver_id": str(row["driver_id"]),
                "passenger_origin_lat": row["passenger_origin_lat"],
                "passenger_origin_lng": row["passenger_origin_lng"],
                "passenger_dest_lat": row["passenger_dest_lat"],
                "passenger_dest_lng": row["passenger_dest_lng"],
                "driver_origin_lat": row["driver_origin_lat"],
                "driver_origin_lng": row["driver_origin_lng"],
                "driver_dest_lat": row["driver_dest_lat"],
                "driver_dest_lng": row["driver_dest_lng"],
                "departure_at_utc": row["desired_departure_at"].isoformat(),
                # Unit conversion: feature_vector is logged by match_logging_service.py
                # in percent/meters; feature_engineering.build_feature_vector_from_coords()
                # expects a ratio/km.
                "overlap_ratio": feature_vector.get("overlap_pct", 0) / 100.0,
                "pickup_detour_km": feature_vector.get("pickup_walk_m", 0) / 1000.0,
                "dropoff_distance_km": feature_vector.get("dropoff_walk_m", 0) / 1000.0,
                "signal_strength_tier": tier,
                "match_prob": match_prob,
                "match_label": match_label,
                "_match_event_created_at": row["match_event_created_at"],
            }
        )

    excluded_count = exclusion_summary["fraud_or_suspension"] + exclusion_summary["retention_window"]
    return included, excluded_count, exclusion_summary


def _anonymize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """FR-004 anonymization step: builds each output row from the explicit
    allowlist only, dropping any other key (e.g. the internal
    _match_event_created_at bookkeeping field)."""
    return [{col: row[col] for col in _PARQUET_COLUMNS} for row in rows]


async def count_eligible_rows() -> int:
    """Cheap pre-check for retraining_scheduler_service.py: runs the same
    join + exclusion filtering as generate_dataset_snapshot() but skips the
    Parquet write, Storage upload, and dataset_snapshots insert. Without this,
    an hourly scheduler that only discovers row_count < min_dataset_size
    *after* generating a full snapshot would spam Storage with a new upload
    and DB row every hour for as long as the platform is below threshold
    (which can be for weeks after launch)."""
    now = datetime.now(timezone.utc)
    pool = get_pool()
    async with pool.acquire() as conn:
        raw_records = await conn.fetch(_JOIN_QUERY)
    raw_rows = [dict(r) for r in raw_records]
    included, _excluded_count, _exclusion_summary = _process_rows(raw_rows, now)
    return len(included)


async def generate_dataset_snapshot(model_type: str) -> dict[str, Any]:
    """FR-001/002/003/004: joins real match events and outcomes into a labeled,
    anonymized Parquet dataset snapshot, uploads it to Storage, and records a
    dataset_snapshots row. The DB row is only inserted after the upload
    succeeds, so a mid-run failure leaves no partial row."""
    snapshot_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    logger.info(json.dumps({
        "event": "dataset_pipeline_run",
        "phase": "start",
        "model_type": model_type,
        "snapshot_id": str(snapshot_id),
    }))

    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            raw_records = await conn.fetch(_JOIN_QUERY)
        raw_rows = [dict(r) for r in raw_records]

        included, excluded_count, exclusion_summary = _process_rows(raw_rows, now)

        if included:
            date_range_start = min(r["_match_event_created_at"] for r in included)
            date_range_end = max(r["_match_event_created_at"] for r in included)
        else:
            date_range_start = now
            date_range_end = now

        final_rows = _anonymize(included)

        storage_path = f"{model_type}/{snapshot_id}/dataset.parquet"
        table = pa.Table.from_pylist(final_rows, schema=_PARQUET_SCHEMA)
        buf = pa.BufferOutputStream()
        pq.write_table(table, buf)
        parquet_bytes = buf.getvalue().to_pybytes()

        # storage_service.upload_file is a synchronous network call (supabase-py
        # has no async client) — running it inline on this coroutine would
        # freeze the whole API event loop (all passenger/driver requests) for
        # the duration of the upload, so it's pushed to a worker thread.
        await asyncio.to_thread(
            storage_service.upload_file, _BUCKET, storage_path, parquet_bytes, "application/octet-stream"
        )

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.dataset_snapshots
                    (id, model_type, storage_path, row_count, excluded_count,
                     date_range_start, date_range_end, exclusion_summary)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                snapshot_id,
                model_type,
                storage_path,
                len(final_rows),
                excluded_count,
                date_range_start,
                date_range_end,
                json.dumps(exclusion_summary),
            )

        logger.info(json.dumps({
            "event": "dataset_pipeline_run",
            "phase": "success",
            "model_type": model_type,
            "snapshot_id": str(snapshot_id),
            "row_count": len(final_rows),
            "excluded_count": excluded_count,
            "exclusion_summary": exclusion_summary,
        }))

        return {
            "snapshot_id": snapshot_id,
            "model_type": model_type,
            "storage_path": storage_path,
            "row_count": len(final_rows),
            "excluded_count": excluded_count,
            "date_range_start": date_range_start,
            "date_range_end": date_range_end,
            "exclusion_summary": exclusion_summary,
        }
    except Exception as exc:
        logger.error(json.dumps({
            "event": "dataset_pipeline_run",
            "phase": "failure",
            "model_type": model_type,
            "snapshot_id": str(snapshot_id),
            "error": str(exc),
        }))
        raise


async def get_labeled_row_count(model_type: str, snapshot_id: uuid.UUID | str) -> int:
    """Returns the row_count recorded for a given dataset snapshot, or 0 if no
    matching snapshot exists."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT row_count FROM public.dataset_snapshots WHERE model_type = $1 AND id = $2",
            model_type,
            snapshot_id if isinstance(snapshot_id, uuid.UUID) else uuid.UUID(str(snapshot_id)),
        )
    return row["row_count"] if row else 0
