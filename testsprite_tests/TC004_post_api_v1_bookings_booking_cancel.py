import requests

BASE_URL = "http://localhost:8000"
HEADERS = {
    "Authorization": "Bearer eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
}

def test_post_api_v1_bookings_booking_cancel():
    # Create a new booking for testing cancel operation
    try:
        # First get a valid ride_id to create a booking
        # Try to find a ride to book
        rides_resp = requests.get(f"{BASE_URL}/api/v1/rides", headers=HEADERS, timeout=30)
        rides_resp.raise_for_status()
        rides = rides_resp.json()
        if not isinstance(rides, list) or len(rides) == 0:
            raise Exception("No rides available to create a booking.")
        ride = None
        for r in rides:
            # Check if ride has available seats
            if r.get("available_seats", 0) > 0:
                ride = r
                break
        if not ride:
            raise Exception("No rides with available seats found.")

        booking_payload = {
            "ride_id": ride["id"],
            "seat_count": 1
        }
        create_resp = requests.post(f"{BASE_URL}/api/v1/bookings", headers={**HEADERS, "Content-Type": "application/json"}, json=booking_payload, timeout=30)
        create_resp.raise_for_status()
        created_booking = create_resp.json()
        booking_id = created_booking.get("id")
        assert booking_id is not None, "Booking creation failed to return booking id."

        # Cancel the booking
        cancel_resp = requests.post(f"{BASE_URL}/api/v1/bookings/{booking_id}/cancel", headers=HEADERS, timeout=30)
        cancel_resp.raise_for_status()
        cancel_result = cancel_resp.json()
        assert cancel_result.get("status") == "cancelled", "Booking status not updated to cancelled."

        # Verify the booking status by getting booking detail
        detail_resp = requests.get(f"{BASE_URL}/api/v1/bookings/{booking_id}", headers=HEADERS, timeout=30)
        detail_resp.raise_for_status()
        booking_detail = detail_resp.json()
        assert booking_detail.get("status") == "cancelled", "Booking detail status is not cancelled after cancel operation."

    finally:
        # Clean up: delete the booking if still exists and status not cancelled (if API supports delete)
        try:
            # Only delete if booking_id exists and if API supports DELETE (not specified, so just ignore)
            if 'booking_id' in locals() and booking_id:
                # No delete endpoint specified, so try to cancel again or ignore
                # Alternatively, no action
                pass
        except Exception:
            pass

test_post_api_v1_bookings_booking_cancel()