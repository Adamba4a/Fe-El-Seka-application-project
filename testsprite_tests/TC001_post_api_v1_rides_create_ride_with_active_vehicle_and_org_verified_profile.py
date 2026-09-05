import requests
import time

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def test_post_api_v1_rides_create_ride_with_active_vehicle_and_org_verified_profile():
    payload = {
        "departure": {"lat": 30.0444, "lng": 31.2357},
        "destination": {"lat": 30.0626, "lng": 31.2497},
        "departure_time": int(time.time()) + 3600,  # 1 hour in future
        "seats_offered": 3,
        "price_per_seat": 15.50,
        "notes": "Test ride creation with active vehicle and verified profile"
    }

    ride_id = None
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/rides",
            headers=headers,
            json=payload,
            timeout=30
        )
        assert response.status_code == 200, f"Expected status 200 but got {response.status_code}"

        ride = response.json()

        assert "id" in ride, "Ride ID missing in response"
        assert "route_geometry" in ride, "OSRM route geometry missing"
        assert "distance" in ride, "Ride distance missing"
        assert "duration" in ride, "Ride duration missing"
        assert "computed_fare" in ride, "Computed fare missing"

        ride_id = ride["id"]

        rg = ride["route_geometry"]
        assert rg is not None and (isinstance(rg, str) or isinstance(rg, dict)), "Invalid route_geometry"

        assert isinstance(ride["distance"], (int, float)) and ride["distance"] > 0, "Invalid distance"
        assert isinstance(ride["duration"], (int, float)) and ride["duration"] > 0, "Invalid duration"

        fare = ride["computed_fare"]
        assert isinstance(fare, (int, float)) and fare > 0, "Invalid computed_fare"

        time.sleep(2)

        get_response = requests.get(
            f"{BASE_URL}/api/v1/rides/{ride_id}",
            headers=headers,
            timeout=30
        )
        assert get_response.status_code == 200, f"Failed to GET created ride {ride_id}"
        ride_details = get_response.json()

        assert ride_details["id"] == ride_id
        assert "route_geometry" in ride_details
        assert "distance" in ride_details
        assert "duration" in ride_details
        assert "computed_fare" in ride_details

    finally:
        try:
            if ride_id is not None:
                del_response = requests.delete(
                    f"{BASE_URL}/api/v1/rides/{ride_id}",
                    headers=headers,
                    timeout=30
                )
                if del_response.status_code not in (200, 204, 404):
                    print(f"Warning: unexpected DELETE status {del_response.status_code}")
        except Exception:
            pass

test_post_api_v1_rides_create_ride_with_active_vehicle_and_org_verified_profile()
