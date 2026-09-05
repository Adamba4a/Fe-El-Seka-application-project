import requests

BASE_URL = "http://localhost:8000"
PASSENGER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI5ZTViMTZlYi0yZWRjLTQ4ZjUtOWNhMy01ZjdkM2IwZjI0MGYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjUwNzg1LCJpYXQiOjE3ODg1NjQzODUsImVtYWlsIjoidGVzdHNwcml0ZS5wYXNzZW5nZXIrNjAwNDdAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2NDM4NX1dLCJzZXNzaW9uX2lkIjoiYzY3ODRmNTEtZTRlMS00ZmYyLTg1ZDYtM2IxYjcyMGVlOWNjIiwiaXNfYW5veW1vdXMiOmZhbHNlfS5MvxYiCpc9BcMinXo0lYWMDCMu6-C9L1ZO5hEDnpxoXKMUa0LowW9NdamiYISGn86U0DjCK_s-EDkBQRSHhzZKQ"
TIMEOUT = 30

def test_post_api_v1_ratings_submit_rating():
    url = f"{BASE_URL}/api/v1/ratings"
    headers = {
        "Authorization": f"Bearer {PASSENGER_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "ride_id": "ef3e0a6a-af35-44a5-bffe-e27c36ad5729",
        "rating": 5,
        "comment": "TestSprite TC007 test rating"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request to POST /api/v1/ratings failed: {e}"

    assert response.status_code == 201, f"Expected status code 201, got {response.status_code}"
    try:
        resp_json = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Validate response references the ride_id and rating submitted
    assert "ride_id" in resp_json, "Response JSON missing 'ride_id'"
    assert resp_json["ride_id"] == payload["ride_id"], f"Response ride_id '{resp_json.get('ride_id')}' does not match submitted ride_id '{payload['ride_id']}'"
    assert "rating" in resp_json, "Response JSON missing 'rating'"
    assert resp_json["rating"] == payload["rating"], f"Response rating '{resp_json.get('rating')}' does not match submitted rating '{payload['rating']}'"

test_post_api_v1_ratings_submit_rating()
