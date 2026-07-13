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
_DEG_TO_KM = 111.0
_POSITIVE_ATTEMPT_PROB = 0.35
_POSITIVE_TIME_JITTER_HOURS = 0.4  # 24 min, safely under the 30 min window

# Route-quality feature distributions (overlap_ratio, pickup_detour_km,
# dropoff_distance_km). These are sampled continuously — not derived as an exact
# deterministic function of zone identity — so the model sees the same kind of
# smoothly-varying, imperfect values that real OSRM/PostGIS route geometry produces
# at serving time (e.g. 92.68% overlap / 2.69km walk, never exactly 100%/0km).
# Superseded 2026-07-04: previously overlap/detour were computed as an exact
# function of zone-centroid distance (1.0/0km for same-zone pairs, wildly different
# otherwise), which taught the model a brittle "same zone name = match" shortcut
# that collapsed on realistic, imperfect real-world inputs. See research.md.
_OVERLAP_GOOD_BETA_A, _OVERLAP_GOOD_BETA_B = 5.0, 1.5   # skewed high, scaled to [0.3, 1.0]
_OVERLAP_POOR_BETA_A, _OVERLAP_POOR_BETA_B = 1.5, 4.0   # skewed low, scaled to [0.0, 0.6]
_PICKUP_GOOD_SCALE_KM = 0.6
_DROPOFF_GOOD_SCALE_KM = 0.4
_PICKUP_POOR_SCALE_KM = 4.0
_DROPOFF_POOR_SCALE_KM = 3.0
_GOOD_DETOUR_CAP_KM = 6.0
_POOR_DETOUR_CAP_KM = 60.0

# Label logistic-regression coefficients, tuned so the 100k-row corpus lands in the
# 30-40% positive rate band (see data-model.md Entity 2 constraint).
_LABEL_OVERLAP_COEF = 4.0
_LABEL_PICKUP_COEF = -0.9
_LABEL_DROPOFF_COEF = -1.3
_LABEL_TIME_DIFF_COEF = -0.04
_LABEL_INTERCEPT = 0.8


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


def _sample_route_quality(
    rng: np.random.Generator, is_same_corridor: bool
) -> tuple[float, float, float]:
    """Sample (overlap_ratio, pickup_detour_km, dropoff_distance_km).

    `is_same_corridor` biases the distribution toward realistic "good match" values
    (high overlap, small walks) or realistic "unrelated route" values (low overlap,
    large walks) — but never pins them to an exact boundary value, so the label
    below is a genuinely probabilistic function of continuous, noisy features.
    """
    if is_same_corridor:
        overlap = 0.3 + rng.beta(_OVERLAP_GOOD_BETA_A, _OVERLAP_GOOD_BETA_B) * 0.7
        pickup_km = min(rng.exponential(_PICKUP_GOOD_SCALE_KM), _GOOD_DETOUR_CAP_KM)
        dropoff_km = min(rng.exponential(_DROPOFF_GOOD_SCALE_KM), _GOOD_DETOUR_CAP_KM)
    else:
        overlap = rng.beta(_OVERLAP_POOR_BETA_A, _OVERLAP_POOR_BETA_B) * 0.6
        pickup_km = min(rng.exponential(_PICKUP_POOR_SCALE_KM), _POOR_DETOUR_CAP_KM)
        dropoff_km = min(rng.exponential(_DROPOFF_POOR_SCALE_KM), _POOR_DETOUR_CAP_KM)
    return float(overlap), float(pickup_km), float(dropoff_km)


def _assign_match_label(
    rng: np.random.Generator,
    overlap_ratio: float,
    pickup_detour_km: float,
    dropoff_distance_km: float,
    time_diff_minutes: float,
) -> tuple[int, float]:
    """Returns (hard_label, p_match).

    p_match is the continuous match probability from the logistic function of the
    same route-quality features the model trains on — mirroring how
    route_service.assess_compatibility() judges real candidates on a continuum
    rather than a hard zone-identity cutoff. This is now kept as the training
    target itself (see engineer.py / train_match_score.py) rather than being
    discarded in favour of a single Bernoulli coin-flip: the coin-flip's job is
    only to provide a hard label for AUC evaluation, never for training, since
    fitting a deep tree to individual coin-flips (see research.md, superseded
    2026-07-04 calibration fix) taught the model to reproduce sampling noise
    instead of the underlying probability.
    """
    quality = (
        _LABEL_OVERLAP_COEF * overlap_ratio
        + _LABEL_PICKUP_COEF * pickup_detour_km
        + _LABEL_DROPOFF_COEF * dropoff_distance_km
        + _LABEL_TIME_DIFF_COEF * time_diff_minutes
        + _LABEL_INTERCEPT
    )
    p_match = 1.0 / (1.0 + math.exp(-quality))
    return int(rng.random() < p_match), p_match


