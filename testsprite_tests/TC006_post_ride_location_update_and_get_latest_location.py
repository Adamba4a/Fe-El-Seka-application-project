import requests
import datetime
import time

BASE_URL = "http://localhost:8000"
AUTH_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {"Authorization": f"Bearer {AUTH_TOKEN}", "Content-Type": "application/json"}
TIMEOUT = 30


def test_post_ride_location_update_and_get_latest_location():
    ride_id = None
    try:
        # Step 1: Create a new ride to get a ride_id
        now = datetime.datetime.utcnow()
        departure_time = (now + datetime.timedelta(hours=1)).isoformat() + "Z"
        # Sample valid vehicle_id (must be valid for test environment)
        vehicle_id = "00000000-0000-0000-0000-000000000001"

        ride_data = {
            "origin": {
                "coordinates": {"lat": 30.0444, "lng": 31.2357},
                "address": "Cairo, Egypt"
            },
            "destination": {
                "coordinates": {"lat": 30.0626, "lng": 31.2497},
                "address": "Downtown Cairo, Egypt"
            },
            "departure_datetime": departure_time,
            "total_seats": 3,
            "vehicle_id": vehicle_id
        }

        post_ride_resp = requests.post(
            f"{BASE_URL}/api/v1/rides",
            json=ride_data,
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        # It is possible this returns 503 in local dev (OSRM routing unavailable) - in this case we fail test
        assert post_ride_resp.status_code == 200, f"Ride creation failed: {post_ride_resp.status_code} {post_ride_resp.text}"
        ride = post_ride_resp.json()
        ride_id = ride.get("id")
        assert ride_id, "Ride ID not returned from creation."

        # Step 2: Post a live GPS location update for the ride
        location_update = {
            "coordinates": {"lat": 30.0500, "lng": 31.2400},
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }

        post_location_resp = requests.post(
            f"{BASE_URL}/api/v1/rides/{ride_id}/location",
            json=location_update,
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        assert post_location_resp.status_code == 200, f"Location update failed: {post_location_resp.status_code} {post_location_resp.text}"

        # Step 3: Get the most recent driver location for the ride
        # Wait briefly to ensure location update processing (if async)
        time.sleep(1)
        get_location_resp = requests.get(
            f"{BASE_URL}/api/v1/rides/{ride_id}/location",
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        assert get_location_resp.status_code == 200, f"Getting ride location failed: {get_location_resp.status_code} {get_location_resp.text}"
        location_data = get_location_resp.json()

        # Validate that the location returned matches the update sent
        returned_coordinates = location_data.get("coordinates")
        assert returned_coordinates, "No coordinates returned in location response."
        lat_diff = abs(returned_coordinates.get("lat") - location_update["coordinates"]["lat"])
        lng_diff = abs(returned_coordinates.get("lng") - location_update["coordinates"]["lng"])
        # Allow minimal difference due to floating point precision
        assert lat_diff < 0.0001 and lng_diff < 0.0001, f"Returned location does not match posted location: {returned_coordinates}"
    finally:
        # Cleanup: delete the created ride if possible to keep test environment clean
        if ride_id:
            try:
                requests.delete(
                    f"{BASE_URL}/api/v1/rides/{ride_id}",
                    headers=HEADERS,
                    timeout=TIMEOUT,
                )
            except Exception:
                pass


test_post_ride_location_update_and_get_latest_location()