import requests

def test_post_api_routes_fare_with_valid_inputs():
    base_url = "http://localhost:8000"
    url = f"{base_url}/api/routes/fare"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "distance_meters": 12000,
        "pricing": {
            "base_fare": 5.0,
            "cost_per_km": 1.2,
            "minimum_fare": 10.0,
            "currency": "EGP"
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
        data = response.json()
        assert "estimated_fare" in data, "Response JSON missing 'estimated_fare'"
        assert isinstance(data["estimated_fare"], (int, float)), "'estimated_fare' should be a number"
        assert data["estimated_fare"] >= 0, "'estimated_fare' should be non-negative"
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

test_post_api_routes_fare_with_valid_inputs()
