import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"


def test_post_api_groups_groupid_domain_verification_request_otp():
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    # Step 1: Create a new open-membership group (non-sponsored)
    create_group_payload = {
        "name": "Test Sponsored Domain Verification Group",
        "description": "Group for testing domain verification OTP request",
        "is_sponsored": False
    }
    group_id = None

    try:
        # Create open-membership group
        create_resp = requests.post(
            f"{BASE_URL}/api/groups",
            json=create_group_payload,
            headers=headers,
            timeout=30
        )
        assert create_resp.status_code in (200, 201), f"Group creation failed: {create_resp.text}"
        group_data = create_resp.json()
        group_id = group_data.get("id")
        assert group_id, "No group ID returned on group creation"

        # Step 2: Upgrade this group to sponsored via admin endpoint to allow domain-verification OTP request
        # Assuming this is possible given admin role with same token, else this step would fail
        upgrade_payload = {"group_id": group_id}
        # According to PRD, admin sponsored groups can be created/upgraded via:
        # POST /api/admin/sponsored-groups with valid payload
        admin_sponsored_payload = {
            "group_id": group_id,  # May not be the exact expected payload; assumed minimal for upgrade
            "name": create_group_payload["name"],
            "description": create_group_payload["description"],
        }
        admin_sponsored_resp = requests.post(
            f"{BASE_URL}/api/admin/sponsored-groups",
            json=admin_sponsored_payload,
            headers=headers,
            timeout=30,
        )
        # Accept either 200 or 201 if upgrade is successful
        assert admin_sponsored_resp.status_code in (200, 201), f"Failed to upgrade group to sponsored: {admin_sponsored_resp.text}"

        # Step 3: Add approved domain for the sponsored group through admin domains endpoint
        approved_domain = "example.com"
        domain_payload = {"domain": approved_domain}
        domain_resp = requests.post(
            f"{BASE_URL}/api/admin/sponsored-groups/{group_id}/domains",
            json=domain_payload,
            headers=headers,
            timeout=30,
        )
        assert domain_resp.status_code == 200, f"Failed to add approved sponsor domain: {domain_resp.text}"

        # Step 4: Request OTP for domain verification for the sponsored group using allowed domain email
        otp_request_payload = {
            "email": f"tester.{group_id}@{approved_domain}"
        }
        otp_resp = requests.post(
            f"{BASE_URL}/api/groups/{group_id}/domain-verification/request",
            json=otp_request_payload,
            headers=headers,
            timeout=30,
        )
        assert otp_resp.status_code == 200, f"OTP request failed: {otp_resp.text}"
        otp_resp_data = otp_resp.json()
        # Verify the response indicates OTP delivery initiation (for example check message or status key)
        assert "message" in otp_resp_data or "status" in otp_resp_data, "OTP request response missing delivery indication"

    finally:
        # Cleanup: Delete the group created
        if group_id:
            del_resp = requests.delete(
                f"{BASE_URL}/api/groups/{group_id}",
                headers=headers,
                timeout=30,
            )
            assert del_resp.status_code == 200, f"Cleanup failed: Could not delete group {group_id}"

test_post_api_groups_groupid_domain_verification_request_otp()