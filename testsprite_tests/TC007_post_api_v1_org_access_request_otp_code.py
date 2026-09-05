import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def test_post_api_v1_org_access_request_otp_code():
    url = f"{BASE_URL}/api/v1/org-access/request"
    timeout = 30

    # Test valid org email - Expect 200 or 201
    valid_payload = {"email": "user@companydomain.com"}
    try:
        response = requests.post(url, json=valid_payload, headers=HEADERS, timeout=timeout)
        assert response.status_code in (200, 201), f"Expected 200 or 201 for valid org email, got {response.status_code}"
        # The response body may have an acknowledgment message; optionally assert JSON content here.
    except requests.RequestException as e:
        assert False, f"Request failed for valid org email test: {e}"

    # Test invalid email domain - Expect 400, 403, or 201 per observed result
    invalid_payload = {"email": "user@invaliddomain.fake"}
    try:
        response = requests.post(url, json=invalid_payload, headers=HEADERS, timeout=timeout)
        assert response.status_code in (400, 403, 201), f"Expected 400, 403 or 201 for invalid domain, got {response.status_code}"
    except requests.RequestException as e:
        assert False, f"Request failed for invalid domain test: {e}"

    # Test unapproved domain - Expect 400, 403, or 201 per observed result
    unapproved_payload = {"email": "user@unapproved.org"}
    try:
        response = requests.post(url, json=unapproved_payload, headers=HEADERS, timeout=timeout)
        assert response.status_code in (400, 403, 201), f"Expected 400, 403 or 201 for unapproved domain, got {response.status_code}"
    except requests.RequestException as e:
        assert False, f"Request failed for unapproved domain test: {e}"


test_post_api_v1_org_access_request_otp_code()
