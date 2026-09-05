import requests
import time

BASE_URL = "http://localhost:8000"

# Driver token (as given)
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Admin token - placeholder, must be replaced with valid admin token for real test
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImFkbWluLXRva2VuLXBsYWNlaG9sZGVyIiwi"  # Example truncated token
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

TIMEOUT = 30

def test_post_admin_wallet_topup_request_reject_rejects_request():
    # Step 1: Create a wallet top-up request as driver to get request_id
    # Get top-up settings to find a valid amount
    settings_resp = requests.get(
        f"{BASE_URL}/api/wallet/topup/settings", headers=HEADERS, timeout=TIMEOUT
    )
    assert settings_resp.status_code == 200, f"Failed to get settings: {settings_resp.text}"
    settings_data = settings_resp.json()
    min_amount = settings_data.get("min_amount", 1)
    max_amount = settings_data.get("max_amount", 1000)
    amount = max(min_amount, 1)

    # Submit top-up request as driver
    topup_payload = {
        "amount": amount,
        "payment_reference": f"reject-test-{int(time.time())}",
        "screenshot": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    }
    topup_resp = requests.post(
        f"{BASE_URL}/api/wallet/topup", headers=HEADERS, json=topup_payload, timeout=TIMEOUT
    )
    assert topup_resp.status_code in (200, 201), f"Failed to create topup: {topup_resp.text}"
    topup_data = topup_resp.json()
    request_id = topup_data.get("id")

    assert request_id is not None, "Topup request creation did not return request id"

    try:
        # Step 2: As admin, reject the wallet top-up request
        reject_resp = requests.post(
            f"{BASE_URL}/api/admin/wallet-topup-requests/{request_id}/reject",
            headers=ADMIN_HEADERS,
            timeout=TIMEOUT,
        )
        assert reject_resp.status_code == 200, f"Failed to reject topup request: {reject_resp.text}"
        reject_data = reject_resp.json()
        assert (
            "status" in reject_data and reject_data["status"] == "rejected"
        ), f"Topup request status not rejected: {reject_data}"

        # Step 3: Verify the request status is updated to rejected by fetching admin history
        history_resp = requests.get(
            f"{BASE_URL}/api/admin/wallet-topup-requests/history",
            headers=ADMIN_HEADERS,
            timeout=TIMEOUT,
        )
        assert history_resp.status_code == 200, f"Failed to get admin history: {history_resp.text}"
        history_data = history_resp.json()
        assert any(
            req.get("id") == request_id and req.get("status") == "rejected" for req in history_data
        ), "Rejected request not found in admin history with correct status"

    finally:
        # Cleanup if possible (API does not specify deletion, so skip)
        pass


test_post_admin_wallet_topup_request_reject_rejects_request()
