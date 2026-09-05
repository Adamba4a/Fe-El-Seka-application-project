import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_post_api_admin_sponsored_groups_groupid_add_funds():
    # Step 1: Create a new sponsored group to use for this test
    sponsored_group_payload = {
        "name": "Test Sponsored Group TC010",
        "description": "Group created for testing adding sponsor funds",
        "sponsored": True
    }
    try:
        create_resp = requests.post(
            f"{BASE_URL}/api/admin/sponsored-groups",
            json=sponsored_group_payload,
            headers=HEADERS,
            timeout=30
        )
        assert create_resp.status_code in (200, 201), f"Failed to create sponsored group: {create_resp.text}"
        group_data = create_resp.json()
        group_id = group_data.get("id")
        assert group_id, "Created group ID is missing"

        # Step 2: Add sponsor funds with a positive amount
        add_funds_payload = {
            "amount": 1000.0  # positive amount for adding funds
        }
        add_funds_resp = requests.post(
            f"{BASE_URL}/api/admin/sponsored-groups/{group_id}/add-funds",
            json=add_funds_payload,
            headers=HEADERS,
            timeout=30
        )
        assert add_funds_resp.status_code == 200, f"Failed to add sponsor funds: {add_funds_resp.text}"
        added_funds_data = add_funds_resp.json()

        # Verify that the sponsor budget was updated reflected in the response
        assert "sponsor_budget" in added_funds_data or "budget" in added_funds_data, "Sponsor budget key is missing in response"
        sponsor_budget = added_funds_data.get("sponsor_budget", added_funds_data.get("budget"))
        assert isinstance(sponsor_budget, (int, float)), "Sponsor budget is not numeric"
        assert sponsor_budget >= add_funds_payload["amount"], "Sponsor budget is less than the added amount"

        # Step 3: Verify updated sponsor budget reflected in the sponsored groups list
        list_resp = requests.get(
            f"{BASE_URL}/api/admin/sponsored-groups",
            headers=HEADERS,
            timeout=30
        )
        assert list_resp.status_code == 200, f"Failed to list sponsored groups: {list_resp.text}"
        groups_list = list_resp.json()
        assert isinstance(groups_list, list), "Sponsored groups list response is not a list"

        matching_groups = [g for g in groups_list if g.get("id") == group_id]
        assert matching_groups, f"Sponsored group with id {group_id} not found in sponsored groups list"
        updated_group = matching_groups[0]

        updated_budget = updated_group.get("sponsor_budget", updated_group.get("budget"))
        assert isinstance(updated_budget, (int, float)), "Updated group sponsor budget is not numeric"
        assert updated_budget >= add_funds_payload["amount"], "Updated group sponsor budget is less than the added amount"

    finally:
        # Clean up - delete the sponsored group after test
        if 'group_id' in locals():
            try:
                del_resp = requests.delete(
                    f"{BASE_URL}/api/admin/sponsored-groups/{group_id}",
                    headers=HEADERS,
                    timeout=30
                )
                assert del_resp.status_code == 200, f"Failed to delete sponsored group in cleanup: {del_resp.text}"
            except Exception as e:
                print(f"Error during cleanup deleting sponsored group {group_id}: {e}")

test_post_api_admin_sponsored_groups_groupid_add_funds()