import requests

BASE_URL = "http://localhost:8000"
PASSENGER_TOKEN = (
    "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI5ZTViMTZlYi0yZWRjLTQ4ZjUtOWNhMy01ZjdkM2IwZjI0MGYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjUwNzg1LCJpYXQiOjE3ODg1NjQzODUsImVtYWlsIjoidGVzdHNwcml0ZS5wYXNzZW5nZXIrNjAwNDdAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2NDM4NX1dLCJzZXNzaW9uX2lkIjoiYzY3ODRmNTEtZTRlMS00ZmYyLTg1ZDYtM2IxYjcyMGVlOWNjIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.LvxYiCpc9BcMinXo0lYWMDCMu6-C9L1ZO5hEDnpxoXKMUa0LowW9NdamiYISGn86U0DjCK_s-EDkBQRSHhzZKQ"
)

HEADERS = {
    "Authorization": f"Bearer {PASSENGER_TOKEN}",
    "Content-Type": "application/json",
}

def test_post_api_v1_bookings_add_seats():
    booking_id = None
    ride_id = "3402c799-2a12-42de-9147-adfe11cb586f"
    create_booking_url = f"{BASE_URL}/api/v1/bookings"
    add_seats_url_template = f"{BASE_URL}/api/v1/bookings/{{booking_id}}/seats"
    get_booking_url_template = f"{BASE_URL}/api/v1/bookings/{{booking_id}}"

    # Booking creation payload as per PRD
    booking_payload = {
        "ride_id": ride_id,
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

    try:
        # Create a new booking (seats=1)
        create_resp = requests.post(create_booking_url, headers=HEADERS, json=booking_payload, timeout=30)
        assert create_resp.status_code == 201, f"Booking creation failed with status {create_resp.status_code}"
        create_data = create_resp.json()
        assert "booking_id" in create_data, "booking_id not in booking creation response"
        booking_id = create_data["booking_id"]

        # Confirm initial seats count is 1 by fetching booking detail
        get_resp = requests.get(get_booking_url_template.format(booking_id=booking_id), headers=HEADERS, timeout=30)
        assert get_resp.status_code == 200, f"Failed to fetch booking details, status {get_resp.status_code}"
        booking_detail = get_resp.json()
        assert "seats" in booking_detail, "seats field missing from booking detail"
        initial_seats = booking_detail["seats"]
        assert initial_seats == 1, f"Initial seats expected 1, got {initial_seats}"

        # Try increasing seats by sending seats=2 (total desired seats)
        add_seats_url = add_seats_url_template.format(booking_id=booking_id)
        add_seats_payload = {"seats": 2}
        add_resp = requests.post(add_seats_url, headers=HEADERS, json=add_seats_payload, timeout=30)

        if add_resp.status_code == 422:
            # Fallback if seats=2 is invalid, try additional_seats=1
            add_seats_payload = {"additional_seats": 1}
            add_resp = requests.post(add_seats_url, headers=HEADERS, json=add_seats_payload, timeout=30)

        assert add_resp.status_code == 200, f"Add seats request failed with status {add_resp.status_code}"
        updated_data = add_resp.json()
        assert "seats" in updated_data, "seats field missing from add seats response"

        updated_seats = updated_data["seats"]
        # Because original was 1, and we tried to add 1 more, seats should be 2
        # If payload was seats=2 (total seats), seats should be 2 as well
        assert updated_seats > initial_seats, f"Seats count not increased, was {initial_seats}, now {updated_seats}"

    finally:
        # Cleanup - delete the booking to not pollute environment
        if booking_id:
            delete_url = f"{BASE_URL}/api/v1/bookings/{booking_id}"
            try:
                requests.delete(delete_url, headers=HEADERS, timeout=30)
            except Exception:
                # Best effort cleanup; ignore errors
                pass

test_post_api_v1_bookings_add_seats()