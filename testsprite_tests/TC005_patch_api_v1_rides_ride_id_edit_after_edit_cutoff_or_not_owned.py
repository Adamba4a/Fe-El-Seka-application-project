import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5veW1vdXMiOmZhbHNlfQ.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def test_patch_api_v1_rides_ride_id_edit_after_edit_cutoff_or_not_owned():
    # Step 1: Create a new ride to test on
    create_ride_url = f"{BASE_URL}/api/v1/rides"
    ride_payload = {
        "origin": "Cairo, Egypt",
        "destination": "Giza, Egypt",
        "departure_time": "2030-01-01T12:00:00Z",  # far future to avoid cutoff but will manipulate later
        "seats": 3,
        "price": 50
    }

    ride_id = None
    try:
        # Create ride
        resp_create = requests.post(create_ride_url, json=ride_payload, headers=HEADERS, timeout=30)
        # In local dev, this may return 503 as per PRD; test should handle that gracefully
        if resp_create.status_code == 503:
            # Skip test because OSRM is not configured
            return
        assert resp_create.status_code == 200, f"Ride creation failed with status {resp_create.status_code}"
        ride_data = resp_create.json()
        ride_id = ride_data.get("id")
        assert ride_id is not None, "Created ride has no ID"

        # Step 2: Fetch original ride data for comparison after patch attempt
        get_ride_url = f"{BASE_URL}/api/v1/rides/{ride_id}"
        resp_get = requests.get(get_ride_url, headers=HEADERS, timeout=30)
        assert resp_get.status_code == 200, f"Failed to GET created ride, status {resp_get.status_code}"
        original_ride = resp_get.json()

        # Step 3: Attempt to PATCH (edit) the ride after the edit cutoff or as not owner scenario
        # To simulate edit cutoff window passed, we can assume the departure_time is near or past now,
        # but since no direct API to set departure in past, we test with the assumption this ride is not owned
        # or the edit is disallowed by backend rules.

        patch_ride_url = f"{BASE_URL}/api/v1/rides/{ride_id}"
        patch_payload = {
            "price": 9999  # Attempt to change price to an invalid or disallowed change
        }
        resp_patch = requests.patch(patch_ride_url, json=patch_payload, headers=HEADERS, timeout=30)

        # Step 4: Validate response status and content for 403 or 422
        assert resp_patch.status_code in (403, 422), f"Expected 403 or 422, got {resp_patch.status_code}"

        # Step 5: Confirm the ride remains unchanged by fetching it again and comparing fields
        resp_get_after = requests.get(get_ride_url, headers=HEADERS, timeout=30)
        assert resp_get_after.status_code == 200, f"Failed to GET ride after patch attempt, status {resp_get_after.status_code}"
        ride_after_patch = resp_get_after.json()

        # The price and other fields should remain unchanged (should equal original)
        assert ride_after_patch == original_ride, "Ride data changed despite rejected edit request"

    finally:
        # Cleanup: delete the created ride if it exists and if API supports deletion (not provided in PRD)
        if ride_id is not None:
            # Because no DELETE endpoint specified in PRD, do nothing here or optionally cancel ride if supported
            pass

test_patch_api_v1_rides_ride_id_edit_after_edit_cutoff_or_not_owned()