import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def test_post_api_vehicles_register_new_active_vehicle():
    vehicle_payload = {
        "make": "Toyota",
        "model": "Corolla",
        "year": 2020,
        "color": "Blue",
        "license_plate": "ABC1234"
    }

    # Successful POST /api/vehicles to register active vehicle
    post_url = f"{BASE_URL}/api/vehicles"
    response = requests.post(post_url, json=vehicle_payload, headers=HEADERS, timeout=30)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    vehicle_response = response.json()
    assert "id" in vehicle_response and isinstance(vehicle_response["id"], str)
    vehicle_id = vehicle_response["id"]
    # The API sets 'active' internally; check that field if present
    if "active" in vehicle_response:
        assert vehicle_response["active"] is True
    for key in ["make", "model", "year", "color", "license_plate"]:
        assert vehicle_response.get(key) == vehicle_payload[key]

    try:
        # Subsequent GET /api/vehicles/me returns the active vehicle
        get_url = f"{BASE_URL}/api/vehicles/me"
        get_response = requests.get(get_url, headers=HEADERS, timeout=30)
        assert get_response.status_code == 200, f"Expected 200 on GET /api/vehicles/me, got {get_response.status_code}"
        vehicle_me = get_response.json()
        assert vehicle_me.get("id") == vehicle_id
        if "active" in vehicle_me:
            assert vehicle_me.get("active") is True
        for key in ["make", "model", "year", "color", "license_plate"]:
            assert vehicle_me.get(key) == vehicle_payload[key]
    finally:
        pass  # No supported delete endpoint for cleanup

test_post_api_vehicles_register_new_active_vehicle()