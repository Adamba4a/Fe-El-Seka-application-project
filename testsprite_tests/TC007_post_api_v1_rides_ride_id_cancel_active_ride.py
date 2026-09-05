import requests
import time
from datetime import datetime, timezone, timedelta

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def test_post_api_v1_rides_ride_id_cancel_active_ride():
    def create_ride():
        url = f"{BASE_URL}/api/v1/rides"
        # Use ISO 8601 datetime string for departure_time
        departure_time_iso = datetime.now(timezone.utc).astimezone().replace(microsecond=0) + timedelta(hours=1)
        departure_time_str = departure_time_iso.isoformat()
        payload = {
            "departure": {"lat": 30.0444, "lng": 31.2357},
            "destination": {"lat": 30.0626, "lng": 31.2497},
            "departure_time": departure_time_str,
            "seats_offered": 3,
            "recurring": False
        }
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        if resp.status_code == 503:
            raise RuntimeError("Ride creation failed due to OSRM routing engine unconfigured (local dev).")
        resp.raise_for_status()
        return resp.json()

    def delete_ride(ride_id):
        url = f"{BASE_URL}/api/v1/rides/{ride_id}"
        try:
            requests.delete(url, headers=HEADERS, timeout=30)
        except Exception:
            pass

    ride_id = None
    try:
        ride = create_ride()
        ride_id = ride.get("id")
        assert ride_id is not None, "Ride ID missing from creation response."

        cancel_url = f"{BASE_URL}/api/v1/rides/{ride_id}/cancel"
        cancel_resp = requests.post(cancel_url, headers=HEADERS, timeout=30)
        assert cancel_resp.status_code == 200, f"Expected status 200 but got {cancel_resp.status_code}"
        cancel_data = cancel_resp.json()
        assert "status" in cancel_data, "Response missing 'status' field"
        assert cancel_data["status"].lower() == "canceled", f"Expected status 'canceled', got '{cancel_data['status']}'"

        get_url = f"{BASE_URL}/api/v1/rides/{ride_id}"
        get_resp = requests.get(get_url, headers=HEADERS, timeout=30)
        assert get_resp.status_code == 200, f"Expected status 200 but got {get_resp.status_code}"
        get_data = get_resp.json()
        assert "status" in get_data, "GET ride response missing 'status' field"
        assert get_data["status"].lower() == "canceled", f"Expected ride status 'canceled', got '{get_data['status']}'"
    finally:
        if ride_id is not None:
            delete_ride(ride_id)

test_post_api_v1_rides_ride_id_cancel_active_ride()
