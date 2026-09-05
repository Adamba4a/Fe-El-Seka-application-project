import requests

def test_post_api_v1_bookings_create_booking():
    base_url = "http://localhost:8000"
    token = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    timeout = 30
    ride_id = None
    booking_id = None

    try:
        # Step 1: To create a booking, we need a valid ride_id.
        # The PRD notes local ride creation returns 503, so try to get a list of rides to find a valid ride_id.
        # If no rides available, test cannot proceed, so we raise an error.
        rides_resp = requests.get(f"{base_url}/api/v1/rides", headers=headers, timeout=timeout)
        rides_resp.raise_for_status()
        rides_data = rides_resp.json()
        if not rides_data or not isinstance(rides_data, list):
            raise RuntimeError("No rides available to test booking creation.")
        # Pick first available ride id
        ride_id = rides_data[0].get("id") if isinstance(rides_data[0], dict) else None
        if not ride_id:
            raise RuntimeError("No valid ride_id available in rides list.")
        
        # Step 2: Create booking with valid ride_id and seat count (1 seat)
        payload = {
            "ride_id": ride_id,
            "seats": 1
        }
        create_resp = requests.post(f"{base_url}/api/v1/bookings", headers=headers, json=payload, timeout=timeout)
        # Accept 200 or 201 status codes for creation
        assert create_resp.status_code in (200,201), f"Unexpected status code: {create_resp.status_code}"
        data = create_resp.json()
        assert isinstance(data, dict), "Response JSON is not an object"
        # Assert essential booking details present
        assert "id" in data, "Booking response missing 'id'"
        assert data.get("ride_id") == ride_id, "Booking response ride_id mismatch"
        assert data.get("seats") == 1, "Booking response seat count mismatch"
        assert data.get("status") in ("active", "confirmed", "pending", None), "Booking status missing or unexpected"

        booking_id = data["id"]

    finally:
        # Cleanup: delete the booking if created
        if booking_id:
            try:
                cancel_resp = requests.post(f"{base_url}/api/v1/bookings/{booking_id}/cancel", headers=headers, timeout=timeout)
                # Accept 200 or 204 for cancel confirmation
                if cancel_resp.status_code not in (200, 204):
                    # Try direct delete if supported (not in PRD, so just warning)
                    pass
            except Exception:
                pass

test_post_api_v1_bookings_create_booking()