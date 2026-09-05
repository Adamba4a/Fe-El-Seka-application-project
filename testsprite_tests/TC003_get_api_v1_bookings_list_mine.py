import requests

BASE_URL = "http://localhost:8000"
PASSENGER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI5ZTViMTZlYi0yZWRjLTQ4ZjUtOWNhMy01ZjdkM2IwZjI0MGYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjUwNzg1LCJpYXQiOjE3ODg1NjQzODUsImVtYWlsIjoidGVzdHNwcml0ZS5wYXNzZW5nZXIrNjAwNDdAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2NDM4NX1dLCJzZXNzaW9uX2lkIjoiYzY3ODRmNTEtZTRlMS00ZmYyLTg1ZDYtM2IxYjcyMGVlOWNjIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.LvxYiCpc9BcMinXo0lYWMDCMu6-C9L1ZO5hEDnpxoXKMUa0LowW9NdamiYISGn86U0DjCK_s-EDkBQRSHhzZKQ"

def test_get_api_v1_bookings_list_mine():
    url = f"{BASE_URL}/api/v1/bookings"
    headers = {
        "Authorization": f"Bearer {PASSENGER_TOKEN}",
        "Accept": "application/json",
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    assert response.status_code == 200, f"Expected status 200 but got {response.status_code}"

    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # The response should be a list or contain a list of bookings.
    # Accept if data itself is a list, or if any top-level value is a list that is non-empty and looks like bookings.
    if isinstance(data, list):
        bookings_list = data
    elif isinstance(data, dict):
        # Try to find a list at any top-level key
        lists_found = [v for v in data.values() if isinstance(v, list)]
        assert lists_found, "Response JSON dict does not contain a list value"
        bookings_list = lists_found[0]
    else:
        assert False, "Response JSON is neither a list nor a dict"

    assert isinstance(bookings_list, list), "Bookings list is not a list"

    # Optional: Assert each item is a dict with keys typical for bookings e.g. booking_id, ride_id, status, etc.
    if bookings_list:
        first = bookings_list[0]
        assert isinstance(first, dict), "Booking entry is not a dict"
        assert "booking_id" in first, "Booking entry does not have a 'booking_id' field"
        assert "ride_id" in first, "Booking entry does not have a 'ride_id' field"
        assert "status" in first, "Booking entry does not have a 'status' field"

test_get_api_v1_bookings_list_mine()