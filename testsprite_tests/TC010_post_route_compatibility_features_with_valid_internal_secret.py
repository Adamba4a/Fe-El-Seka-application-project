import requests

def test_post_route_compatibility_features_with_valid_internal_secret():
    base_url = "http://localhost:8000"
    url = f"{base_url}/internal/route-intelligence/compatibility-features"

    # Internal secret - assumed header key from typical internal secret patterns
    # The PRD notes internal endpoints authenticate via a shared internal secret header,
    # not the Bearer token used by other endpoints.
    internal_secret = "ed3bfc8744d94d3e9a014ae31bcf82d5"  # Example internal secret, adjust as necessary

    headers = {
        "X-Internal-Secret": internal_secret,
        "Content-Type": "application/json",
    }

    # Sample route data payload structured for compatibility feature computation
    payload = {
        "driver_route": {
            "start": {"lat": 30.0444, "lng": 31.2357},
            "end": {"lat": 30.0626, "lng": 31.2497},
            "waypoints": [
                {"lat": 30.0500, "lng": 31.2400},
                {"lat": 30.0550, "lng": 31.2440}
            ]
        },
        "passenger_route": {
            "start": {"lat": 30.0450, "lng": 31.2360},
            "end": {"lat": 30.0600, "lng": 31.2480},
            "waypoints": []
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        assert response.status_code == 200, f"Unexpected status code: {response.status_code}"

        json_data = response.json()
        # Validate expected keys in the response indicating computed features
        expected_keys = {"route_overlap_score", "time_compatibility_score", "distance_compatibility_score"}
        assert expected_keys.issubset(json_data.keys()), f"Response missing expected keys: {expected_keys - json_data.keys()}"

        # Further assertions can be added depending on returned values type and ranges
        for key in expected_keys:
            value = json_data[key]
            assert isinstance(value, (int, float)), f"{key} should be numeric"
            assert 0 <= value <= 1, f"{key} should be between 0 and 1"

    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

test_post_route_compatibility_features_with_valid_internal_secret()