import requests

BASE_URL = "http://localhost:8000"
ADMIN_JWT = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

def test_list_pending_verification_submissions():
    url = f"{BASE_URL}/api/admin/verification/queue"
    headers_with_auth = {
        "Authorization": f"Bearer {ADMIN_JWT}",
        "Accept": "application/json",
    }
    headers_without_auth = {
        "Accept": "application/json",
    }

    # Test with valid admin JWT
    try:
        response = requests.get(url, headers=headers_with_auth, timeout=30)
        assert response.status_code == 200, f"Expected 200 OK but got {response.status_code}"
        json_resp = response.json()
        assert isinstance(json_resp, list), "Expected response to be a list"
    except Exception as e:
        raise AssertionError(f"Failed with admin JWT: {e}")

    # Test without admin auth (no Authorization header)
    try:
        response_no_auth = requests.get(url, headers=headers_without_auth, timeout=30)
        assert response_no_auth.status_code == 403, f"Expected 403 Forbidden but got {response_no_auth.status_code}"
    except Exception as e:
        raise AssertionError(f"Failed without admin JWT: {e}")

test_list_pending_verification_submissions()