def _make_row(
    rng: np.random.Generator,
    p_origin: CairoZone,
    p_dest: CairoZone,
    p_hour: float,
) -> dict:
    is_same_corridor = rng.random() < _POSITIVE_ATTEMPT_PROB
    if is_same_corridor:
        # Construct a plausible carpool corridor: same origin/destination zone,
        # departure close in time — real matches are geographically scarce
        # but not vanishingly rare, per research.md Decision 2.
        d_origin_zone = p_origin
        d_dest = p_dest
        jitter = rng.uniform(-_POSITIVE_TIME_JITTER_HOURS, _POSITIVE_TIME_JITTER_HOURS)
        d_hour = float(np.clip(p_hour + jitter, 0.0, 23.999))
    else:
        weights = np.array([z.weight for z in ZONES])
        d_origin_zone = ZONES[rng.choice(len(ZONES), p=weights)]
        d_dest = ZONES[rng.choice(len(ZONES), p=weights)]
        d_hour = _sample_departure_hour(rng)

    p_o_lat = p_origin.centroid_lat + rng.normal(0, _COORD_NOISE_STD)
    p_o_lng = p_origin.centroid_lng + rng.normal(0, _COORD_NOISE_STD)
    p_d_lat = p_dest.centroid_lat + rng.normal(0, _COORD_NOISE_STD)
    p_d_lng = p_dest.centroid_lng + rng.normal(0, _COORD_NOISE_STD)

    est_dist = _euclidean_km(p_o_lat, p_o_lng, p_d_lat, p_d_lng)
    overlap_ratio, pickup_km, dropoff_km = _sample_route_quality(rng, is_same_corridor)
    time_diff = abs(p_hour - d_hour) * 60
    label, p_match = _assign_match_label(rng, overlap_ratio, pickup_km, dropoff_km, time_diff)

    return {
        "id": str(uuid.uuid4()),
        "origin_zone": p_origin.name,
        "destination_zone": p_dest.name,
        "origin_lat": p_o_lat,
        "origin_lng": p_o_lng,
        "destination_lat": p_d_lat,
        "destination_lng": p_d_lng,
        "departure_at": _hour_to_datetime(p_hour),
        "estimated_distance_km": est_dist,
        "driver_origin_zone": d_origin_zone.name,
        "driver_dest_zone": d_dest.name,
        "driver_departure_hour": d_hour,
        "is_driver": False,
        "overlap_ratio": overlap_ratio,
        "pickup_detour_km": pickup_km,
        "dropoff_distance_km": dropoff_km,
        "match_label": label,
        "match_prob": p_match,
    }


def generate_rides(n: int = 100_000) -> pd.DataFrame:
    rng = np.random.default_rng(_RNG_SEED)
    weights = np.array([z.weight for z in ZONES])
    zone_names = [z.name for z in ZONES]

    rows = []
    for _ in range(n):
        p_origin = ZONES[rng.choice(len(ZONES), p=weights)]
        p_dest = ZONES[rng.choice(len(ZONES), p=weights)]
        p_hour = _sample_departure_hour(rng)
        rows.append(_make_row(rng, p_origin, p_dest, p_hour))

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
                topup_rows.append(_make_row(rng, zone, p_dest, p_hour))
            df = pd.concat([df, pd.DataFrame(topup_rows)], ignore_index=True)
            logger.info("Topped up zone '%s' with %d extra records", zone_name, deficit)

    positive_rate = df["match_label"].mean()
    logger.info(
        "Generated %d rides. Zones (origin): %d. Match label rate: %.1f%%",
        len(df), df["origin_zone"].nunique(), positive_rate * 100,
    )
    return df.reset_index(drop=True)
