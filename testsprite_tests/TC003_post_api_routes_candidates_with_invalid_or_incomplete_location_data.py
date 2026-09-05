import requests

def test_post_api_routes_candidates_with_invalid_or_incomplete_location_data():
    base_url = "http://localhost:8000"
    url = f"{base_url}/api/routes/candidates"
    headers = {
        "Authorization": "Bearer eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw",
        "Content-Type": "application/json"
    }

    invalid_payloads = [
        {},  # completely empty payload
        {"origin": {}},  # origin present but incomplete
        {"destination": {}},  # destination present but incomplete
        {"origin": {"lat": "not_a_number", "lng": 31.2357}, "destination": {"lat": 30.033, "lng": 31.233}},  # invalid lat type
        {"origin": {"lat": 30.033}, "destination": {"lat": 30.033, "lng": 31.233}},  # origin missing lng
        {"origin": {"lat": 30.033, "lng": 31.2357}, "destination": {"lng": 31.233}},  # destination missing lat
        {"origin": {"lat": 30.033, "lng": 31.2357}, "destination": {"lat": None, "lng": 31.233}},  # destination lat null
        {"origin": {"lat": 30.033, "lng": None}, "destination": {"lat": 30.033, "lng": 31.233}},  # origin lng null
    ]

    for payload in invalid_payloads:
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
        except requests.RequestException as e:
            assert False, f"Request failed: {e}"
        assert response.status_code >= 400 and response.status_code < 500, (
            f"Payload: {payload} - Expected 4xx status code but got {response.status_code}"
        )

test_post_api_routes_candidates_with_invalid_or_incomplete_location_data()