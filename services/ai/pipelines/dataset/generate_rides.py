import logging
import math
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from pipelines.dataset.zones import ZONES, CairoZone, zone_by_name

logger = logging.getLogger(__name__)

_RNG_SEED = 42
_BASE_DATE = datetime(2026, 6, 13, tzinfo=timezone.utc)
_COORD_NOISE_STD = 0.008  # ~900m
_MIN_RECORDS_PER_ZONE = 1_000
_MATCH_DEST_THRESHOLD_KM = 5.0
_MATCH_TIME_WINDOW_MIN = 30
_DEG_TO_KM = 111.0
_POSITIVE_ATTEMPT_PROB = 0.35
_POSITIVE_TIME_JITTER_HOURS = 0.4  # 24 min, safely under the 30 min window


def _euclidean_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat = (lat2 - lat1) * _DEG_TO_KM
    dlng = (lng2 - lng1) * _DEG_TO_KM * math.cos(math.radians((lat1 + lat2) / 2))
    return math.sqrt(dlat**2 + dlng**2)


def _sample_departure_hour(rng: np.random.Generator) -> float:
    slot = rng.choice([0, 1, 2], p=[0.40, 0.40, 0.20])
    if slot == 0:  # morning peak
        return float(np.clip(rng.normal(8.0, 0.5), 6.0, 10.0))
    elif slot == 1:  # evening peak
        return float(np.clip(rng.normal(17.0, 0.75), 14.0, 20.0))
    else:  # off-peak uniform
        return float(rng.uniform(0.0, 24.0))


def _hour_to_datetime(hour: float) -> datetime:
    h = int(hour)
    m = int((hour - h) * 60)
    return _BASE_DATE.replace(hour=h % 24, minute=m, second=0, microsecond=0)


def _assign_match_label(
    p_dest: CairoZone,
    d_dest: CairoZone,
    p_origin: CairoZone,
    d_origin: CairoZone,
    p_hour: float,
    d_hour: float,
) -> int:
    dest_dist = _euclidean_km(p_dest.centroid_lat, p_dest.centroid_lng,
                               d_dest.centroid_lat, d_dest.centroid_lng)
    origin_dist = _euclidean_km(p_origin.centroid_lat, p_origin.centroid_lng,
                                 d_origin.centroid_lat, d_origin.centroid_lng)
    time_diff = abs(p_hour - d_hour) * 60  # minutes
    if (
        dest_dist <= _MATCH_DEST_THRESHOLD_KM
        and time_diff <= _MATCH_TIME_WINDOW_MIN
        and origin_dist <= _MATCH_DEST_THRESHOLD_KM
    ):
        return 1
    return 0


