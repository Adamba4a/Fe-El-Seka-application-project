import requests
import time

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnymb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_post_api_groups_groupid_transfer_ownership():
    # Create a new open-membership group to test on
    create_group_payload = {
        "name": f"TestGroup-{int(time.time())}",
        "description": "A test group for ownership transfer",
        "is_sponsored": False
    }

    timeout = 30
    group_id = None
    try:
        # Create group
        r = requests.post(
            f"{BASE_URL}/api/groups",
            json=create_group_payload,
            headers=HEADERS,
            timeout=timeout
        )
        assert r.status_code in (200, 201), f"Failed to create group: {r.text}"
        group = r.json()
        group_id = group.get("id")
        assert group_id is not None, "Group ID not returned on creation"

        # Fetch members of the group to identify at least two members (owner and member)
        r = requests.get(
            f"{BASE_URL}/api/groups/{group_id}/members",
            headers=HEADERS,
            timeout=timeout
        )
        assert r.status_code == 200, f"Failed to get members: {r.text}"
        members = r.json()
        assert isinstance(members, list) and len(members) >= 1, "Members list empty"

        # At creation group owner should be the authenticated user, members list must contain owner at minimum
        owner_id = None
        for m in members:
            if m.get("role") == "owner":
                owner_id = m.get("user_id")
                break
        assert owner_id is not None, "Owner user_id not found in members"

        # Need to find another member (different from owner) to transfer ownership to.
        # If no other member exists, create one by inviting another user to join the group.
        # Since no user_id for other users is provided, we simulate by creating a second user via joining.

        # Try to invite another user - but as no provision to add other users, this is a limitation.
        # Instead, join the authenticated user again will not help.
        # So, for this test, we create a new user by temporary an alternate token or assume members >1.

        # If only one member (owner), we create a new member by joining the group.
        if len(members) < 2:
            # Join self to group again to simulate second member
            # But this likely will return error or no effect,
            # So we opt to check members again periodically for added other members
            # We'll just raise an error to indicate cannot transfer ownership without another member.
            raise AssertionError("Insufficient members in the group to transfer ownership")

        # Pick a member other than owner to transfer ownership
        new_owner = None
        for m in members:
            if m.get("user_id") != owner_id:
                new_owner = m
                break
        assert new_owner is not None, "No alternative member found to transfer ownership to"
        new_owner_id = new_owner.get("user_id")
        assert new_owner_id is not None, "New owner user_id is None"

        # Transfer ownership to new member
        r = requests.post(
            f"{BASE_URL}/api/groups/{group_id}/transfer-ownership",
            json={"new_owner_user_id": new_owner_id},
            headers=HEADERS,
            timeout=timeout
        )
        assert r.status_code == 200, f"Ownership transfer failed: {r.text}"
        transfer_resp = r.json()

        # Validate response contains updated owner info
        assert transfer_resp.get("owner_id") == new_owner_id or transfer_resp.get("owner").get("user_id") == new_owner_id, "Response does not confirm new ownership"

        # Get the group detail and confirm ownership updated
        r = requests.get(
            f"{BASE_URL}/api/groups/{group_id}",
            headers=HEADERS,
            timeout=timeout
        )
        assert r.status_code == 200, f"Failed to get group detail after ownership transfer: {r.text}"
        group_detail = r.json()
        # The owner id or owner user_id should be updated to new_owner_id
        # The key may vary so we check common patterns
        group_owner_id = None
        if "owner_id" in group_detail:
            group_owner_id = group_detail["owner_id"]
        elif "owner" in group_detail and isinstance(group_detail["owner"], dict):
            group_owner_id = group_detail["owner"].get("user_id") or group_detail["owner"].get("id")
        assert group_owner_id == new_owner_id, "Group owner not updated to new owner"

    finally:
        # Cleanup: delete the group if created
        if group_id:
            try:
                r = requests.delete(
                    f"{BASE_URL}/api/groups/{group_id}",
                    headers=HEADERS,
                    timeout=timeout
                )
                # Deletion might return 200 or 204; ignore errors here
            except Exception:
                pass


test_post_api_groups_groupid_transfer_ownership()