"""
Validate that build_feature_vector_from_coords is deterministic.
Run: uv run python scripts/validate_determinism.py
"""
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from app.services.feature_engineering import build_feature_vector_from_coords

_SAMPLE = dict(
    passenger_origin_lat=30.0444,
    passenger_origin_lng=31.2357,
    passenger_dest_lat=30.0131,
    passenger_dest_lng=31.2089,
    driver_origin_lat=30.0444,
    driver_origin_lng=31.2357,
    driver_dest_lat=30.0131,
    driver_dest_lng=31.2089,
    overlap_ratio=0.75,
    pickup_detour_km=1.2,
    dropoff_distance_km=0.8,
    departure_at_utc=datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc),
)

RUNS = 10
vectors = [build_feature_vector_from_coords(**_SAMPLE) for _ in range(RUNS)]

for i, v in enumerate(vectors[1:], start=1):
    if not np.array_equal(vectors[0], v):
        print(f"FAIL: run {i} differs from run 0")
        print(f"  run 0: {vectors[0]}")
        print(f"  run {i}: {v}")
        sys.exit(1)

print(f"PASS: {RUNS} runs produced identical 14-dim vectors")
print(f"Vector: {vectors[0]}")
