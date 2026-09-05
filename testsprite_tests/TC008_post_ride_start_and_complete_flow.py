import requests
import uuid
from datetime import datetime, timedelta, timezone

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

def test_post_ride_start_and_complete_flow():
    ride_id = None
    try:
        # Step 1: Create a new ride first (needed to perform start and complete)
        now = datetime.now(timezone.utc) + timedelta(hours=1)
        ride_data = {
            "origin": {
                "coordinates": {"lat": 30.0444, "lng": 31.2357},
                "address": "Cairo, Egypt"
            },
            "destination": {
                "coordinates": {"lat": 30.0131, "lng": 31.2089},
                "address": "Giza, Egypt"
            },
            "departure_datetime": now.isoformat(),
            "total_seats": 3,
            # Using a placeholder UUID for vehicle_id. This should be replaced with a valid vehicle_id if known.
            "vehicle_id": str(uuid.uuid4())
        }
        create_resp = requests.post(
            f"{BASE_URL}/api/v1/rides",
            headers=HEADERS,
            json=ride_data,
            timeout=30,
        )
        # Handle local dev 503 fallback (OSRM not configured). Raise if 503.
        if create_resp.status_code == 503:
            error_body = create_resp.json()
            assert error_body.get("error") == "route_intelligence_unavailable"
            # Can't proceed with test if ride can't be created; skip the test
            raise RuntimeError("Cannot create ride in local dev environment (OSRM unavailable).")
        assert create_resp.status_code == 200, f"Ride creation failed: {create_resp.status_code} {create_resp.text}"
        ride_resp_json = create_resp.json()
        ride_id = ride_resp_json.get("id")
        assert ride_id is not None, "Ride ID missing in creation response"

        # Step 2: POST /api/v1/rides/{ride_id}/start
        start_resp = requests.post(
            f"{BASE_URL}/api/v1/rides/{ride_id}/start",
            headers=HEADERS,
            timeout=30,
        )
        assert start_resp.status_code == 200, f"Ride start failed: {start_resp.status_code} {start_resp.text}"
        start_resp_json = start_resp.json()
        # Expect ride status to be 'in-progress' or equivalent
        assert "status" in start_resp_json, "start response missing 'status'"
        status = start_resp_json["status"]
        assert status == "in-progress" or status == "started", f"Unexpected ride status after start: {status}"

        # Step 3: POST /api/v1/rides/{ride_id}/complete
        complete_resp = requests.post(
            f"{BASE_URL}/api/v1/rides/{ride_id}/complete",
            headers=HEADERS,
            timeout=30,
        )
        assert complete_resp.status_code == 200, f"Ride completion failed: {complete_resp.status_code} {complete_resp.text}"
        complete_resp_json = complete_resp.json()
        # Expect ride status to be 'completed' or equivalent
        assert "status" in complete_resp_json, "complete response missing 'status'"
        final_status = complete_resp_json["status"]
        assert final_status == "completed" or final_status == "complete", f"Unexpected ride status after complete: {final_status}"

    finally:
        # Cleanup: delete the ride if it was created, ignore errors
        if ride_id:
            try:
                requests.delete(
                    f"{BASE_URL}/api/v1/rides/{ride_id}",
                    headers=HEADERS,
                    timeout=30,
                )
            except Exception:
                pass

test_post_ride_start_and_complete_flow()