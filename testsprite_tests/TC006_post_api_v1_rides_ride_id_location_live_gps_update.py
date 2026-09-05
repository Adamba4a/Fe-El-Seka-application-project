import requests
import uuid

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def test_post_api_v1_rides_ride_id_location_live_gps_update():
    ride_id = None
    try:
        # Create a new ride since no ride_id is provided
        create_ride_payload = {
            "origin": {
                "coordinates": {"lat": 30.0444, "lng": 31.2357},  # Cairo
                "address": "Cairo City Center"
            },
            "destination": {
                "coordinates": {"lat": 30.0626, "lng": 31.2497},   # Nearby point in Cairo
                "address": "Cairo Nearby Point"
            },
            "departure_datetime": "2026-10-01T08:00:00Z",
            "total_seats": 3
        }
        # POST /api/v1/rides
        create_response = requests.post(
            f"{BASE_URL}/api/v1/rides",
            headers=HEADERS,
            json=create_ride_payload,
            timeout=30
        )

        # If running locally, POST /api/v1/rides reliably returns 503, handle this gracefully
        assert create_response.status_code == 200, f"Ride creation failed with status {create_response.status_code}, msg: {create_response.text}"

        ride_data = create_response.json()
        ride_id = ride_data.get("id")
        assert ride_id, "Created ride ID is missing"

        # Prepare live GPS location update payload
        location_payload = {
            "latitude": 30.0500,
            "longitude": 31.2400,
            "timestamp": "2026-10-01T08:15:00Z",
            "accuracy_m": 5.0,
            "altitude": 50.0,
            "speed": 10.5,
            "heading": 90
        }

        # POST location update for the ride
        location_response = requests.post(
            f"{BASE_URL}/api/v1/rides/{ride_id}/location",
            headers=HEADERS,
            json=location_payload,
            timeout=30
        )
        assert location_response.status_code == 200, f"Location update failed with status {location_response.status_code}, msg: {location_response.text}"

        # GET the ride location to verify
        get_location_response = requests.get(
            f"{BASE_URL}/api/v1/rides/{ride_id}/location",
            headers=HEADERS,
            timeout=30
        )
        assert get_location_response.status_code == 200, f"Get location failed with status {get_location_response.status_code}, msg: {get_location_response.text}"

        location_data = get_location_response.json()
        # Validate that the latest location matches what was sent (or at least is recent)
        assert abs(location_data.get("latitude", 0) - location_payload["latitude"]) < 0.0001
        assert abs(location_data.get("longitude", 0) - location_payload["longitude"]) < 0.0001

    finally:
        # Clean up by deleting the created ride if exists
        if ride_id:
            requests.delete(
                f"{BASE_URL}/api/v1/rides/{ride_id}",
                headers=HEADERS,
                timeout=30
            )

test_post_api_v1_rides_ride_id_location_live_gps_update()
