"""
Feature engineering pipeline.
Imports build_feature_vector from the shared app/services/feature_engineering.py
to guarantee training/serving consistency (FR-011).
"""
import logging
from datetime import timezone

import pandas as pd

from app.services.feature_engineering import FEATURE_NAMES, build_feature_vector

logger = logging.getLogger(__name__)


def engineer_features(rides_df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform raw ride records into the standardized 14-dim feature matrix.
    Each row represents a (passenger, driver) pair.

    overlap_ratio / pickup_detour_km / dropoff_distance_km are read directly from
    the ride record (sampled realistically by generate_rides.py) rather than
    re-derived from zone identity — see generate_rides.py for the 2026-07-04
    realism fix that replaced the old exact zone-distance estimate.
    """
    records = []
    skipped = 0

    for _, row in rides_df.iterrows():
        try:
            departure_at = row["departure_at"]
            if departure_at.tzinfo is None:
                departure_at = departure_at.replace(tzinfo=timezone.utc)

            vec = build_feature_vector(
                passenger_origin_zone=row["origin_zone"],
                passenger_dest_zone=row["destination_zone"],
                driver_origin_zone=row["driver_origin_zone"],
                driver_dest_zone=row["driver_dest_zone"],
                overlap_ratio=row["overlap_ratio"],
                pickup_detour_km=row["pickup_detour_km"],
                dropoff_distance_km=row["dropoff_distance_km"],
                departure_at_utc=departure_at,
            )
            records.append((*vec, int(row["match_label"]), float(row["match_prob"])))
        except (ValueError, KeyError) as exc:
            logger.warning("Skipping row (id=%s): %s", row.get("id", "?"), exc)
            skipped += 1

    if skipped > 0:
        logger.warning("Skipped %d rows due to errors", skipped)

    cols = FEATURE_NAMES + ["match_label", "match_prob"]
    df = pd.DataFrame(records, columns=cols)
    return df
