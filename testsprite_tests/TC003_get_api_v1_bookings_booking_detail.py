import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}
TIMEOUT = 30

def test_get_api_v1_bookings_booking_detail():
    # Step 1: Create a new booking to get a valid booking_id
    # For that, we first need to find a valid ride_id by listing bookings or rides.
    # Since ride creation is unreliable locally (503) and no ride_id given, we try to get existing bookings or fail gracefully.
    # If no booking exists, we skip test as we can't proceed.
    # So first: list bookings for authenticated user to get existing booking_id (preferred to avoid creating dependency on rides).
    
    list_bookings_url = f"{BASE_URL}/api/v1/bookings"
    try:
        response = requests.get(list_bookings_url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        bookings_data = response.json()
        # bookings_data expected to be a list or dict with bookings list
        if isinstance(bookings_data, dict):
            # In case of dict with list inside
            bookings = bookings_data.get("data") or bookings_data.get("bookings") or []
        elif isinstance(bookings_data, list):
            bookings = bookings_data
        else:
            bookings = []
    except (requests.RequestException, ValueError) as e:
        # Cannot get bookings list, fail test
        assert False, f"Failed to list bookings to obtain booking_id: {str(e)}"
    
    if not bookings:
        # No existing booking found, try to create a booking by finding a ride_id from booking creation endpoint, but ride creation unreliable, so skip test.
        assert False, "No existing bookings found for authenticated user; cannot retrieve booking detail without a booking_id."
    
    # Use the first booking's id
    booking_id = None
    if isinstance(bookings, list):
        first_booking = bookings[0]
    elif isinstance(bookings, dict):
        # fallback for dict booking
        first_booking = bookings
    else:
        assert False, "Unexpected bookings format"
    
    if isinstance(first_booking, dict) and "id" in first_booking:
        booking_id = first_booking["id"]
    elif isinstance(first_booking, dict) and "booking_id" in first_booking:
        booking_id = first_booking["booking_id"]
    else:
        # Try to get first key with an id like key
        booking_id = None
    
    assert booking_id, "Booking ID not found in the first booking item."
    
    # Step 2: Retrieve booking details by booking_id
    booking_detail_url = f"{BASE_URL}/api/v1/bookings/{booking_id}"
    try:
        detail_response = requests.get(booking_detail_url, headers=HEADERS, timeout=TIMEOUT)
        detail_response.raise_for_status()
        detail_json = detail_response.json()
    except requests.HTTPError as http_err:
        assert False, f"HTTP error on getting booking detail: {http_err}"
    except requests.RequestException as req_err:
        assert False, f"Request error on getting booking detail: {req_err}"
    except ValueError as json_err:
        assert False, f"Invalid JSON response on getting booking detail: {json_err}"
    
    # Step 3: Validate response contents
    
    # response should include booking details including the booking_id used
    assert isinstance(detail_json, dict), "Booking detail response is not a JSON object"
    
    # Check booking id in response
    detail_id = detail_json.get("id") or detail_json.get("booking_id")
    assert detail_id is not None, "Booking detail response missing booking id"
    assert str(detail_id) == str(booking_id), f"Response booking id {detail_id} does not match requested id {booking_id}"
    
    # Additional checks (optional, assuming keys from booking list)
    # For example: check that status or seats keys exist
    # If available in detail_json, validate types and values
    # We can check for keys like 'status', 'ride_id', 'seat_count', 'created_at' for general sanity
    
    expected_keys = ["id", "status", "ride_id", "seat_count", "created_at"]
    for key in expected_keys:
        assert key in detail_json, f"Expected key '{key}' missing in booking detail response"
    
    # Assert status field is string and seat_count is int
    status = detail_json.get("status")
    seat_count = detail_json.get("seat_count")
    assert isinstance(status, str), "Booking status is not a string"
    assert isinstance(seat_count, int), "Booking seat_count is not an integer"


test_get_api_v1_bookings_booking_detail()