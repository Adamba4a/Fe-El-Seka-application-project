import requests
from datetime import datetime, timedelta
import uuid

BASE_URL = "http://localhost:8000"
AUTH_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
}

def test_patch_ride_before_edit_cutoff_window():
    ride_id = None
    try:
        future_departure = (datetime.utcnow() + timedelta(days=5)).isoformat() + "Z"
        vehicle_id = str(uuid.uuid4())

        create_payload = {
            "origin": {
                "coordinates": {"lat": 30.0444, "lng": 31.2357},
                "address": "Cairo, Egypt"
            },
            "destination": {
                "coordinates": {"lat": 30.0131, "lng": 31.2089},
                "address": "Giza, Egypt"
            },
            "departure_datetime": future_departure,
            "total_seats": 3,
            "vehicle_id": vehicle_id
        }

        create_response = requests.post(
            f"{BASE_URL}/api/v1/rides",
            headers=HEADERS,
            json=create_payload,
            timeout=30
        )

        if create_response.status_code == 503:
            raise Exception("Ride creation failed due to route_intelligence_unavailable (local dev environment)")

        assert create_response.status_code == 200, f"Failed to create ride, status: {create_response.status_code}, body: {create_response.text}"
        created_ride = create_response.json()
        ride_id = created_ride.get("ride_id") or created_ride.get("id")
        assert ride_id is not None, "Created ride response missing ride_id"

        patch_payload = {
            "total_seats": 4,
            "destination": {
                "coordinates": {"lat": 30.0131, "lng": 31.2089},
                "address": "Giza Plateau, Egypt"
            }
        }

        patch_response = requests.patch(
            f"{BASE_URL}/api/v1/rides/{ride_id}",
            headers=HEADERS,
            json=patch_payload,
            timeout=30
        )

        assert patch_response.status_code == 200, f"Patch failed with status: {patch_response.status_code}, body: {patch_response.text}"
        patched_ride = patch_response.json()

        assert patched_ride.get("total_seats") == 4, f"Expected total_seats 4, got {patched_ride.get('total_seats')}"
        updated_destination = patched_ride.get("destination")
        assert updated_destination is not None, "Updated ride missing destination field"
        assert updated_destination.get("address") == "Giza Plateau, Egypt", "Destination address did not update correctly"

        get_response = requests.get(
            f"{BASE_URL}/api/v1/rides/{ride_id}",
            headers=HEADERS,
            timeout=30
        )

        assert get_response.status_code == 200, f"Get ride failed with status: {get_response.status_code}, body: {get_response.text}"
        ride_details = get_response.json()
        assert ride_details.get("total_seats") == 4, "Persisted ride total_seats not updated"
        ride_destination = ride_details.get("destination")
        assert ride_destination is not None, "Ride details missing destination"
        assert ride_destination.get("address") == "Giza Plateau, Egypt", "Persisted destination address not updated"

    finally:
        if ride_id:
            try:
                requests.delete(
                    f"{BASE_URL}/api/v1/rides/{ride_id}",
                    headers=HEADERS,
                    timeout=30
                )
            except Exception:
                pass

test_patch_ride_before_edit_cutoff_window()
