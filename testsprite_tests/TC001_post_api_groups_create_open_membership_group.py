import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def test_post_api_groups_create_open_membership_group():
    url = f"{BASE_URL}/api/groups"
    payload = {
        "name": "Test Open Membership Group",
        "description": "This is a test open-membership group created by automated test.",
        "is_sponsored": False  # Assuming API distinguishes sponsored vs open by a flag or absence
    }

    try:
        # Create a new open-membership group
        response = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        assert response.status_code in (200, 201), f"Unexpected status code {response.status_code}, response: {response.text}"
        data = response.json()

        # Validate the response contains the new group details
        assert "id" in data and isinstance(data["id"], (int, str)), "Response missing valid 'id'"
        assert data.get("name") == payload["name"], f"Response 'name' does not match payload"
        assert not data.get("is_sponsored", True), "Group is unexpectedly sponsored"
        assert "description" in data and data["description"] == payload["description"], "Group description mismatch"

    finally:
        # Cleanup: delete the created group if created
        if 'data' in locals() and "id" in data:
            group_id = data["id"]
            delete_url = f"{BASE_URL}/api/groups/{group_id}"
            try:
                del_resp = requests.delete(delete_url, headers=HEADERS, timeout=30)
                assert del_resp.status_code == 200, f"Failed to delete group {group_id}, status: {del_resp.status_code}"
            except Exception as e:
                # Log the cleanup failure, but do not raise to not mask the original test result
                print(f"Warning: Cleanup deletion of group {group_id} failed: {e}")

test_post_api_groups_create_open_membership_group()