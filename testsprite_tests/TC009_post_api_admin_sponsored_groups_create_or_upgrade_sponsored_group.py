import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}


def test_post_api_admin_sponsored_groups_create_or_upgrade_sponsored_group():
    url = f"{BASE_URL}/api/admin/sponsored-groups"

    # Payload to create a new sponsored group
    payload = {
        "name": "Test Sponsored Group TC009",
        "description": "This is a test sponsored group created by TC009 automated test.",
        "sponsorship_state": "sponsored"
    }

    created_group_id = None
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        assert response.status_code in (200, 201), f"Expected 200 or 201, got {response.status_code}"

        data = response.json()
        assert "id" in data, "Response missing group ID"
        assert data.get("name") == payload["name"], "Group name mismatch"
        # Sponsorship state expected to be sponsored or equivalent indicator
        # Validate presence or status that confirms sponsorship
        sponsorship_state = data.get("sponsorship_state") or data.get("status") or data.get("is_sponsored")
        assert sponsorship_state in ("sponsored", True, "active"), f"Unexpected sponsorship state: {sponsorship_state}"

        created_group_id = data["id"]
    finally:
        # Cleanup created sponsored group if it was created
        if created_group_id:
            del_url = f"{BASE_URL}/api/admin/sponsored-groups/{created_group_id}"
            try:
                del_resp = requests.delete(del_url, headers=HEADERS, timeout=30)
                assert del_resp.status_code == 200, f"Failed to delete group {created_group_id}"
            except Exception:
                pass


test_post_api_admin_sponsored_groups_create_or_upgrade_sponsored_group()