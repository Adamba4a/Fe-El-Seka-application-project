import requests
import datetime
import time

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_patch_api_v1_rides_ride_id_edit_within_edit_window():
    create_url = f"{BASE_URL}/api/v1/rides"
    create_payload = {
        "departure_address": "Cairo, Egypt",
        "departure_coordinates": [31.2357, 30.0444],
        "destination_address": "Giza, Egypt",
        "destination_coordinates": [31.1313, 30.0131],
        "departure_time": (datetime.datetime.utcnow() + datetime.timedelta(hours=4)).isoformat() + "Z",
        "seats": 3,
        "vehicle_id": "123e4567-e89b-12d3-a456-426614174000"
    }

    ride_id = None
    try:
        response = requests.post(create_url, json=create_payload, headers=HEADERS, timeout=30)
        if response.status_code == 503:
            raise RuntimeError("Service unavailable (503) due to OSRM routing engine not being configured locally.")
        response.raise_for_status()
        ride = response.json()
        ride_id = ride.get("id")
        assert ride_id is not None, "No ride ID returned on creation"

        patch_url = f"{BASE_URL}/api/v1/rides/{ride_id}"
        patch_payload = {
            "departure_address": "Heliopolis, Cairo",
            "price_per_seat": 45.0
        }
        patch_response = requests.patch(patch_url, json=patch_payload, headers=HEADERS, timeout=30)
        assert patch_response.status_code == 200, f"Patch ride failed with status {patch_response.status_code}"
        patched_ride = patch_response.json()

        assert patched_ride.get("departure_address") == patch_payload["departure_address"], "Departure address not updated"
        assert patched_ride.get("price_per_seat") == patch_payload["price_per_seat"], "Price per seat not updated"

        get_url = f"{BASE_URL}/api/v1/rides/{ride_id}"
        get_response = requests.get(get_url, headers=HEADERS, timeout=30)
        assert get_response.status_code == 200, f"Get ride failed with status {get_response.status_code}"
        ride_data = get_response.json()

        assert ride_data.get("departure_address") == patch_payload["departure_address"], "Departure address not updated in GET"
        assert ride_data.get("price_per_seat") == patch_payload["price_per_seat"], "Price per seat not updated in GET"

    finally:
        if ride_id is not None:
            del_url = f"{BASE_URL}/api/v1/rides/{ride_id}"
            try:
                requests.delete(del_url, headers=HEADERS, timeout=30)
            except Exception:
                pass

test_patch_api_v1_rides_ride_id_edit_within_edit_window()
