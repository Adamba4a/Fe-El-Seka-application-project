import requests
import uuid

BASE_URL = "http://localhost:8000"
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
NON_ADMIN_TOKEN = ADMIN_TOKEN  # As per the PRD note, same token simulates non-admin for checking forbidden

HEADERS_ADMIN = {
    "Authorization": f"Bearer {ADMIN_TOKEN}",
    "Content-Type": "application/json",
}

HEADERS_NON_ADMIN = {
    "Authorization": f"Bearer {NON_ADMIN_TOKEN}",
    "Content-Type": "application/json",
}

TIMEOUT = 30

def create_test_user():
    url = f"{BASE_URL}/api/admin/users"
    try:
        resp = requests.get(url, headers=HEADERS_ADMIN, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        # If data is a list, check if it has user dicts with 'id'
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and 'id' in data[0]:
            return data[0]['id']

        # If data is a dict, try keys to find list
        if isinstance(data, dict):
            for key in ['users', 'data', 'items']:
                if key in data and isinstance(data[key], list) and len(data[key]) > 0 and 'id' in data[key][0]:
                    return data[key][0]['id']

    except Exception:
        pass
    raise RuntimeError("Cannot find an existing user via GET /api/admin/users to run the test.")

def test_suspend_and_reinstate_user_account():
    user_id = None
    try:
        user_id = create_test_user()
        suspend_url = f"{BASE_URL}/api/admin/users/{user_id}/suspend"
        reinstate_url = f"{BASE_URL}/api/admin/users/{user_id}/reinstate"

        # Suspend user with valid admin JWT
        suspend_resp = requests.post(suspend_url, headers=HEADERS_ADMIN, timeout=TIMEOUT)
        assert suspend_resp.status_code == 200, f"Expected 200 on suspend with admin token, got {suspend_resp.status_code}"

        # Suspend user with non-admin JWT (should be forbidden 403)
        suspend_resp_non_admin = requests.post(suspend_url, headers=HEADERS_NON_ADMIN, timeout=TIMEOUT)
        assert suspend_resp_non_admin.status_code == 403, f"Expected 403 on suspend with non-admin token, got {suspend_resp_non_admin.status_code}"

        # Reinstate suspended user with valid admin JWT
        reinstate_resp = requests.post(reinstate_url, headers=HEADERS_ADMIN, timeout=TIMEOUT)
        assert reinstate_resp.status_code == 200, f"Expected 200 on reinstate with admin token, got {reinstate_resp.status_code}"

    finally:
        # Cleanup: try to reinstate user if suspended to leave user in normal state
        if user_id:
            try:
                requests.post(f"{BASE_URL}/api/admin/users/{user_id}/reinstate", headers=HEADERS_ADMIN, timeout=TIMEOUT)
            except Exception:
                pass

test_suspend_and_reinstate_user_account()
