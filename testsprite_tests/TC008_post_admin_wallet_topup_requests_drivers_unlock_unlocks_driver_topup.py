import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZHRhIjp7InByb3ZpZGVyIjoiZW1haWwiLCJwcm92aWRlcnMiOlsiZW1haWwiXX0sInVzZXJfbWV0YWRhdGEiOnsiZW1haWxfdmVyaWZpZWQiOnRydWV9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6InBhc3N3b3JkIiwidGltZXN0YW1wIjoxNzg4NTQ5Mzg0fV0sInNlc3Npb25faWQiOiI5MGFkYjM5OS0zMmQ3LTRhZjYtOWU1NC0xYThhMDliNjMzNjEiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
TIMEOUT = 30

def test_post_admin_wallet_topup_requests_drivers_unlock_unlocks_driver_topup():
    # Step 1: Get the current driver's id from token info or create a dummy driver top-up request to extract driver_id
    # Since no driver_id is provided, we must create a new resource: a wallet top-up request to get a suitable driver_id.

    # Create a new wallet top-up request to find driver_id from the associated request or token
    topup_payload = {
        "amount": 10,  # assuming 10 is a valid amount within limits
        "reference_data": "unlock_test_case"
    }
    # POST /api/wallet/topup requires driver token - provided token is driver token
    topup_response = requests.post(
        f"{BASE_URL}/api/wallet/topup",
        json=topup_payload,
        headers=HEADERS,
        timeout=TIMEOUT
    )
    assert topup_response.status_code in [200,201], f"Failed to create wallet top-up request, status: {topup_response.status_code}"
    topup_data = topup_response.json()

    try:
        # Extract driver_id from token or from response data (no explicit driver_id field in response - assume from token)
        # The token subject is the driver unique identifier, or possibly topup_data includes driver_id (not specified in PRD)
        # So, parse driver_id from token payload "sub"
        import jwt
        # jwt.decode without signature verification to extract payload (token is ES256)
        driver_id = None
        try:
            driver_payload = jwt.decode(TOKEN, options={"verify_signature": False, "verify_aud": False})
            driver_id = driver_payload.get("sub")
        except Exception:
            pass

        assert driver_id is not None, "Could not extract driver_id from token."

        # Step 2: POST /api/admin/wallet-topup-requests/drivers/{driver_id}/unlock
        unlock_url = f"{BASE_URL}/api/admin/wallet-topup-requests/drivers/{driver_id}/unlock"
        unlock_response = requests.post(
            unlock_url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        # Validate success response code
        assert unlock_response.status_code == 200, f"Expected 200 OK, got {unlock_response.status_code}: {unlock_response.text}"
        unlock_json = unlock_response.json()
        # Validate response has confirmation of unlock (not detailed in PRD - assume presence of success key or message)
        assert isinstance(unlock_json, dict), "Unlock response is not a JSON object"
        assert any(
            key in unlock_json for key in ("message", "detail", "success", "unlocked")
        ), "Unlock response does not contain confirmation message"

    finally:
        # Cleanup: cancel the created top-up request to avoid data pollution
        request_id = topup_data.get("id") or topup_data.get("request_id")
        if request_id:
            cancel_url = f"{BASE_URL}/api/wallet/topup/{request_id}/cancel"
            cancel_response = requests.post(
                cancel_url,
                headers=HEADERS,
                timeout=TIMEOUT
            )
            # Cancellation may or may not succeed if status changed - ignore errors in cleanup

test_post_admin_wallet_topup_requests_drivers_unlock_unlocks_driver_topup()