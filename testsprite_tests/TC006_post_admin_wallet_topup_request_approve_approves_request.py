import requests

BASE_URL = "http://localhost:8000"
ADMIN_AUTH_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"


def test_post_admin_wallet_topup_request_approve_approves_request():
    headers = {
        "Authorization": f"Bearer {ADMIN_AUTH_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Step 1: Create a wallet top-up request as a driver
    # Note: The admin token belongs to a driver account and cannot create requests properly (403 expected),
    # so we create the resource via admin queue if exists, else fail the test.
    # But from PRD we see driver role token only, and admin endpoints require admin token,
    # The provided token is for driver role, so admin endpoints return 403.
    # This test requires an admin token and a valid pending top-up request id.
    # Since no request id provided, try to find a pending request from admin queue.

    # Get pending wallet top-up requests (admin endpoint)
    pending_url = f"{BASE_URL}/api/admin/wallet-topup-requests"
    try:
        resp = requests.get(pending_url, headers=headers, timeout=30)
        assert resp.status_code == 200, f"Failed to fetch pending requests, status: {resp.status_code}"

        pending_requests = resp.json()
        assert isinstance(pending_requests, list), "Pending requests response should be a list"
        assert len(pending_requests) > 0, "No pending wallet top-up requests available to approve"

        first_request = pending_requests[0]
        request_id = first_request.get("id") or first_request.get("request_id")
        assert request_id, "Pending request missing 'id' or 'request_id' field"

        # Approve the wallet top-up request
        approve_url = f"{BASE_URL}/api/admin/wallet-topup-requests/{request_id}/approve"
        approve_resp = requests.post(approve_url, headers=headers, timeout=30)
        assert approve_resp.status_code == 200, f"Approval failed with status {approve_resp.status_code}"

        approve_data = approve_resp.json()
        assert approve_data.get("status") == "approved" or approve_data.get("status") == "APPROVED" or "approved" in approve_data.values(), (
            f"Request status not updated to approved: {approve_data}"
        )

        # Verify that the status updated correctly by fetching the request in history
        history_url = f"{BASE_URL}/api/admin/wallet-topup-requests/history"
        history_resp = requests.get(history_url, headers=headers, timeout=30)
        assert history_resp.status_code == 200, f"Failed to fetch admin history, status: {history_resp.status_code}"

        history_list = history_resp.json()
        assert isinstance(history_list, list), "Admin history response should be a list"

        # Find the approved request in the history by ID
        approved_requests = [r for r in history_list if (r.get("id") == request_id or r.get("request_id") == request_id)]
        assert len(approved_requests) == 1, f"Approved request id {request_id} not found in history"

        approved_request = approved_requests[0]
        assert approved_request.get("status") == "approved" or approved_request.get("status") == "APPROVED", (
            f"Approved request status is not correct in history: {approved_request}"
        )

    except Exception as e:
        raise e


test_post_admin_wallet_topup_request_approve_approves_request()