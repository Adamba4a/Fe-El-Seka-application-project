"""
Basic load test for the AI service prediction endpoints.
Run with service already started: uv run python scripts/load_test.py
"""
import statistics
import sys
import time

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: uv add httpx")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8001"
BATCH_SIZE = 50
ITERATIONS = 20
TIMEOUT = 10.0

_CANDIDATE = {
    "passenger_origin": {"lat": 30.0444, "lng": 31.2357},
    "passenger_destination": {"lat": 30.0131, "lng": 31.2089},
    "driver_origin": {"lat": 30.0500, "lng": 31.2400},
    "driver_destination": {"lat": 30.0100, "lng": 31.2050},
    "overlap_ratio": 0.70,
    "pickup_detour_km": 1.5,
    "dropoff_distance_km": 0.9,
    "departure_at": "2026-06-01T08:00:00Z",
}


def bench(client: httpx.Client, endpoint: str, payload: dict) -> float:
    t0 = time.perf_counter()
    resp = client.post(f"{BASE_URL}/{endpoint}", json=payload, timeout=TIMEOUT)
    elapsed = (time.perf_counter() - t0) * 1000
    if resp.status_code != 200:
        print(f"  WARN {endpoint} → {resp.status_code}: {resp.text[:120]}")
    return elapsed


def main() -> None:
    with httpx.Client() as client:
        # Health check first
        resp = client.get(f"{BASE_URL}/health", timeout=5.0)
        print(f"Health: {resp.status_code} {resp.json()}")

        batch = {"candidates": [_CANDIDATE] * BATCH_SIZE}
        price_req = {
            "passenger_origin": {"lat": 30.0444, "lng": 31.2357},
            "passenger_destination": {"lat": 30.0131, "lng": 31.2089},
            "dest_zone_distance_km": 4.5,
            "departure_at": "2026-06-01T08:00:00Z",
        }

        for label, endpoint, payload in [
            ("match-score", "predict/match-score", batch),
            ("ride-ranking", "predict/ride-ranking", {
                "candidates": [{**_CANDIDATE, "candidate_id": str(i)} for i in range(BATCH_SIZE)]
            }),
            ("price", "predict/price-recommendation", price_req),
        ]:
            times = [bench(client, endpoint, payload) for _ in range(ITERATIONS)]
            p50 = statistics.median(times)
            p95 = statistics.quantiles(times, n=20)[18]
            print(
                f"{label:20s} batch={BATCH_SIZE if 'candidates' in payload else 1}  "
                f"p50={p50:.1f}ms  p95={p95:.1f}ms  "
                f"min={min(times):.1f}ms  max={max(times):.1f}ms"
            )


if __name__ == "__main__":
    main()
