import requests

BASE_URL = "http://localhost:8000"
PASSENGER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI5ZTViMTZlYi0yZWRjLTQ4ZjUtOWNhMy01ZjdkM2IwZjI0MGYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjUwNzg1LCJpYXQiOjE3ODg1NjQzODUsImVtYWlsIjoidGVzdHNwcml0ZS5wYXNzZW5nZXIrNjAwNDdAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2NDM4NX1dLCJzZXNzaW9uX2lkIjoiYzY3ODRmNTEtZTRlMS00ZmYyLTg1ZDYtM2IxYjcyMGVlOWNjIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.LvxYiCpc9BcMinXo0lYWMDCMu6-C9L1ZO5hEDnpxoXKMUa0LowW9NdamiYISGn86U0DjCK_s-EDkBQRSHhzZKQ"
TIMEOUT = 30

def test_post_api_v1_bookings_cancel():
    headers = {
        "Authorization": f"Bearer {PASSENGER_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    booking_id = None

    try:
        # Step 1: Create a new booking (seats=1) on ride_id "625ffbb9-89f4-449c-87a5-3ae9261d5c9d"
        create_payload = {
            "ride_id": "625ffbb9-89f4-449c-87a5-3ae9261d5c9d",
            "seats": 1,
            "boarding_point": {
                "lat": 30.0444,
                "lng": 31.2357,
                "address": "Tahrir Square, Cairo"
            },
            "alighting_point": {
                "lat": 30.0131,
                "lng": 31.2089,
                "address": "Ramses Station, Cairo"
            }
        }
        create_response = requests.post(
            f"{BASE_URL}/api/v1/bookings",
            headers=headers,
            json=create_payload,
            timeout=TIMEOUT
        )
        assert create_response.status_code == 201, f"Expected 201 on booking creation, got {create_response.status_code}"
        create_data = create_response.json()
        assert "booking_id" in create_data, "Response missing booking_id"
        booking_id = create_data["booking_id"]

        # Step 2: Cancel the booking with POST /api/v1/bookings/{booking_id}/cancel
        cancel_response = requests.post(
            f"{BASE_URL}/api/v1/bookings/{booking_id}/cancel",
            headers=headers,
            timeout=TIMEOUT
        )
        assert cancel_response.status_code == 200, f"Expected 200 on booking cancel, got {cancel_response.status_code}"
        cancel_data = cancel_response.json()

        # Assert the booking status is cancelled (status field is 'cancelled' or equivalent)
        status = cancel_data.get("status")
        assert status is not None, "Cancel response missing status field"
        assert status.lower() == "cancelled", f"Expected booking status to be 'cancelled', got '{status}'"

    finally:
        # Clean up: Delete the booking by cancelling it if not already cancelled, or ignore if already cancelled
        if booking_id is not None:
            # Try cancelling again to ensure cleanup, ignore any errors
            try:
                requests.post(
                    f"{BASE_URL}/api/v1/bookings/{booking_id}/cancel",
                    headers=headers,
                    timeout=TIMEOUT
                )
            except Exception:
                pass

test_post_api_v1_bookings_cancel()