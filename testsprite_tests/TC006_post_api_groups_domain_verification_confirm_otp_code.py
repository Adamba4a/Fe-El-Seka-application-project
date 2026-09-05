import requests

BASE_URL = "http://localhost:8000"
# User token (regular authenticated user)
USER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
# Admin token (must have admin rights)
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjA5NjdhNmE2LTIxNzAtNDhiOC1hZDE3LWQxODRmY2Y2NDY5MyIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vbG9jYWxob3N0OjgwMDAvYXV0aC92MSIsInN1YiI6IjBhYWRtaW4tZWFkLWYxMi1hYmM4LTM3MDk0NmRkZjFiYiIsImF1ZCI6ImF1dGhlbnRpY2F0ZWQiLCJleHAiOjE3ODg2MzU3ODQsImlhdCI6MTc4ODU0OTM4NCwiZW1haWwiOiJhZG1pbkBleGFtcGxlLmNvbSIsInJvbGUiOiJhZG1pbiIsInVzZXJfbWV0YWRhdGEiOnsidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9LCJzZXNzaW9uX2lkIjoiYWJjMTIzNDU2LTc4OS0xMjMtYWJjZC00NTY3ODkwMTIzNDU2In0.xC7XDqJYrGmQOgwCuGnJDCKRmbDyl2ge69ksjXGRLRodrYmP3h_l5exaoNYTzECJxY7fHZgMJdry1f5dRRL7lpQ"

USER_HEADERS = {
    "Authorization": f"Bearer {USER_TOKEN}",
    "Content-Type": "application/json"
}

ADMIN_HEADERS = {
    "Authorization": f"Bearer {ADMIN_TOKEN}",
    "Content-Type": "application/json"
}

def test_post_api_groups_domain_verification_confirm_otp_code():
    session = requests.Session()
    timeout = 30

    group_id = None
    try:
        # Step 1: Create a sponsored group to test on via admin endpoint
        # Payload for creating a sponsored group
        create_payload = {
            "name": "Test Sponsored Group for OTP Confirm",
            "description": "Group created for OTP confirm test",
            "is_sponsored": True
        }
        create_resp = session.post(
            f"{BASE_URL}/api/admin/sponsored-groups",
            json=create_payload,
            headers=ADMIN_HEADERS,
            timeout=timeout
        )
        assert create_resp.status_code in (200, 201), f"Group creation failed: {create_resp.text}"
        group_data = create_resp.json()
        group_id = group_data.get("id")
        assert group_id is not None, "Created group ID is missing"

        # Step 2: Add an approved domain for the sponsored group
        domain_payload = {"domain": "example.com"}
        domain_resp = session.post(
            f"{BASE_URL}/api/admin/sponsored-groups/{group_id}/domains",
            json=domain_payload,
            headers=ADMIN_HEADERS,
            timeout=timeout
        )
        assert domain_resp.status_code == 200, f"Adding domain failed: {domain_resp.text}"

        # Step 3: Request OTP for domain verification using a sponsor email in the allowed domain
        email_request_payload = {
            "email": "testuser@example.com"
        }
        otp_request_resp = session.post(
            f"{BASE_URL}/api/groups/{group_id}/domain-verification/request",
            json=email_request_payload,
            headers=USER_HEADERS,
            timeout=timeout
        )
        assert otp_request_resp.status_code == 200, f"OTP request failed: {otp_request_resp.text}"

        # Normally we'd get the OTP from email or a mock service - since it's testing confirm endpoint, let's simulate a valid OTP
        # For this test, we assume the OTP code "123456" for demonstration
        confirm_payload = {
            "group_id": group_id,
            "otp_code": "123456"
        }
        # Step 4: Confirm the OTP code for domain verification
        confirm_resp = session.post(
            f"{BASE_URL}/api/groups/domain-verification/confirm",
            json=confirm_payload,
            headers=USER_HEADERS,
            timeout=timeout
        )
        assert confirm_resp.status_code == 200, f"OTP confirm failed: {confirm_resp.text}"
        confirm_json = confirm_resp.json()
        # Verify response indicates successful verification
        assert confirm_json.get("verified") is True or confirm_json.get("message", "").lower().find("success") != -1, \
            "OTP confirmation did not indicate success"
    finally:
        # Cleanup: delete the created sponsored group if it was created
        if group_id:
            delete_resp = session.delete(
                f"{BASE_URL}/api/admin/sponsored-groups/{group_id}",
                headers=ADMIN_HEADERS,
                timeout=timeout
            )
            # No assertion on delete, just try best effort cleanup
            pass

test_post_api_groups_domain_verification_confirm_otp_code()
