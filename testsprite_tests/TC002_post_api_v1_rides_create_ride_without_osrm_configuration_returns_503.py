import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_post_api_v1_rides_create_ride_without_osrm_configuration_returns_503():
    url = f"{BASE_URL}/api/v1/rides"
    # Use correct payload keys and remove price_per_seat per PRD specification
    payload = {
        "origin": {"latitude": 30.0444, "longitude": 31.2357},
        "destination": {"latitude": 30.0610, "longitude": 31.3260},
        "departure_time": "2026-12-15T08:00:00Z",
        "vehicle_id": "vehicle-123",
        "seats_available": 3
    }

    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request failed unexpectedly: {e}"

    assert response.status_code == 503, f"Expected 503 Service Unavailable, got {response.status_code}"

    try:
        resp_json = response.json()
    except ValueError:
        resp_json = None

    if resp_json:
        # Response should not include any ride id on 503 error
        assert 'id' not in resp_json and 'ride_id' not in resp_json, "Response should not contain created ride id"


test_post_api_v1_rides_create_ride_without_osrm_configuration_returns_503()
