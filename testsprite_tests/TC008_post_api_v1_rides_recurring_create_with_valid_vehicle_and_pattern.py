import requests
import datetime
import uuid

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def test_post_api_v1_rides_recurring_create_with_valid_vehicle_and_pattern():
    # Use a valid UUID string placeholder for vehicle_id
    vehicle_id = "123e4567-e89b-12d3-a456-426614174000"

    # Prepare recurring ride definition payload
    # Weekly recurrence on Monday (1), Wednesday (3), Friday(5), for next 4 weeks
    payload = {
        "vehicle_id": vehicle_id,
        "recurrence_pattern": {
            "type": "weekly",
            "days_of_week": [1, 3, 5]
        },
        "start_date": datetime.date.today().isoformat(),
        "end_date": (datetime.date.today() + datetime.timedelta(weeks=4)).isoformat(),
        "origin": {"address": "Cairo, Egypt"},
        "destination": {"address": "Giza, Egypt"},
        "departure_time": "08:00",
        "weekdays": [1, 3, 5],
        "total_seats": 3,
        "price_per_seat": 30.0
    }

    created_recurring_ride_id = None
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/rides/recurring",
            headers=HEADERS,
            json=payload,
            timeout=30,
        )
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"

        data = resp.json()
        assert "id" in data, "Response missing recurring ride definition id"
        created_recurring_ride_id = data["id"]
        assert data.get("vehicle_id") == vehicle_id, "Vehicle ID mismatch in response"
        assert data.get("recurrence_pattern", {}).get("type") == "weekly", "Recurrence pattern type mismatch"
        days = data.get("recurrence_pattern", {}).get("days_of_week", [])
        for d in [1, 3, 5]:
            assert d in days, f"Day {d} missing in recurrence pattern days_of_week"
        origin = data.get("origin")
        assert isinstance(origin, dict) and origin.get("address") == "Cairo, Egypt"
        destination = data.get("destination")
        assert isinstance(destination, dict) and destination.get("address") == "Giza, Egypt"
        assert data.get("departure_time") == "08:00"
        assert data.get("total_seats") == 3
        assert data.get("price_per_seat") == 30.0

    finally:
        if created_recurring_ride_id:
            del_resp = requests.delete(
                f"{BASE_URL}/api/v1/rides/recurring/{created_recurring_ride_id}",
                headers=HEADERS,
                timeout=30,
            )
            assert del_resp.status_code in [200, 204], f"Failed to delete recurring ride definition {created_recurring_ride_id}: {del_resp.text}"

test_post_api_v1_rides_recurring_create_with_valid_vehicle_and_pattern()
