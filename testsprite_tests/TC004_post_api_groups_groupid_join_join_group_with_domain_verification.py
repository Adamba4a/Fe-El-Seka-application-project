import requests
import time

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTAifQ=="

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
TIMEOUT = 30

def test_post_api_groups_join_with_domain_verification():
    group_id = None
    verified_email = "testsprite.drive+4f241358@example.com"

    try:
        # Create a new open-membership group (POST /api/groups)
        payload_create_group = {
            "name": "Test Sponsored Group",
            "description": "An open group for joining test"
        }
        create_resp = requests.post(f"{BASE_URL}/api/groups", headers=HEADERS, json=payload_create_group, timeout=TIMEOUT)
        assert create_resp.status_code in (200,201), f"Failed to create group: {create_resp.text}"
        group = create_resp.json()
        group_id = group.get("id")
        assert group_id, "Created group does not have an id"

        # For open-membership group, joining does not require domain verification
        join_resp = requests.post(f"{BASE_URL}/api/groups/{group_id}/join", headers=HEADERS, timeout=TIMEOUT)
        assert join_resp.status_code == 200, f"Failed to join group: {join_resp.text}"

        join_data = join_resp.json()
        # The response should indicate membership confirmation
        assert "membership" in join_data or "group_id" in join_data, "Join response does not confirm membership"

        # Verify the user is now a member by fetching group members (GET /api/groups/{group_id}/members)
        members_resp = requests.get(f"{BASE_URL}/api/groups/{group_id}/members", headers=HEADERS, timeout=TIMEOUT)
        assert members_resp.status_code == 200, f"Failed to get group members: {members_resp.text}"
        members = members_resp.json()
        assert isinstance(members, list), "Members response is not a list"
        user_email_found = any(m.get("email", "").lower() == verified_email.lower() for m in members)
        assert user_email_found, "User email not found in group members after joining"

    finally:
        # Cleanup: Leave the group and delete it if possible
        if group_id:
            # Leave the group (POST /api/groups/{group_id}/leave)
            try:
                leave_resp = requests.post(f"{BASE_URL}/api/groups/{group_id}/leave", headers=HEADERS, timeout=TIMEOUT)
                assert leave_resp.status_code == 200, f"Failed to leave group during cleanup: {leave_resp.text}"
            except Exception:
                pass
            # Delete group (DELETE /api/groups/{group_id})
            try:
                del_resp = requests.delete(f"{BASE_URL}/api/groups/{group_id}", headers=HEADERS, timeout=TIMEOUT)
                if del_resp.status_code not in (200, 204, 404):
                    raise AssertionError(f"Delete group failed in cleanup: {del_resp.status_code} {del_resp.text}")
            except Exception:
                pass

test_post_api_groups_join_with_domain_verification()
