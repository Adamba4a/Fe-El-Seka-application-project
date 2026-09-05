import requests
import datetime
import uuid

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
TIMEOUT = 30

def create_ride_payload(departure_datetime_iso):
    return {
        "origin": {
            "coordinates": {"lat": 30.0444, "lng": 31.2357},
            "address": "Cairo, Egypt"
        },
        "destination": {
            "coordinates": {"lat": 30.0626, "lng": 31.2775},
            "address": "Dokki, Egypt"
        },
        "departure_datetime": departure_datetime_iso,
        "total_seats": 3,
        "vehicle_id": "00000000-0000-4000-8000-000000000001"  # Presumed active vehicle_id for test token
    }

def get_ride(ride_id):
    url = f"{BASE_URL}/api/v1/rides/{ride_id}"
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()

def patch_ride(ride_id, payload):
    url = f"{BASE_URL}/api/v1/rides/{ride_id}"
    return requests.patch(url, json=payload, headers=HEADERS, timeout=TIMEOUT)

def delete_ride(ride_id):
    url = f"{BASE_URL}/api/v1/rides/{ride_id}/cancel"
    # Cancel ride to simulate deletion (assuming no direct DELETE endpoint)
    resp = requests.post(url, headers=HEADERS, timeout=TIMEOUT)
    if resp.status_code not in (200, 404):
        resp.raise_for_status()

def test_patch_ride_after_edit_cutoff_window_forbidden():
    # Create a ride with a departure time already in the past to simulate after cutoff window
    # Set departure_datetime to 1 hour ago
    past_datetime = (datetime.datetime.utcnow() - datetime.timedelta(hours=1)).replace(microsecond=0).isoformat() + "Z"
    ride_payload = create_ride_payload(past_datetime)

    created_ride_id = None
    try:
        create_resp = requests.post(f"{BASE_URL}/api/v1/rides", json=ride_payload, headers=HEADERS, timeout=TIMEOUT)
        if create_resp.status_code == 503:
            # OSRM unavailable in local dev, mark test as skipped by raising AssertionError
            # or just exit test early
            raise AssertionError("Ride creation 503 due to OSRM unavailability in local dev environment")
        create_resp.raise_for_status()
        ride_data = create_resp.json()
        created_ride_id = ride_data.get("id")
        assert created_ride_id, "Created ride did not return an id"
        
        # Get original ride data
        original_ride = get_ride(created_ride_id)
        
        # Attempt to patch ride to change total_seats
        patch_payload = {"total_seats": original_ride.get("total_seats", 3) + 1}
        patch_resp = patch_ride(created_ride_id, patch_payload)

        # Validate the response status code is 403 or 409
        assert patch_resp.status_code in (403, 409), f"Expected 403 or 409 but got {patch_resp.status_code}"

        # Re-fetch the ride to confirm it remains unchanged
        ride_after_patch = get_ride(created_ride_id)
        assert ride_after_patch.get("total_seats") == original_ride.get("total_seats"), "Ride total_seats changed despite forbidden edit"
    finally:
        if created_ride_id:
            delete_ride(created_ride_id)

test_patch_ride_after_edit_cutoff_window_forbidden()
