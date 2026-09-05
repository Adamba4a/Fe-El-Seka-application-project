import requests
import uuid

BASE_URL = "http://localhost:8000"
DRIVER_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiIyYjYxYjQ4ZS0xZWMyLTRjYjMtYjJjMS03NTBkMGY1NjNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjM1Nzg0LCJpYXQiOjE3ODg1NDkzODQsImVtYWlsIjoidGVzdHNwcml0ZS5kcml2ZXIrNGYyNDEzNThAZXhhbXBsZS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU0OTM4NH1dLCJzZXNzaW9uX2lkIjoiOTBhZGIzOTktMzJkNy00YWY2LTllNTQtMWE4YTA5YjYzMzYxIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.7tnorXc_v1GajgbKOx_eL1YOszeBUfjHR8eD_sTpsMVGd1byScCiaea2NrexKmTDL3dIlmobE5Mqry_s39Blkw"
ADMIN_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6ImI4MTI2OWYxLTIxZDgtNGYyZS1iNzE5LWMyMjQwYTg0MGQ5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwOi8vMTI3LjAuMC4xOjU0MzIxL2F1dGgvdjEiLCJzdWIiOiI1N2I1MjY0My1hOGM2LTQxNTAtYjI3ZS04NzY3MTg3ZDIwMzAiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzg4NjQ3NjgwLCJpYXQiOjE3ODg1NjEyODAsImVtYWlsIjoiYWRtaW5AdHJpcGx5eS5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc4ODU2MTI4MH1dLCJzZXNzaW9uX2lkIjoiZTZhNGE5MDMtZDBjMy00MWU5LWEyMGQtNzc1NjEwN2RkM2M0IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.Ntg7e0ufpK5UYOQ73Ve63NQxVtxWS66NZ0pXZj03Mv2igmU-js51NCIACpMprr8xppT2dcHCqFVNE3ZldH0qnw"

def test_post_api_wallet_withdrawals_submit_and_admin_reject():
    driver_headers = {
        "Authorization": f"Bearer {DRIVER_TOKEN}",
        "Content-Type": "application/json",
    }
    admin_headers = {
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json",
    }

    # Generate unique payout_reference to avoid collisions
    random_suffix = str(uuid.uuid4())
    payout_reference = f"TESTSPRITE-TC013-{random_suffix}"

    # Step 1: DRIVER submits a withdrawal request
    withdrawal_submit_url = f"{BASE_URL}/api/wallet/withdrawals"
    withdrawal_payload = {
        "amount_egp": 100.00,
        "payout_reference": payout_reference,
    }

    try:
        resp = requests.post(
            withdrawal_submit_url,
            headers=driver_headers,
            json=withdrawal_payload,
            timeout=30,
        )
        assert resp.status_code == 201, f"Expected 201 on withdrawal submission but got {resp.status_code}"
        resp_json = resp.json()
        withdrawal_id = resp_json.get("id")
        assert withdrawal_id, "Response JSON did not contain 'id' for withdrawal request"

        # Step 2: ADMIN rejects the withdrawal request with a reason
        admin_reject_url = f"{BASE_URL}/api/admin/withdrawal-requests/{withdrawal_id}/reject"
        reject_payload = {"reason": "TestSprite TC013 test rejection"}
        admin_resp = requests.post(
            admin_reject_url,
            headers=admin_headers,
            json=reject_payload,
            timeout=30,
        )
        assert admin_resp.status_code == 200, f"Expected 200 on admin rejection but got {admin_resp.status_code}"
    finally:
        # Cleanup: Attempt to delete the withdrawal request if such an endpoint exists to maintain test hygiene.
        # The PRD does not specify a DELETE endpoint for withdrawal requests; hence, no deletion code here.
        # If deletion or cancellation endpoint exists, it can be called here.
        pass

test_post_api_wallet_withdrawals_submit_and_admin_reject()