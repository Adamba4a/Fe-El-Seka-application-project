import requests

BASE_URL = "http://localhost:8000"
ADMIN_JWT = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
TIMEOUT = 30

def test_list_and_search_users():
    url = f"{BASE_URL}/api/admin/users"
    headers_with_auth = {
        "Authorization": f"Bearer {ADMIN_JWT}",
        "Accept": "application/json"
    }
    headers_without_auth = {
        "Accept": "application/json"
    }

    # Test 1: With valid admin JWT - expect 200 and a searchable list of users
    try:
        resp = requests.get(url, headers=headers_with_auth, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request with admin JWT failed: {e}"
    assert resp.status_code == 200, f"Expected 200 with admin JWT, got {resp.status_code}"
    try:
        data = resp.json()
    except Exception:
        assert False, "Response is not valid JSON"
    assert isinstance(data, dict) or isinstance(data, list), "Response JSON should be a dict or list"
    # If the API returns a list or dict with users, it should be searchable (contain some keys)
    if isinstance(data, dict):
        assert "users" in data or len(data) > 0, "Response JSON dict should contain users or be non-empty"
    elif isinstance(data, list):
        # If list, expect zero or more user records (dicts)
        if len(data) > 0:
            assert isinstance(data[0], dict), "User list items should be dicts"

    # Test 2: Without authorization - expect 403 Forbidden
    try:
        resp_no_auth = requests.get(url, headers=headers_without_auth, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request without auth failed: {e}"
    assert resp_no_auth.status_code == 403, f"Expected 403 without admin JWT, got {resp_no_auth.status_code}"

test_list_and_search_users()