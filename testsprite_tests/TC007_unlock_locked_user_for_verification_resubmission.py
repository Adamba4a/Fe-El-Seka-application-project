import requests

BASE_URL = "http://localhost:8000"
ADMIN_JWT = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
TIMEOUT = 30

def test_unlock_locked_user_for_verification_resubmission():
    headers = {
        "Authorization": f"Bearer {ADMIN_JWT}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Step 1: Get a locked user id eligible for unlock.
    # Since PRD doesn’t provide a direct API to create a locked user or get locked users,
    # we will list users and use the first user to try the unlock endpoint.
    # In a real test, you might set up a locked user as precondition.
    try:
        users_resp = requests.get(f"{BASE_URL}/api/admin/users", headers=headers, timeout=TIMEOUT)
        assert users_resp.status_code == 200, f"Failed to fetch users, status: {users_resp.status_code}"
        users = users_resp.json()
        assert isinstance(users, list) or isinstance(users.get("users"), list), "Users response is not a list or missing 'users' key"

        # Extract user_id robustly:
        if isinstance(users, list):
            user = users[0] if users else None
        else:
            user = users.get("users")[0] if users.get("users") else None

        assert user is not None, "No users found for unlock test"
        user_id = user.get("id") if isinstance(user, dict) else None
        assert user_id, "User object missing 'id'"

        # Step 2: POST unlock for that user
        unlock_url = f"{BASE_URL}/api/admin/verification/users/{user_id}/unlock"
        unlock_resp = requests.post(unlock_url, headers=headers, timeout=TIMEOUT)

        # Validate successful unlock status
        assert unlock_resp.status_code == 200, f"Unlock request failed with status {unlock_resp.status_code}"
        # Response body might be empty or contain JSON indicating success
        if unlock_resp.content:
            try:
                resp_json = unlock_resp.json()
                assert isinstance(resp_json, dict), "Unlock response JSON is not a dict"
            except Exception:
                # If not JSON, that's acceptable as long as status is 200
                pass

    except AssertionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Test failed due to an unexpected error: {e}")

test_unlock_locked_user_for_verification_resubmission()