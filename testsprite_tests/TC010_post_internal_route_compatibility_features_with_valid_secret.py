import requests

def test_post_internal_route_compatibility_features_with_valid_secret():
    base_url = "http://localhost:8000"
    url = f"{base_url}/internal/route-intelligence/compatibility"
    headers = {
        "X-Internal-Secret": "dev-internal-secret-t039",
        "Content-Type": "application/json"
    }
    payload = {
        "ride_id": "1113f6bd-7e6a-448f-8226-be0e90cb3a8b",
        "passenger_origin": {"lat": 30.0444, "lng": 31.2357},
        "passenger_destination": {"lat": 30.0626, "lng": 31.2497},
        "requested_departure_time": "2026-09-06T09:00:00Z"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    data = response.json()
    assert response.status_code == 200
    # Validate expected keys in response (example: overlap_pct, pickup_walk_m)
    assert isinstance(data, dict)
    assert "overlap_pct" in data
    assert isinstance(data["overlap_pct"], (float, int))
    assert "pickup_walk_m" in data
    assert isinstance(data["pickup_walk_m"], (float, int))

test_post_internal_route_compatibility_features_with_valid_secret()