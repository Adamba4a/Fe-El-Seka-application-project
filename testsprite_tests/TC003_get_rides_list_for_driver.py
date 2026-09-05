import requests


BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
TIMEOUT = 30


def test_get_rides_list_for_driver():
    url = f"{BASE_URL}/api/v1/rides"
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        assert response.status_code == 200, f"Expected 200 but got {response.status_code}"
        data = response.json()
        # Expecting the response to be a JSON list (or object with a list) containing ride items.
        # We validate that it is a list and each item contains expected ride fields.
        assert isinstance(data, list) or isinstance(data, dict), "Response JSON should be list or dict"
        rides = data if isinstance(data, list) else data.get("rides", data)
        assert isinstance(rides, list), "Rides data should be a list"

        # If rides list is non-empty, verify structure of first ride
        if rides:
            ride = rides[0]
            # Basic expected keys based on typical ride details
            expected_keys = {"id", "origin", "destination", "departure_datetime", "total_seats", "vehicle_id"}
            assert all(key in ride for key in expected_keys), f"Ride missing expected keys: {expected_keys - ride.keys()}"

            # Validate nested origin/destination structure
            for place in ("origin", "destination"):
                place_obj = ride.get(place, {})
                assert "coordinates" in place_obj and "address" in place_obj
                coords = place_obj.get("coordinates", {})
                assert "lat" in coords and isinstance(coords["lat"], (float, int))
                assert "lng" in coords and isinstance(coords["lng"], (float, int))

            # departure_datetime should be a non-empty string
            assert isinstance(ride["departure_datetime"], str) and ride["departure_datetime"], "departure_datetime should be a non-empty string"

            # total_seats should be int > 0
            assert isinstance(ride["total_seats"], int) and ride["total_seats"] > 0

            # vehicle_id should be a non-empty string (UUID)
            assert isinstance(ride["vehicle_id"], str) and ride["vehicle_id"]

    except requests.RequestException as e:
        assert False, f"Request to get rides failed: {e}"


test_get_rides_list_for_driver()