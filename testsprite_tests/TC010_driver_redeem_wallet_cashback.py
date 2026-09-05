import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def test_driver_redeem_wallet_cashback():
    # Step 1: Get current wallet state
    wallet_url = f"{BASE_URL}/api/v1/drivers/me/wallet"
    try:
        get_response = requests.get(wallet_url, headers=HEADERS, timeout=30)
        assert get_response.status_code == 200, f"Expected 200 on GET wallet, got {get_response.status_code}"
        wallet_data = get_response.json()
        cashback_available = wallet_data.get("cashback", 0) if isinstance(wallet_data, dict) else 0
    except requests.RequestException as e:
        assert False, f"GET wallet request failed: {e}"

    # Step 2: Redeem accumulated cashback via POST /wallet only if cashback > 0
    if cashback_available and cashback_available > 0:
        redeem_payload = {"amount": cashback_available}
        try:
            post_response = requests.post(wallet_url, headers=HEADERS, json=redeem_payload, timeout=30)
        except requests.RequestException as e:
            assert False, f"POST redeem wallet request failed: {e}"

        # Validate response is 200 and has updated wallet state
        assert post_response.status_code == 200, f"Expected 200 on redeem POST, got {post_response.status_code}"
        try:
            post_data = post_response.json()
        except ValueError:
            assert False, "Response is not valid JSON"

        assert isinstance(post_data, dict), "Response JSON is not an object"
        post_cashback = post_data.get("cashback")
        assert post_cashback is not None, "Response missing 'cashback' field after redemption"
        assert post_cashback <= cashback_available, (
            f"Cashback after redemption ({post_cashback}) should be <= cashback before ({cashback_available})"
        )
    else:
        # If no cashback available, cannot redeem. This scenario is valid and no POST call is made.
        assert cashback_available == 0, "Cashback should be zero or missing if not redeeming"


test_driver_redeem_wallet_cashback()
