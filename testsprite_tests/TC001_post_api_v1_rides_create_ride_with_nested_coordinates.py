import requests
from datetime import datetime, timedelta
import random

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}
TIMEOUT = 30


def test_post_api_v1_rides_create_ride_with_nested_coordinates():
    # Step 1: Get current vehicle id
    vehicles_me_url = f"{BASE_URL}/api/vehicles/me"
    try:
        resp_vehicles = requests.get(vehicles_me_url, headers=HEADERS, timeout=TIMEOUT)
        resp_vehicles.raise_for_status()
    except requests.RequestException as e:
        raise AssertionError(f"Failed to get current vehicle: {e}")
    data_vehicles = resp_vehicles.json()
    vehicle_id = data_vehicles.get("id")
    if not vehicle_id:
        raise AssertionError("No vehicle ID found in /api/vehicles/me response")

    # Step 2: Prepare payload for ride creation
    departure_datetime = datetime.utcnow() + timedelta(hours=48, minutes=random.randint(1, 600))
    departure_iso = departure_datetime.isoformat() + "Z"

    # Example coordinates in Cairo area, arbitrary valid values
    origin_coords = {"lat": 30.0444, "lng": 31.2357}
    destination_coords = {"lat": 30.0626, "lng": 31.2497}

    payload = {
        "origin": {
            "coordinates": origin_coords,
            "address": "Downtown Cairo, Cairo, Egypt"
        },
        "destination": {
            "coordinates": destination_coords,
            "address": "Zamalek, Cairo, Egypt"
        },
        "departure_datetime": departure_iso,
        "total_seats": 3,
        "vehicle_id": vehicle_id
    }

    # Step 3: Post the new ride
    rides_url = f"{BASE_URL}/api/v1/rides"
    try:
        resp = requests.post(rides_url, headers=HEADERS, json=payload, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise AssertionError(f"Request exception during ride creation: {e}")

    # Step 4: Validate response
    if resp.status_code == 201:
        json_resp = resp.json()
        ride = json_resp.get("ride")
        assert ride is not None, "Response JSON missing 'ride' key"
        assert ride.get("id"), "Created ride missing 'id'"
        assert "origin" in ride and "coordinates" in ride["origin"], "Missing nested 'origin.coordinates'"
        assert ride["origin"]["coordinates"] == origin_coords, "Origin coordinates mismatch"
        assert "price_per_seat" in ride, "Missing 'price_per_seat' in ride"
    elif resp.status_code == 503:
        json_resp = resp.json()
        # Expecting error {"error":"route_intelligence_unavailable"} in local dev
        assert json_resp.get("error") == "route_intelligence_unavailable", f"Unexpected error response: {json_resp}"
    else:
        raise AssertionError(f"Unexpected status code {resp.status_code} with body {resp.text}")


test_post_api_v1_rides_create_ride_with_nested_coordinates()