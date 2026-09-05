import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}
TIMEOUT = 30

def test_post_api_v1_org_access_confirm_otp_code():
    # Step 1: Request OTP for a valid org-domain email
    request_url = f"{BASE_URL}/api/v1/org-access/request"
    valid_org_email = "test@triplyy.com"  # Assuming triplyy.com is approved domain for test
    request_payload = {"email": valid_org_email}

    res_request = requests.post(request_url, json=request_payload, headers=HEADERS, timeout=TIMEOUT)
    assert res_request.status_code in (200, 201), f"Expected 200 or 201 on OTP request, got {res_request.status_code}"

    # Extract OTP from response or simulate OTP retrieval
    otp_code = None
    try:
        data = res_request.json()
        otp_code = data.get("otp_code")
    except Exception:
        pass

    if not otp_code:
        otp_code = "123456"

    confirm_url = f"{BASE_URL}/api/v1/org-access/confirm"

    # Step 2: Confirm OTP with correct code
    confirm_payload_correct = {"otp_code": otp_code}
    res_confirm_correct = requests.post(confirm_url, json=confirm_payload_correct, headers=HEADERS, timeout=TIMEOUT)
    assert res_confirm_correct.status_code == 200, f"Expected 200 on correct OTP confirm, got {res_confirm_correct.status_code}"
    profile_data = res_confirm_correct.json()
    assert "org_verified_at" in profile_data and profile_data["org_verified_at"], "org_verified_at not marked in profile"
    assert "org_verified_domain" in profile_data and profile_data["org_verified_domain"], "org_verified_domain not marked in profile"

    # Step 3: Confirm OTP with incorrect code
    confirm_payload_incorrect = {"otp_code": "000000"}
    res_confirm_incorrect = requests.post(confirm_url, json=confirm_payload_incorrect, headers=HEADERS, timeout=TIMEOUT)
    assert res_confirm_incorrect.status_code == 400, f"Expected 400 on incorrect OTP confirm, got {res_confirm_incorrect.status_code}"

    profile_me_url = f"{BASE_URL}/api/profiles/me"
    res_profile = requests.get(profile_me_url, headers=HEADERS, timeout=TIMEOUT)
    assert res_profile.status_code == 200, f"Expected 200 on profile/me fetch, got {res_profile.status_code}"
    profile_after = res_profile.json()
    assert "org_verified_at" in profile_after and profile_after["org_verified_at"], "Verification should remain after incorrect OTP attempt"
    assert "org_verified_domain" in profile_after and profile_after["org_verified_domain"], "Verification domain should remain after incorrect OTP attempt"

test_post_api_v1_org_access_confirm_otp_code()
