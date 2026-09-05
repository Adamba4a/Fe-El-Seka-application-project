import requests
import uuid

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def test_post_api_v1_bookings_booking_seats_add_seats():
    """
    Test adding seats to an existing booking owned by the authenticated passenger,
    expect success response with updated seat count.
    """
    created_booking_id = None
    created_ride_id = None
    try:
        # Step 1: Create a new ride (needed to create a booking)
        # Since rides creation returns 503 locally, we must skip actual ride creation,
        # We will try to get an existing ride from passenger's bookings or fail if none.

        # Step 2: Get existing bookings for the passenger to find a booking to add seats
        bookings_resp = requests.get(
            f"{BASE_URL}/api/v1/bookings",
            headers=HEADERS,
            timeout=30,
        )
        assert bookings_resp.status_code == 200, f"Failed to get bookings: {bookings_resp.text}"
        bookings_data = bookings_resp.json()
        # bookings_data expected to be a list of bookings or dict with data?

        bookings = bookings_data if isinstance(bookings_data, list) else bookings_data.get("bookings", [])
        
        if not bookings:
            # No booking exists, create a new booking first:
            # Step 2.1: Find a ride to book seats on (get rides or fail)
            rides_resp = requests.get(
                f"{BASE_URL}/api/v1/rides",
                headers=HEADERS,
                timeout=30,
            )
            assert rides_resp.status_code == 200, f"Failed to get rides: {rides_resp.text}"
            rides_data = rides_resp.json()
            rides = rides_data if isinstance(rides_data, list) else rides_data.get("rides", [])
            assert rides, "No rides available to create booking."

            selected_ride = rides[0]
            created_ride_id = selected_ride.get("id") or selected_ride.get("ride_id")
            assert created_ride_id, "Ride ID not found in ride data."

            # Create booking with 1 seat
            booking_payload = {
                "ride_id": created_ride_id,
                "seat_count": 1
            }

            create_booking_resp = requests.post(
                f"{BASE_URL}/api/v1/bookings",
                headers=HEADERS,
                json=booking_payload,
                timeout=30,
            )
            assert create_booking_resp.status_code in (200, 201), f"Failed to create booking: {create_booking_resp.text}"
            booking_created = create_booking_resp.json()
            created_booking_id = booking_created.get("id") or booking_created.get("booking_id")
            assert created_booking_id, "Booking id not returned after creation."
            original_seat_count = booking_created.get("seat_count", 1)
        else:
            # Use first booking found
            booking = bookings[0]
            created_booking_id = booking.get("id") or booking.get("booking_id")
            assert created_booking_id, "Booking id not found."
            original_seat_count = booking.get("seat_count", 1)

        # Step 3: Add seats to existing booking
        add_seats_payload = {
            "additional_seat_count": 2
        }

        add_seats_resp = requests.post(
            f"{BASE_URL}/api/v1/bookings/{created_booking_id}/seats",
            headers=HEADERS,
            json=add_seats_payload,
            timeout=30,
        )
        assert add_seats_resp.status_code == 200, f"Failed to add seats: {add_seats_resp.text}"
        updated_booking = add_seats_resp.json()

        updated_seat_count = updated_booking.get("seat_count") or updated_booking.get("total_seats") or updated_booking.get("seats")

        assert updated_seat_count is not None, "Updated seat count not in response."
        assert updated_seat_count == original_seat_count + add_seats_payload["additional_seat_count"], \
            f"Seat count not updated correctly, expected {original_seat_count + add_seats_payload['additional_seat_count']}, got {updated_seat_count}"

        # Step 4: Verify booking detail shows updated seat count
        detail_resp = requests.get(
            f"{BASE_URL}/api/v1/bookings/{created_booking_id}",
            headers=HEADERS,
            timeout=30,
        )
        assert detail_resp.status_code == 200, f"Failed to get booking detail: {detail_resp.text}"
        detail_data = detail_resp.json()
        detail_seat_count = detail_data.get("seat_count") or detail_data.get("total_seats") or detail_data.get("seats")
        assert detail_seat_count == updated_seat_count, "Booking detail seat count does not match updated seat count."

    finally:
        # Cleanup created booking
        if created_booking_id is not None:
            requests.post(
                f"{BASE_URL}/api/v1/bookings/{created_booking_id}/cancel",
                headers=HEADERS,
                timeout=30,
            )

test_post_api_v1_bookings_booking_seats_add_seats()