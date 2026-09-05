import requests
import uuid

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def test_post_api_v1_rides_recurring_create_with_invalid_or_inactive_vehicle():
    url = f"{BASE_URL}/api/v1/rides/recurring"

    # Use a valid UUID format string to pass UUID parsing but presumably invalid/inactive
    invalid_vehicle_id = str(uuid.UUID("12345678-1234-5678-1234-567812345678"))

    # Correct payload with required fields and proper structure
    payload = {
        "vehicle_id": invalid_vehicle_id,
        "weekdays": [0, 2, 4],  # Monday=0, Wednesday=2, Friday=4
        "departure_time": "08:00:00",
        "total_seats": 4,
        "price_per_seat": 10.0,
        "origin": {
            "coordinates": {"lng": 31.2357, "lat": 30.0444},  # dict instead of list
            "address": "Tahrir Square, Cairo"
        },
        "destination": {
            "coordinates": {"lng": 31.2238, "lat": 30.0595},  # dict instead of list
            "address": "Downtown, Cairo"
        }
    }

    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    assert response.status_code in (400, 403), (
        f"Expected status code 400 or 403, got {response.status_code}. Response: {response.text}"
    )

    # Confirm no recurring ride definition is created
    get_url = f"{BASE_URL}/api/v1/rides/recurring"
    try:
        list_response = requests.get(get_url, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        assert False, f"List request failed: {e}"

    assert list_response.status_code == 200, (
        f"Expected 200 for recurring rides list, got {list_response.status_code}. Response: {list_response.text}"
    )

    try:
        recurring_rides = list_response.json()
    except ValueError as e:
        assert False, f"Response is not valid JSON: {e}"

    # Verify that no recurring ride definition with the invalid vehicle_id exists
    for rec in recurring_rides:
        vid = rec.get('vehicle_id') or rec.get('vehicle', {}).get('id')
        assert vid != invalid_vehicle_id, (
            "Recurring ride definition with invalid or inactive vehicle_id was created unexpectedly"
        )


test_post_api_v1_rides_recurring_create_with_invalid_or_inactive_vehicle()