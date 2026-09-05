import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def test_get_passenger_facing_ride_preview_and_detail():
    ride_id = None
    import uuid
    import datetime

    # Since we don't have a ride_id, create a new ride first for testing
    # Using a valid nested origin and destination with coordinates and a departure_datetime in the future
    try:
        ride_data = {
            "origin": {
                "coordinates": {"lat": 30.0444, "lng": 31.2357},
                "address": "Cairo, Egypt"
            },
            "destination": {
                "coordinates": {"lat": 30.0131, "lng": 31.2089},
                "address": "Giza, Egypt"
            },
            "departure_datetime": (datetime.datetime.utcnow() + datetime.timedelta(hours=2)).replace(microsecond=0).isoformat() + "Z",
            "total_seats": 3,
            # Provide a valid vehicle_id (random UUID); assuming any UUID is accepted for the test as no real lookup is done here
            "vehicle_id": str(uuid.uuid4())
        }

        create_resp = requests.post(
            f"{BASE_URL}/api/v1/rides",
            headers=HEADERS,
            json=ride_data,
            timeout=30
        )
        # The environment might return 503 due to local OSRM limitation but we must try
        assert create_resp.status_code == 200, f"Ride creation failed with status {create_resp.status_code}: {create_resp.text}"
        created_ride = create_resp.json()
        ride_id = created_ride.get("id")
        assert ride_id is not None, "Created ride response missing 'id'"
        
        # GET /api/v1/rides/{ride_id}/preview as passenger
        preview_resp = requests.get(
            f"{BASE_URL}/api/v1/rides/{ride_id}/preview",
            headers=HEADERS,
            timeout=30
        )
        assert preview_resp.status_code == 200, f"GET preview failed with status {preview_resp.status_code}: {preview_resp.text}"
        preview_json = preview_resp.json()
        # Validate expected minimal preview fields exist (example checks)
        assert "origin" in preview_json
        assert "destination" in preview_json

        # GET /api/v1/rides/{ride_id}/passenger-detail as passenger
        detail_resp = requests.get(
            f"{BASE_URL}/api/v1/rides/{ride_id}/passenger-detail",
            headers=HEADERS,
            timeout=30
        )
        assert detail_resp.status_code == 200, f"GET passenger-detail failed with status {detail_resp.status_code}: {detail_resp.text}"
        detail_json = detail_resp.json()
        # Validate passenger-facing full detail fields including AI match score
        assert "ai_match_score" in detail_json or "aiMatchScore" in detail_json, "AI match score missing in passenger-detail response"
        assert "origin" in detail_json
        assert "destination" in detail_json

    finally:
        # Cleanup: delete the created ride if created
        if ride_id:
            try:
                delete_resp = requests.delete(
                    f"{BASE_URL}/api/v1/rides/{ride_id}",
                    headers=HEADERS,
                    timeout=30
                )
                # No assert here, just best effort cleanup
            except Exception:
                pass

test_get_passenger_facing_ride_preview_and_detail()