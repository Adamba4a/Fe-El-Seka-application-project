"""
Single source of truth for feature vector construction.
Imported by both the training pipeline and the serving layer.
Feature order is FIXED — any change requires retraining all models.
"""
import logging
import math
from datetime import datetime

import numpy as np

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "passenger_origin_lat",
    "passenger_origin_lng",
    "passenger_dest_lat",
    "passenger_dest_lng",
    "driver_origin_lat",
    "driver_origin_lng",
    "driver_dest_lat",
    "driver_dest_lng",
    "overlap_ratio",
    "pickup_detour_km",
    "dropoff_distance_km",
    "dest_zone_distance_km",
    "departure_hour_sin",
    "departure_hour_cos",
]

_DEG_TO_KM = 111.0  # approximate km per degree latitude

# Monotonic direction per FEATURE_NAMES entry, shared by both training scripts
# (train_match_score.py, train_ranker.py): +1 = score must never decrease as
# the feature increases, -1 = score must never increase, 0 = unconstrained.
# Prevents the model from learning erratic behaviour in sparsely-populated
# corners of feature space, e.g. real-world inputs combining high overlap with
# a large pickup detour — a combination the synthetic "good corridor"
# distribution rarely produces (see research.md, 2026-07-04 calibration fix).
MATCH_QUALITY_MONOTONE_CONSTRAINTS = (
    0, 0, 0, 0,   # passenger_origin_lat/lng, passenger_dest_lat/lng
    0, 0, 0, 0,   # driver_origin_lat/lng, driver_dest_lat/lng
    1,            # overlap_ratio: more overlap must never lower the score
    -1,           # pickup_detour_km: more detour must never raise the score
    -1,           # dropoff_distance_km: more distance must never raise the score
    -1,           # dest_zone_distance_km: further-apart destinations must never raise the score
    0, 0,         # departure_hour_sin/cos
)


def _zone_centroid(zone_name: str) -> tuple[float, float]:
    # Training-only path (see build_feature_vector below) — imported lazily so the
    # serving container, which never calls it, doesn't need the pipelines package.
    from pipelines.dataset.zones import zone_by_name

    zone = zone_by_name.get(zone_name)
    if zone is None:
        raise ValueError(f"Unknown zone: '{zone_name}'. Known zones: {list(zone_by_name.keys())}")
    return zone.centroid_lat, zone.centroid_lng


def _euclidean_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat = (lat2 - lat1) * _DEG_TO_KM
    dlng = (lng2 - lng1) * _DEG_TO_KM * math.cos(math.radians((lat1 + lat2) / 2))
    return math.sqrt(dlat**2 + dlng**2)


def build_feature_vector(
    passenger_origin_zone: str,
    passenger_dest_zone: str,
    driver_origin_zone: str,
    driver_dest_zone: str,
    overlap_ratio: float,
    pickup_detour_km: float,
    dropoff_distance_km: float,
    departure_at_utc: datetime,
) -> np.ndarray:
    """
    Build a deterministic 14-element float64 feature vector from zone names.
    Used by the training pipeline. Identical inputs always produce identical outputs (FR-011).
    """
    p_o_lat, p_o_lng = _zone_centroid(passenger_origin_zone)
    p_d_lat, p_d_lng = _zone_centroid(passenger_dest_zone)
    d_o_lat, d_o_lng = _zone_centroid(driver_origin_zone)
    d_d_lat, d_d_lng = _zone_centroid(driver_dest_zone)

    return build_feature_vector_from_coords(
        p_o_lat, p_o_lng, p_d_lat, p_d_lng,
        d_o_lat, d_o_lng, d_d_lat, d_d_lng,
        overlap_ratio, pickup_detour_km, dropoff_distance_km, departure_at_utc,
    )


def build_feature_vector_from_coords(
    passenger_origin_lat: float,
    passenger_origin_lng: float,
    passenger_dest_lat: float,
    passenger_dest_lng: float,
    driver_origin_lat: float,
    driver_origin_lng: float,
    driver_dest_lat: float,
    driver_dest_lng: float,
    overlap_ratio: float,
    pickup_detour_km: float,
    dropoff_distance_km: float,
    departure_at_utc: datetime,
) -> np.ndarray:
    """
    Build a deterministic 14-element float64 feature vector from raw coordinates.
    Used by the serving layer. Identical inputs always produce identical outputs (FR-011).
    """
    clamped_overlap = float(np.clip(overlap_ratio, 0.0, 1.0))
    if overlap_ratio != clamped_overlap:
        logger.warning("overlap_ratio %s clamped to %s", overlap_ratio, clamped_overlap)

    dest_dist_km = _euclidean_km(
        passenger_dest_lat, passenger_dest_lng, driver_dest_lat, driver_dest_lng
    )

    hour = departure_at_utc.hour + departure_at_utc.minute / 60.0
    hour_sin = math.sin(2 * math.pi * hour / 24)
    hour_cos = math.cos(2 * math.pi * hour / 24)

    return np.array(
        [
            passenger_origin_lat, passenger_origin_lng,
            passenger_dest_lat, passenger_dest_lng,
            driver_origin_lat, driver_origin_lng,
            driver_dest_lat, driver_dest_lng,
            clamped_overlap,
            float(pickup_detour_km),
            float(dropoff_distance_km),
            dest_dist_km,
            hour_sin,
            hour_cos,
        ],
        dtype=np.float64,
    )