def generate_rides(n: int = 100_000) -> pd.DataFrame:
    rng = np.random.default_rng(_RNG_SEED)
    weights = np.array([z.weight for z in ZONES])
    zone_names = [z.name for z in ZONES]

    rows = []
    for _ in range(n):
        p_origin = ZONES[rng.choice(len(ZONES), p=weights)]
        p_dest = ZONES[rng.choice(len(ZONES), p=weights)]
        p_hour = _sample_departure_hour(rng)

        if rng.random() < _POSITIVE_ATTEMPT_PROB:
            # Construct a plausible carpool match: same origin/destination zone,
            # departure close in time — real matches are geographically scarce
            # but not vanishingly rare, per research.md Decision 2.
            d_origin = p_origin
            d_dest = p_dest
            jitter = rng.uniform(-_POSITIVE_TIME_JITTER_HOURS, _POSITIVE_TIME_JITTER_HOURS)
            d_hour = float(np.clip(p_hour + jitter, 0.0, 23.999))
        else:
            d_origin = ZONES[rng.choice(len(ZONES), p=weights)]
            d_dest = ZONES[rng.choice(len(ZONES), p=weights)]
            d_hour = _sample_departure_hour(rng)

        # Apply Gaussian noise to centroid for realistic coordinate variation
        p_o_lat = p_origin.centroid_lat + rng.normal(0, _COORD_NOISE_STD)
        p_o_lng = p_origin.centroid_lng + rng.normal(0, _COORD_NOISE_STD)
        p_d_lat = p_dest.centroid_lat + rng.normal(0, _COORD_NOISE_STD)
        p_d_lng = p_dest.centroid_lng + rng.normal(0, _COORD_NOISE_STD)

        est_dist = _euclidean_km(p_o_lat, p_o_lng, p_d_lat, p_d_lng)
        label = _assign_match_label(p_dest, d_dest, p_origin, d_origin, p_hour, d_hour)

        rows.append({
            "id": str(uuid.uuid4()),
            "origin_zone": p_origin.name,
            "destination_zone": p_dest.name,
            "origin_lat": p_o_lat,
            "origin_lng": p_o_lng,
            "destination_lat": p_d_lat,
            "destination_lng": p_d_lng,
            "departure_at": _hour_to_datetime(p_hour),
            "estimated_distance_km": est_dist,
            "driver_origin_zone": d_origin.name,
            "driver_dest_zone": d_dest.name,
            "driver_departure_hour": d_hour,
            "is_driver": False,
            "match_label": label,
        })

    df = pd.DataFrame(rows)

    # Enforce minimum records per zone
    origin_counts = df["origin_zone"].value_counts()
    for zone_name in zone_names:
        count = origin_counts.get(zone_name, 0)
        if count < _MIN_RECORDS_PER_ZONE:
            deficit = _MIN_RECORDS_PER_ZONE - count
            zone = zone_by_name[zone_name]
            topup_rows = []
            for _ in range(deficit):
                p_dest = ZONES[rng.choice(len(ZONES), p=weights)]
                p_hour = _sample_departure_hour(rng)
                if rng.random() < _POSITIVE_ATTEMPT_PROB:
                    d_origin = zone
                    d_dest = p_dest
                    jitter = rng.uniform(-_POSITIVE_TIME_JITTER_HOURS, _POSITIVE_TIME_JITTER_HOURS)
                    d_hour = float(np.clip(p_hour + jitter, 0.0, 23.999))
                else:
                    d_origin = ZONES[rng.choice(len(ZONES), p=weights)]
                    d_dest = ZONES[rng.choice(len(ZONES), p=weights)]
                    d_hour = _sample_departure_hour(rng)
                p_o_lat = zone.centroid_lat + rng.normal(0, _COORD_NOISE_STD)
                p_o_lng = zone.centroid_lng + rng.normal(0, _COORD_NOISE_STD)
                p_d_lat = p_dest.centroid_lat + rng.normal(0, _COORD_NOISE_STD)
                p_d_lng = p_dest.centroid_lng + rng.normal(0, _COORD_NOISE_STD)
                est_dist = _euclidean_km(p_o_lat, p_o_lng, p_d_lat, p_d_lng)
                label = _assign_match_label(p_dest, d_dest, zone, d_origin, p_hour, d_hour)
                topup_rows.append({
                    "id": str(uuid.uuid4()),
                    "origin_zone": zone_name,
                    "destination_zone": p_dest.name,
                    "origin_lat": p_o_lat,
                    "origin_lng": p_o_lng,
                    "destination_lat": p_d_lat,
                    "destination_lng": p_d_lng,
                    "departure_at": _hour_to_datetime(p_hour),
                    "estimated_distance_km": est_dist,
                    "driver_origin_zone": d_origin.name,
                    "driver_dest_zone": d_dest.name,
                    "driver_departure_hour": d_hour,
                    "is_driver": False,
                    "match_label": label,
                })
            df = pd.concat([df, pd.DataFrame(topup_rows)], ignore_index=True)
            logger.info("Topped up zone '%s' with %d extra records", zone_name, deficit)

    positive_rate = df["match_label"].mean()
    logger.info(
        "Generated %d rides. Zones (origin): %d. Match label rate: %.1f%%",
        len(df), df["origin_zone"].nunique(), positive_rate * 100,
    )
    return df.reset_index(drop=True)
