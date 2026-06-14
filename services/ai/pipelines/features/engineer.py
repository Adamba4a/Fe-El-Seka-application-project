"""
Feature engineering pipeline.
Imports build_feature_vector from the shared app/services/feature_engineering.py
to guarantee training/serving consistency (FR-011).
"""
import logging

import numpy as np
import pandas as pd

from app.services.feature_engineering import FEATURE_NAMES, build_feature_vector

logger = logging.getLogger(__name__)


def engineer_features(rides_df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform raw ride records into the standardized 14-dim feature matrix.
    Each row represents a (passenger, driver) pair.
    Synthetic overlap_ratio and detour values are estimated from zone distance.
    """
    records = []
    skipped = 0

    for _, row in rides_df.iterrows():
        try:
            # Estimate overlap features from zone geometry for synthetic data
            overlap_ratio = _estimate_overlap(
                row["origin_zone"], row["destination_zone"],
                row["driver_origin_zone"], row["driver_dest_zone"],
            )
            pickup_detour_km = _estimate_detour(row["origin_zone"], row["driver_origin_zone"])
            dropoff_distance_km = _estimate_detour(row["destination_zone"], row["driver_dest_zone"])

            from datetime import timezone
            departure_at = row["departure_at"]
            if departure_at.tzinfo is None:
                from datetime import timezone
                departure_at = departure_at.replace(tzinfo=timezone.utc)

            vec = build_feature_vector(
                passenger_origin_zone=row["origin_zone"],
                passenger_dest_zone=row["destination_zone"],
                driver_origin_zone=row["driver_origin_zone"],
                driver_dest_zone=row["driver_dest_zone"],
                overlap_ratio=overlap_ratio,
                pickup_detour_km=pickup_detour_km,
                dropoff_distance_km=dropoff_distance_km,
                departure_at_utc=departure_at,
            )
            records.append((*vec, int(row["match_label"])))
        except (ValueError, KeyError) as exc:
            logger.warning("Skipping row (id=%s): %s", row.get("id", "?"), exc)
            skipped += 1

    if skipped > 0:
        logger.warning("Skipped %d rows due to errors", skipped)

    cols = FEATURE_NAMES + ["match_label"]
    df = pd.DataFrame(records, columns=cols)
    return df


def _estimate_overlap(p_origin: str, p_dest: str, d_origin: str, d_dest: str) -> float:
    """
    Synthetic overlap estimate: zones that share origin/dest cluster get higher overlap.
    Used only during training — Phase 5 (route engine) provides real overlap values.
    """
    import math

    from pipelines.dataset.zones import zone_by_name

    DEG_TO_KM = 111.0

    def dist(z1: str, z2: str) -> float:
        a, b = zone_by_name[z1], zone_by_name[z2]
        dlat = (a.centroid_lat - b.centroid_lat) * DEG_TO_KM
        dlng = (
            (a.centroid_lng - b.centroid_lng)
            * DEG_TO_KM
            * math.cos(math.radians(a.centroid_lat))
        )
        return math.sqrt(dlat**2 + dlng**2)

    dest_dist = dist(p_dest, d_dest)
    origin_dist = dist(p_origin, d_origin)
    overlap = max(0.0, 1.0 - (dest_dist + origin_dist) / 40.0)
    return float(np.clip(overlap, 0.0, 1.0))


def _estimate_detour(zone1: str, zone2: str) -> float:
    import math

    from pipelines.dataset.zones import zone_by_name

    DEG_TO_KM = 111.0
    a, b = zone_by_name[zone1], zone_by_name[zone2]
    dlat = (a.centroid_lat - b.centroid_lat) * DEG_TO_KM
    dlng = (a.centroid_lng - b.centroid_lng) * DEG_TO_KM * math.cos(math.radians(a.centroid_lat))
    return math.sqrt(dlat**2 + dlng**2)
