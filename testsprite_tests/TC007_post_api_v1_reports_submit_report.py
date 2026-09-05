import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vb255bW91cyI6ZmFsc2V9.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}
TIMEOUT = 30


def test_post_api_v1_reports_submit_report():
    # From the error we see required fields: ride_id, booking_id, reported_user_id, category, description
    # We use dummy UUIDs for ride_id and booking_id, and the token subject as reported_user_id
    target_user_id = "2b61b48e-1ec2-4cb3-b2c1-750d0f563bd6"
    dummy_ride_id = "11111111-1111-1111-1111-111111111111"
    dummy_booking_id = "22222222-2222-2222-2222-222222222222"

    payload = {
        "ride_id": dummy_ride_id,
        "booking_id": dummy_booking_id,
        "reported_user_id": target_user_id,
        "category": "fraud_or_scam",
        "description": "Suspicious behavior reported during ride."
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/reports",
        headers=HEADERS,
        json=payload,
        timeout=TIMEOUT
    )

    # Assert the response is 200 or 201 (success creation)
    assert response.status_code in (200, 201), f"Expected 200 or 201, got {response.status_code}, response: {response.text}"

    # Assert response body has an id or confirmation of report creation
    response_json = response.json()
    assert "id" in response_json or "report_id" in response_json or "created_at" in response_json, \
        f"Response JSON missing expected report confirmation fields: {response_json}"

    # Optionally validate returned reported_user_id matches target_user_id or similar
    if "reported_user_id" in response_json:
        assert response_json["reported_user_id"] == target_user_id, "Returned reported_user_id does not match"


test_post_api_v1_reports_submit_report()
