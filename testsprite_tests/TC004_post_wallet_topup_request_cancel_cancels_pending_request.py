import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def test_post_wallet_topup_request_cancel_cancels_pending_request():
    session = requests.Session()
    session.headers.update(HEADERS)
    timeout = 30
    
    # Step 1: Create a new top-up request to ensure a pending request exists
    topup_payload = {
        "amount_egp": 10.0,
        "payment_reference": "unittest-cancel-test",
        "screenshot": "test_screenshot_data"
    }
    
    try:
        create_resp = session.post(f"{BASE_URL}/api/wallet/topup", json=topup_payload, timeout=timeout)
        assert create_resp.status_code in (200, 201), f"Failed to create top-up request: {create_resp.text}"
        create_data = create_resp.json()
        request_id = create_data.get("id") or create_data.get("request_id")
        assert request_id, "Created top-up request ID not found in response"
        
        # Step 2: Cancel the pending top-up request
        cancel_resp = session.post(f"{BASE_URL}/api/wallet/topup/{request_id}/cancel", timeout=timeout)
        assert cancel_resp.status_code == 200, f"Failed to cancel top-up request: {cancel_resp.text}"
        cancel_data = cancel_resp.json()
        
        # Step 3: Verify cancellation is confirmed in response
        # Assuming an indication like 'status' or 'message' that confirms cancellation
        # Check if status is "canceled" or similar
        status = cancel_data.get("status")
        if not status:
            # fallback to message check
            message = cancel_data.get("message","").lower()
            assert "cancel" in message or "canceled" in message, f"Cancellation confirmation missing: {cancel_data}"

        else:
            assert status.lower() in ("canceled", "cancelled"), f"Request status after cancel not 'canceled': {status}"
        
        # Step 4: Verify via GET /api/wallet/topup that the request status is updated to canceled
        history_resp = session.get(f"{BASE_URL}/api/wallet/topup", timeout=timeout)
        assert history_resp.status_code == 200, f"Failed to fetch top-up history: {history_resp.text}"
        history_data = history_resp.json()
        assert isinstance(history_data, list), "Top-up history response is not a list"
        canceled_request = None
        for req in history_data:
            if str(req.get("id") or req.get("request_id")) == str(request_id):
                canceled_request = req
                break
        assert canceled_request is not None, "Canceled request not found in top-up history"
        # Confirm that status is updated to canceled
        req_status = canceled_request.get("status")
        assert req_status is not None, "Status field missing in top-up history request"
        assert str(req_status).lower() in ("canceled", "cancelled"), f"Request status expected to be 'canceled' but got '{req_status}'"
    
    finally:
        # Cleanup: Attempt to delete the created request if API supports it
        # The PRD does not mention DELETE /api/wallet/topup/{request_id}
        # So this block is left intentionally blank
        pass

test_post_wallet_topup_request_cancel_cancels_pending_request()
