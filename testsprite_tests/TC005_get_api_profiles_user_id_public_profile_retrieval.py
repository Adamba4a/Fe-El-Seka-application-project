import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json"
}
TIMEOUT = 30

def test_get_user_public_profile():
    # Step 1: Get current user's own profile to obtain a valid user_id
    try:
        resp_me = requests.get(f"{BASE_URL}/api/profiles/me", headers=HEADERS, timeout=TIMEOUT)
        resp_me.raise_for_status()
        current_user = resp_me.json()
        user_id = current_user.get("id") or current_user.get("user_id")
        if not user_id:
            raise ValueError("Current user profile does not contain 'id' or 'user_id'")
    except Exception as e:
        raise AssertionError(f"Failed to get current user profile: {e}")

    # Step 2: Get the public profile of another user (using the current user id here)
    try:
        resp_public = requests.get(f"{BASE_URL}/api/profiles/{user_id}/public", headers=HEADERS, timeout=TIMEOUT)
        resp_public.raise_for_status()
        public_profile = resp_public.json()

        # Validate response fields - assuming typical public profile fields present
        assert isinstance(public_profile, dict), "Public profile response is not a dictionary"
        # We expect some public profile fields like display_name or role or email as per product overview
        assert any(k in public_profile for k in ("display_name", "role", "email", "id")), "Public profile missing expected keys"

    except Exception as e:
        raise AssertionError(f"Failed to retrieve public profile for existing user_id {user_id}: {e}")

    # Step 3: Try to get public profile for a nonexistent user_id and expect 404 or error
    fake_user_id = "00000000-0000-0000-0000-000000000000"
    try:
        resp_fake = requests.get(f"{BASE_URL}/api/profiles/{fake_user_id}/public", headers=HEADERS, timeout=TIMEOUT)
        if resp_fake.status_code == 404:
            # Expected for nonexistent user
            return
        else:
            # If not 404, maybe another error or success, validate and fail if success
            try:
                resp_fake.raise_for_status()
            except requests.HTTPError:
                # Some other error code, acceptable as well
                return
            # If here, means 2xx response returned for fake user_id - fail test
            raise AssertionError(f"Expected 404 for nonexistent user_id but got {resp_fake.status_code}")
    except requests.HTTPError:
        # Consider any HTTP error other than success as expected behavior
        return
    except Exception as e:
        # Any other error considered as failure
        raise AssertionError(f"Unexpected error when requesting nonexistent user's public profile: {e}")

test_get_user_public_profile()