import requests

def test_post_api_auth_verify_otp_with_valid_code():
    base_url = "http://localhost:8000"
    url = f"{base_url}/api/auth/verify-otp"
    headers = {
        "Authorization": "Bearer eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw",
        "Content-Type": "application/json"
    }
    # For a valid OTP code we must provide a code, email or phone field for the verify-otp endpoint payload.
    # The PRD does not specify exact required fields for /api/auth/verify-otp payload besides it verifying a code.
    # Commonly the payload should contain "email" and "otp" code or similar.
    # Since we have no specific code given, we'll use a placeholder valid OTP code and email from the token.
    payload = {
        "email": "testssprite.driver+4f241358@example.com",
        "otp": "123456"  # This should be a valid OTP code; real tests might insert dynamic OTPs but here hard-coded.
    }
    timeout = 30

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)

    # Assert the response status code is 200
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"

    json_resp = response.json()

    # Assert the response contains session tokens (likely access_token and refresh_token or similar fields)
    assert "access_token" in json_resp or "accessToken" in json_resp, "Response missing access token"
    assert "refresh_token" in json_resp or "refreshToken" in json_resp, "Response missing refresh token"

    # Optionally assert signup event recorded by fraud signal by checking any event or message field (if present)
    # As PRD doesn't state response contents for fraud signal, we skip explicit check here.

test_post_api_auth_verify_otp_with_valid_code()