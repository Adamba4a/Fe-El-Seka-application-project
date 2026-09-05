import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def test_post_reinstate_user_with_admin_auth():
    session = requests.Session()
    session.headers.update(HEADERS)
    timeout = 30

    try:
        # Step 1: Get flagged users to find a user_id to reinstate
        flagged_url = f"{BASE_URL}/api/admin/moderation/flagged"
        flagged_resp = session.get(flagged_url, timeout=timeout)
        assert flagged_resp.status_code == 200, f"Failed to get flagged users, status: {flagged_resp.status_code}"
        flagged_data = flagged_resp.json()
        assert isinstance(flagged_data, list), "Flagged users response is not a list"

        if not flagged_data:
            raise ValueError("No flagged users available to reinstate")

        user_id = flagged_data[0].get("user_id") or flagged_data[0].get("id")
        assert user_id, "No user_id found in flagged user data"

        # Step 2: Post to reinstate the user
        reinstate_url = f"{BASE_URL}/api/admin/moderation/users/{user_id}/reinstate"
        reinstate_resp = session.post(reinstate_url, timeout=timeout)
        assert reinstate_resp.status_code == 200, f"Failed to reinstate user {user_id}, status: {reinstate_resp.status_code}"

        reinstate_json = reinstate_resp.json()
        assert ("reinstated" in reinstate_json and reinstate_json["reinstated"] is True) or (
            "message" in reinstate_json and "reinstated" in reinstate_json["message"].lower()
        ), "Response does not confirm reinstatement"
    finally:
        session.close()

test_post_reinstate_user_with_admin_auth()