import requests

BASE_URL = "http://localhost:8000"
PASSENGER_TOKEN = (
    "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI5ZTViMTZlYi0yZWRjLTQ4ZjUtOWNhMy01Zjdk"
    "M2IwZjI0MGYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjUwNzg1LCJpYXQiOjE3ODg1NjQzODUsImVtYWlsIjoid"
    "GVzdHNwcml0ZS5wYXNzZW5nZXIrNjAwNDdAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlc"
    "iI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm"
    "9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc"
    "4ODU2NDM4NX1dLCJzZXNzaW9uX2lkIjoiYzY3ODRmNTEtZTRlMS00ZmYyLTg1ZDYtM2IxYjcyMGVlOWNjIiwiaXNfYW5vbnltb3Vz"
    "IjpmYWxzZX0.LvxYiCpc9BcMinXo0lYWMDCMu6-C9L1ZO5hEDnpxoXKMUa0LowW9NdamiYISGn86U0DjCK_s-EDkBQRSHhzZKQ"
)

def test_get_api_v1_bookings_detail():
    booking_id = "b2f23396-5a55-41a6-b514-a4cfe64a103a"
    url = f"{BASE_URL}/api/v1/bookings/{booking_id}"
    headers = {
        "Authorization": f"Bearer {PASSENGER_TOKEN}",
        "Accept": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Assert presence and correctness of key booking detail fields
    assert "booking_id" in data, "Response missing 'booking_id' field"
    assert data["booking_id"] == booking_id, "Returned booking_id does not match requested booking_id"
    assert "ride_id" in data and isinstance(data["ride_id"], str) and data["ride_id"], "Response missing or invalid 'ride_id'"
    assert "status" in data and isinstance(data["status"], str) and data["status"], "Response missing or invalid 'status'"
    assert "seats" in data and isinstance(data["seats"], int) and data["seats"] > 0, "Response missing or invalid 'seats'"

test_get_api_v1_bookings_detail()