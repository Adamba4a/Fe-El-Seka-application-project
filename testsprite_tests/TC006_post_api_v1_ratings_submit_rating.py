import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def test_post_api_v1_ratings_submit_rating():
    """
    Test submitting a rating for a completed ride with valid authenticated user,
    expect success confirmation of rating submission.
    """

    # Step 1: Create a booking to get a completed ride to rate.
    # This requires creating a booking so we have a valid ride_id and driver_id.

    booking_id = None
    rating_id = None

    try:
        # Fetch rides (assuming this endpoint exists and returns at least one completed ride suitable for booking)
        # Since no rides endpoint documented, create booking requires a ride_id, so we must guess or skip to just create booking with a hypothetical ride.
        # We need to create a booking to get a completed ride; however, PRD mentions rides endpoint returns 503 (OSRM issue)
        # So we simulate by creating a booking first with a placeholder ride_id assuming a completed ride exists with id=1.
        # If that is invalid, test might fail due to environment, but per instructions we do the best with available info.

        # Create booking payload
        booking_payload = {
            "ride_id": 1,
            "seat_count": 1
        }

        # Create booking
        resp = requests.post(
            f"{BASE_URL}/api/v1/bookings",
            headers=HEADERS,
            json=booking_payload,
            timeout=30
        )

        # If booking creation fails due to ride_id 1 invalid, test can't proceed.
        assert resp.status_code in (200, 201), f"Booking creation failed: {resp.status_code} {resp.text}"
        booking_data = resp.json()
        booking_id = booking_data.get("id")
        assert booking_id is not None, "Booking ID not found in response."
        ride_id = booking_data.get("ride_id")
        # Target user is the other party in ride: either driver or passenger.
        # From context, rating is post-ride driver <-> passenger rating.
        # Assuming booking_data contains ride info with driver_id or passenger_id; if not, use a placeholder.
        # We'll try to find the 'driver_id' in booking response or fallback.

        driver_id = booking_data.get("driver_id")
        if not driver_id:
            # Fallback: request booking detail to find driver_id?
            resp_detail = requests.get(f"{BASE_URL}/api/v1/bookings/{booking_id}", headers=HEADERS, timeout=30)
            assert resp_detail.status_code == 200, f"Failed getting booking detail: {resp_detail.text}"
            booking_detail = resp_detail.json()
            driver_id = booking_detail.get("driver_id")
        assert driver_id is not None, "Driver ID not found for rating target."

        # Step 2: Submit rating for the completed ride
        rating_payload = {
            "ride_id": ride_id,
            "target_user_id": driver_id,
            "rating": 5,
            "comment": "Great ride!"
        }

        rating_resp = requests.post(
            f"{BASE_URL}/api/v1/ratings",
            headers=HEADERS,
            json=rating_payload,
            timeout=30
        )

        assert rating_resp.status_code in (200, 201), f"Rating submission failed: {rating_resp.status_code} {rating_resp.text}"
        rating_data = rating_resp.json()
        # Check typical properties in rating response, e.g. id, ride_id, target_user_id, rating
        assert "id" in rating_data, "Rating response missing id."
        assert rating_data.get("ride_id") == ride_id, "Rating ride_id mismatch."
        assert rating_data.get("target_user_id") == driver_id, "Rating target_user_id mismatch."
        assert rating_data.get("rating") == 5, "Rating value mismatch."

        rating_id = rating_data.get("id")

    finally:
        # Cleanup: Delete the created booking
        if booking_id:
            try:
                requests.post(f"{BASE_URL}/api/v1/bookings/{booking_id}/cancel", headers=HEADERS, timeout=30)
            except Exception:
                pass

test_post_api_v1_ratings_submit_rating()