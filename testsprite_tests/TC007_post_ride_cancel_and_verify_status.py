import requests
import uuid
import datetime
import time

BASE_URL = "http://localhost:8000"
AUTH_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def create_ride():
    url = f"{BASE_URL}/api/v1/rides"
    now = datetime.datetime.utcnow()
    departure_datetime = (now + datetime.timedelta(hours=1)).replace(microsecond=0).isoformat() + "Z"
    vehicle_id = get_active_vehicle_id()
    if not vehicle_id:
        raise Exception("No active vehicle found for the driver, cannot create ride.")
    payload = {
        "origin": {
            "coordinates": {"lat": 30.0444, "lng": 31.2357},
            "address": "Cairo, Egypt"
        },
        "destination": {
            "coordinates": {"lat": 30.0131, "lng": 31.2089},
            "address": "Giza, Egypt"
        },
        "departure_datetime": departure_datetime,
        "total_seats": 3,
        "vehicle_id": vehicle_id
    }
    response = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    if response.status_code == 503 and response.json().get("error") == "route_intelligence_unavailable":
        raise Exception("OSRM routing engine unavailable; test environment does not support ride creation.")
    response.raise_for_status()
    ride = response.json()
    assert ride.get("id"), "Created ride id is missing."
    return ride["id"]

def get_active_vehicle_id():
    # Attempt to get the driver's vehicles by fetching rides and reading vehicle_id from a ride if any exist.
    # Otherwise, this function cannot create a ride since vehicle_id is required.
    # We try to get existing rides and return vehicle_id from first available ride as a fallback.
    rides_url = f"{BASE_URL}/api/v1/rides"
    resp = requests.get(rides_url, headers=HEADERS, timeout=30)
    if resp.status_code == 200:
        rides = resp.json()
        if isinstance(rides, list) and rides:
            first_ride = rides[0]
            vehicle_id = first_ride.get("vehicle_id")
            if vehicle_id:
                return vehicle_id
    # If no rides or vehicle_id found, try to fetch an active vehicle by another mechanism if available.
    # No explicit endpoint provided in PRD, so return None.
    return None

def delete_ride(ride_id):
    # PRD doesn't specify delete endpoint, so cannot delete ride by API.
    # Skipping delete, or if implemented, put here.
    pass

def test_post_ride_cancel_and_verify_status():
    ride_id = None
    try:
        ride_id = create_ride()
        cancel_url = f"{BASE_URL}/api/v1/rides/{ride_id}/cancel"
        cancel_resp = requests.post(cancel_url, headers=HEADERS, timeout=30)
        assert cancel_resp.status_code == 200, f"Expected 200 for cancel, got {cancel_resp.status_code}"
        cancel_data = cancel_resp.json()
        assert cancel_data.get("status") == "cancelled", f"Ride status after cancel expected 'cancelled', got '{cancel_data.get('status')}'"

        get_ride_url = f"{BASE_URL}/api/v1/rides/{ride_id}"
        get_resp = requests.get(get_ride_url, headers=HEADERS, timeout=30)
        assert get_resp.status_code == 200, f"Expected 200 for get ride, got {get_resp.status_code}"
        ride_data = get_resp.json()
        assert ride_data.get("status") == "cancelled", f"Ride status from GET expected 'cancelled', got '{ride_data.get('status')}'"
    finally:
        # No deletion endpoint available, so just pass here.
        pass

test_post_ride_cancel_and_verify_status()